"""Bounded autonomous scientific maintenance.

Turns detected maintenance needs into auditable research-work proposals.
It never mutates scientific state or approves evidence.
"""
from uuid import uuid4
from app.models import now

class AutonomousScientificMaintenance:
    def __init__(self,db): self.db=db

    def propose(self):
        from app.knowledge_freshness import KnowledgeFreshness
        from app.knowledge_impact import KnowledgeImpactAnalyzer
        out=[]
        for x in KnowledgeFreshness(self.db).scan()["stale"]:
            out.append({"kind":"REVALIDATION","priority":"HIGH","entity_type":x["entity_type"],"entity_id":x["entity_id"],"title":f"Revalidate {x['entity_type']} {x['entity_id']}","reason":"scientific review interval elapsed"})
        for x in KnowledgeImpactAnalyzer(self.db).contradiction_scan()["impacts"]:
            out.append({"kind":"CONTRADICTION_REVIEW","priority":"HIGH","entity_type":"CLAIM","entity_id":x["claim_id"],"title":f"Review conflicted claim {x['claim_id']}","reason":x["reason"]})
        return {"count":len(out),"proposals":out,"policy":"proposal only; execution requires normal task, approval, cost and evidence gates"}

    def create_tasks(self,project_id,owner="chief-scientist"):
        created=[]
        for p in self.propose()["proposals"]:
            existing=self.db.one("SELECT id FROM tasks WHERE project_id=? AND title=? AND status NOT IN ('COMPLETED','FAILED')",(project_id,p["title"]))
            if existing: continue
            task_id=str(uuid4())
            self.db.execute("INSERT INTO tasks(id,project_id,title,assigned_agent_id,priority,status,success_criteria,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
                (task_id,project_id,p["title"],owner,1.0,"PLANNED","Produce an evidence-backed review with explicit uncertainty and no silent state mutation.",now(),now()))
            created.append(task_id)
        return created
    def materialize(self,actor="system"):
        proposals=self.propose()["proposals"]
        created=[]
        for p in proposals:
            exists=self.db.one("SELECT id FROM maintenance_work WHERE kind=? AND entity_type=? AND entity_id=? AND status IN ('PROPOSED','APPROVAL_PENDING','APPROVED','RUNNING')",(p["kind"],p["entity_type"],p["entity_id"]))
            if exists:
                continue
            wid=str(uuid4())
            self.db.execute(
                "INSERT INTO maintenance_work(id,kind,entity_type,entity_id,title,reason,success_criteria,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (wid,p["kind"],p["entity_type"],p["entity_id"],p["title"],p["reason"],
                 "Produce an evidence-backed review and explicit recommendation; do not silently mutate scientific state.",
                 "PROPOSED",now(),now()))
            created.append(wid)
        return {"created":created,"count":len(created),"policy":"materialization creates auditable work only"}

