"""Human-reviewable queue of next scientific questions.

The queue proposes work; it never silently changes scientific claims.
"""
import json
from uuid import uuid4
from app.models import now

class ResearchQueue:
    STATUSES = {"PROPOSED", "APPROVED", "IN_PROGRESS", "DONE", "REJECTED"}

    def __init__(self, db):
        self.db = db
        self._ensure()

    def _ensure(self):
        self.db.execute("""CREATE TABLE IF NOT EXISTS hds_research_queue (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            question TEXT NOT NULL,
            rationale TEXT NOT NULL,
            trigger_type TEXT NOT NULL,
            evidence_refs TEXT NOT NULL DEFAULT '[]',
            priority TEXT NOT NULL DEFAULT 'NORMAL',
            status TEXT NOT NULL DEFAULT 'PROPOSED',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )""")

    def propose(self, project_id, question, rationale, trigger_type="MANUAL",
                evidence_refs=(), priority="NORMAL"):
        if not str(question or "").strip() or not str(rationale or "").strip():
            raise ValueError("question and rationale are required")
        existing=self.db.one(
            "SELECT * FROM hds_research_queue WHERE project_id=? AND question=? AND status IN ('PROPOSED','APPROVED','IN_PROGRESS') LIMIT 1",
            (project_id,question))
        if existing:
            return existing
        if priority not in {"LOW", "NORMAL", "HIGH", "CRITICAL"}:
            raise ValueError("invalid priority")
        i = str(uuid4())
        ts = now()
        self.db.execute(
            """INSERT INTO hds_research_queue
            (id,project_id,question,rationale,trigger_type,evidence_refs,priority,status,created_at,updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (i, project_id, question, rationale, trigger_type,
             json.dumps(list(evidence_refs), sort_keys=True), priority, "PROPOSED", ts, ts),
        )
        return self.get(i)

    def get(self, item_id):
        return self.db.one("SELECT * FROM hds_research_queue WHERE id=?", (item_id,))

    def approve(self, item_id, actor):
        row = self.get(item_id)
        if not row or row["status"] != "PROPOSED":
            raise ValueError("research item is not awaiting approval")
        if not str(actor or "").strip():
            raise ValueError("actor is required")
        updated=self.db.execute(
            "UPDATE hds_research_queue SET status='APPROVED', updated_at=? WHERE id=? AND status='PROPOSED'",
            (now(), item_id),
        )
        if updated.rowcount != 1:
            raise ValueError("research item was changed concurrently")
        return self.get(item_id)

    def begin(self, item_id, actor):
        row=self.get(item_id)
        if not row or row["status"]!="APPROVED":
            raise ValueError("research item must be APPROVED before work begins")
        from app.research_engine import ResearchEngine
        engine=ResearchEngine(self.db)
        existing=self.db.one(
            "SELECT * FROM research_workspaces WHERE project_id=? AND question=? AND status IN ('DRAFT','ACTIVE','SYNTHESIS_READY','REVIEWED') LIMIT 1",
            (row["project_id"],row["question"]))
        workspace=existing or engine.create(
            row["project_id"],row["question"],
            scope="Created from founder-approved research queue item.",
            owner=actor)
        if workspace["status"]=="DRAFT":
            workspace=engine.activate(workspace["id"],actor)
        with self.db.transaction() as con:
            updated=con.execute("UPDATE hds_research_queue SET status='IN_PROGRESS',updated_at=? WHERE id=? AND status='APPROVED'",(now(),item_id))
            if updated.rowcount != 1:
                raise ValueError("research item was changed concurrently")
            con.execute("INSERT INTO audit_logs(id,event_type,entity_type,entity_id,actor,payload,created_at) VALUES (?,?,?,?,?,?,?)",
                        (str(uuid4()),"research_queue.started","research_queue",item_id,actor,
                         json.dumps({"workspace_id":workspace["id"]},sort_keys=True),now()))
        return {"queue_item":self.get(item_id),"workspace":workspace}

    def list(self, project_id, status=None):
        if status and status not in self.STATUSES:
            raise ValueError("invalid status")
        if status:
            return self.db.all(
                "SELECT * FROM hds_research_queue WHERE project_id=? AND status=? ORDER BY created_at DESC",
                (project_id, status),
            )
        return self.db.all(
            "SELECT * FROM hds_research_queue WHERE project_id=? ORDER BY created_at DESC",
            (project_id,),
        )
