from app.tasks import TaskEngine
from app.models import now
from uuid import uuid4

class ResearchReviewPipeline:
    def __init__(self, db):
        self.db=db
        self.tasks=TaskEngine(db)
        self.db.execute("CREATE TABLE IF NOT EXISTS research_review_tasks (task_id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, synthesis_id TEXT NOT NULL, role TEXT NOT NULL, created_at TEXT NOT NULL, UNIQUE(workspace_id,synthesis_id,role))")

    def create_for_synthesis(self, synthesis_id):
        syn=self.db.one("SELECT * FROM research_syntheses WHERE id=?",(synthesis_id,))
        if not syn: raise ValueError("synthesis not found")
        ws=self.db.one("SELECT * FROM research_workspaces WHERE id=?",(syn["workspace_id"],))
        if not ws: raise ValueError("workspace not found")
        created=[]
        for role,title in (("skeptic","[SKEPTIC] Challenge synthesis"),("evidence-auditor","[EVIDENCE_AUDIT] Audit synthesis")):
            existing=self.db.one("SELECT task_id FROM research_review_tasks WHERE workspace_id=? AND synthesis_id=? AND role=?",(ws["id"],synthesis_id,role))
            if existing: continue
            agent=self.db.one("SELECT id FROM agents WHERE id=? AND status IN ('ACTIVE','IDLE') LIMIT 1",(role,))
            if not agent: raise ValueError("review agent not found")
            task=self.tasks.create_task(title=title+" "+synthesis_id,description="Review research synthesis "+synthesis_id,project_id=ws["project_id"],owner=agent["id"],required_permissions=["READ"],priority=1.8,retry_limit=1)
            self.db.execute("INSERT INTO research_review_tasks(task_id,workspace_id,synthesis_id,role,created_at) VALUES (?,?,?,?,?)",(task["id"],ws["id"],synthesis_id,role,now()))
            self.db.audit("scientific.research_review_task_created","task",task["id"],"research-orchestrator",{"role":role,"synthesis_id":synthesis_id},now(),str(uuid4()))
            created.append(task)
        return {"synthesis":syn,"tasks":created}
