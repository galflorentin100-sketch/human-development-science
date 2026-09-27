"""Bounded autonomous scientific maintenance.

Turns detected maintenance needs into auditable research-work proposals.
It never mutates scientific state or approves evidence.
"""
from uuid import uuid4
from app.models import now

class AutonomousScientificMaintenance:
    def __init__(self,db): self.db=db

    def _entity_project(self,entity_type,entity_id):
        table={"CLAIM":"claims","INTERVENTION":"interventions","TRAINING_PROTOCOL":"training_protocols"}.get(entity_type)
        if not table:
            raise ValueError("unsupported maintenance entity type")
        row=self.db.one(f"SELECT project_id FROM {table} WHERE id=?",(entity_id,))
        return row["project_id"] if row else None

    def propose(self,project_id=None):
        from app.knowledge_freshness import KnowledgeFreshness
        from app.knowledge_impact import KnowledgeImpactAnalyzer
        out=[]
        for x in KnowledgeFreshness(self.db).scan()["stale"]:
            out.append({"kind":"REVALIDATION","priority":"HIGH","entity_type":x["entity_type"],"entity_id":x["entity_id"],"title":f"Revalidate {x['entity_type']} {x['entity_id']}","reason":"scientific review interval elapsed","success_criteria":"Revalidate the entity against current evidence and record explicit uncertainty."})
        for x in KnowledgeImpactAnalyzer(self.db).contradiction_scan()["impacts"]:
            out.append({"kind":"CONTRADICTION_REVIEW","priority":"HIGH","entity_type":"CLAIM","entity_id":x["claim_id"],"title":f"Review conflicted claim {x['claim_id']}","reason":x["reason"],"success_criteria":"Resolve or document the contradiction using independently reviewed evidence."})
        if project_id is not None:
            out=[p for p in out if self._entity_project(p["entity_type"],p["entity_id"]) == project_id]
        return {"count":len(out),"proposals":out,"policy":"proposal only; execution requires normal task, approval, cost and evidence gates"}

    def create_tasks(self,project_id,owner="chief-scientist"):
        created=[]
        for p in self.propose(project_id=project_id)["proposals"]:
            with self.db.transaction() as con:
                existing_link=con.execute(
                    "SELECT task_id FROM maintenance_task_links WHERE kind=? AND entity_type=? AND entity_id=?",
                    (p["kind"],p["entity_type"],p["entity_id"])).fetchone()
                if existing_link:
                    continue
                existing=con.execute(
                    "SELECT id FROM tasks WHERE project_id=? AND title=? AND status NOT IN ('COMPLETED','FAILED')",
                    (project_id,p["title"])).fetchone()
                if existing:
                    con.execute(
                        "INSERT INTO maintenance_task_links(task_id,kind,entity_type,entity_id,created_at) VALUES (?,?,?,?,?) ON CONFLICT(kind,entity_type,entity_id) DO NOTHING",
                        (dict(existing)["id"],p["kind"],p["entity_type"],p["entity_id"],now()))
                    continue
                task_id=str(uuid4())
                ts=now()
                con.execute(
                    "INSERT INTO tasks(id,project_id,title,assigned_agent_id,priority,status,success_criteria,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
                    (task_id,project_id,p["title"],owner,1.0,"PLANNED",
                     "Produce an evidence-backed review with explicit uncertainty and no silent state mutation.",ts,ts))
                linked=con.execute(
                    "INSERT INTO maintenance_task_links(task_id,kind,entity_type,entity_id,created_at) VALUES (?,?,?,?,?) ON CONFLICT(task_id) DO NOTHING",
                    (task_id,p["kind"],p["entity_type"],p["entity_id"],ts))
                if linked.rowcount == 1:
                    created.append(task_id)
                else:
                    con.execute("DELETE FROM tasks WHERE id=?",(task_id,))
        return created

    def materialize(self,actor="system"):
        proposals=self.propose()["proposals"]
        created=[]
        for p in proposals:
            if self._entity_project(p["entity_type"],p["entity_id"]) is None:
                continue
            wid=str(uuid4())
            with self.db.transaction() as con:
                inserted=con.execute(
                    "INSERT INTO maintenance_work(id,kind,entity_type,entity_id,title,reason,success_criteria,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?) ON CONFLICT(kind,entity_type,entity_id) WHERE status IN ('PROPOSED','APPROVAL_PENDING','APPROVED','IN_PROGRESS') DO NOTHING",
                    (wid,p["kind"],p["entity_type"],p["entity_id"],p["title"],p["reason"],
                     "Produce an evidence-backed review and explicit recommendation; do not silently mutate scientific state.",
                     "PROPOSED",now(),now()))
                if inserted.rowcount == 1:
                    created.append(wid)
        return {"created":created,"count":len(created),"policy":"materialization creates auditable work only"}

