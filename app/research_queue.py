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
            research_queue_workspace_id TEXT,
            question TEXT NOT NULL,
            rationale TEXT NOT NULL,
            trigger_type TEXT NOT NULL,
            evidence_refs TEXT NOT NULL DEFAULT '[]',
            priority TEXT NOT NULL DEFAULT 'NORMAL',
            status TEXT NOT NULL DEFAULT 'PROPOSED',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )""")
        if "research_queue_workspace_id" not in set(self.db.table_columns("hds_research_queue")):
            self.db.execute("ALTER TABLE hds_research_queue ADD COLUMN research_queue_workspace_id TEXT")

    def propose(self, project_id, question, rationale, trigger_type="MANUAL",
                evidence_refs=(), priority="NORMAL"):
        if not str(project_id or "").strip():
            raise ValueError("project_id is required")
        if not str(question or "").strip() or not str(rationale or "").strip():
            raise ValueError("question and rationale are required")
        if priority not in {"LOW", "NORMAL", "HIGH", "CRITICAL"}:
            raise ValueError("invalid priority")
        refs=[str(x) for x in (evidence_refs or ())]
        with self.db.transaction() as con:
            if not con.execute("SELECT 1 FROM projects WHERE id=?",(project_id,)).fetchone():
                raise ValueError("project not found")
            for ref in refs:
                evidence=con.execute(
                "SELECT e.id FROM evidence e JOIN claims c ON c.id=e.claim_id WHERE e.id=? AND c.project_id=?",
                (ref,project_id)).fetchone()
                if not evidence:
                    raise ValueError("research queue evidence belongs to another project or does not exist")
            existing=con.execute(
            "SELECT * FROM hds_research_queue WHERE project_id=? AND question=? AND status IN ('PROPOSED','APPROVED','IN_PROGRESS') LIMIT 1",
            (project_id,question)).fetchone()
            if existing:
                return dict(existing)
            i=str(uuid4()); ts=now()
            con.execute("""
            INSERT INTO hds_research_queue
            (id,project_id,question,rationale,trigger_type,evidence_refs,priority,status,created_at,updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (i,project_id,question,rationale,trigger_type,
                 json.dumps(refs,sort_keys=True),priority,"PROPOSED",ts,ts))
            return dict(con.execute("SELECT * FROM hds_research_queue WHERE id=?",(i,)).fetchone())


    def get(self, item_id):
        return self.db.one("SELECT * FROM hds_research_queue WHERE id=?", (item_id,))

    def approve(self, item_id, actor):
        row = self.get(item_id)
        if not row or row["status"] != "PROPOSED":
            raise ValueError("research item is not awaiting approval")
        if not str(actor or "").strip():
            raise ValueError("actor is required")
        with self.db.transaction() as con:
            updated=con.execute(
                "UPDATE hds_research_queue SET status='APPROVED', updated_at=? WHERE id=? AND status='PROPOSED'",
                (now(), item_id),
            )
            if updated.rowcount != 1:
                raise ValueError("research item was changed concurrently")
            row=dict(con.execute("SELECT * FROM hds_research_queue WHERE id=?",(item_id,)).fetchone())
        return row

    def begin(self, item_id, actor):
        if not str(actor or "").strip():
            raise ValueError("actor is required")
        with self.db.transaction() as con:
            row=con.execute("SELECT * FROM hds_research_queue WHERE id=? AND status='APPROVED'",(item_id,)).fetchone()
            if not row:
                raise ValueError("research item must be APPROVED before work begins")
            row=dict(row)
            existing=con.execute(
                "SELECT * FROM research_workspaces WHERE project_id=? AND question=? AND status IN ('DRAFT','ACTIVE','SYNTHESIS_READY','REVIEWED') LIMIT 1",
                (row["project_id"],row["question"])).fetchone()
            if existing:
                workspace=dict(existing)
            else:
                workspace_id=str(uuid4()); ts=now()
                con.execute(
                    "INSERT INTO research_workspaces(id,project_id,question,scope,inclusion_rules,exclusion_rules,status,owner,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (workspace_id,row["project_id"],row["question"],
                     "Created from founder-approved research queue item.","[]","[]","DRAFT",actor,ts,ts))
                workspace=dict(zip(
                    ["id","project_id","question","scope","inclusion_rules","exclusion_rules","status","owner","created_at","updated_at"],
                    [workspace_id,row["project_id"],row["question"],
                     "Created from founder-approved research queue item.","[]","[]","DRAFT",actor,ts,ts]))
            if workspace["status"]=="DRAFT":
                ts=now()
                updated_ws=con.execute(
                    "UPDATE research_workspaces SET status='ACTIVE',updated_at=? WHERE id=? AND status='DRAFT'",
                    (ts,workspace["id"]))
                if updated_ws.rowcount != 1:
                    raise ValueError("research workspace changed concurrently")
                workspace["status"]="ACTIVE"; workspace["updated_at"]=ts
            linked=con.execute(
                "UPDATE hds_research_queue SET research_queue_workspace_id=? WHERE id=? AND status='APPROVED' AND (research_queue_workspace_id IS NULL OR research_queue_workspace_id=?)",
                (workspace["id"],item_id,workspace["id"]))
            if linked.rowcount != 1:
                raise ValueError("research queue workspace linkage changed concurrently")
            updated=con.execute(
                "UPDATE hds_research_queue SET status='IN_PROGRESS',updated_at=? WHERE id=? AND status='APPROVED' AND research_queue_workspace_id=?",
                (now(),item_id,workspace["id"]))
            if updated.rowcount != 1:
                raise ValueError("research item was changed concurrently")
            con.execute(
                "INSERT INTO audit_logs(id,event_type,entity_type,entity_id,actor,payload,created_at) VALUES (?,?,?,?,?,?,?)",
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
