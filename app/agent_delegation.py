"""Scientific-to-company agent delegation bridge.

Turns approved/reviewable scientific work into normal HDS tasks while keeping
high-risk actions and scientific state changes behind existing gates.
"""
from app.tasks import TaskEngine
from app.planner import AutonomousPlanner
from app.models import now

ROLE_MAP={
    "RESEARCH":"researcher",
    "SKEPTIC":"skeptic",
    "CONTRADICTION":"skeptic",
    "IMPACT":"knowledge-manager",
    "EXPERIMENT":"experiment-designer",
    "INTEGRITY":"evidence-auditor",
    "AGENT_OUTPUT":"knowledge-manager",
}

class AgentDelegation:
    def __init__(self,db):
        self.db=db
        self.tasks=TaskEngine(db)

    def delegate(self,project_id,decision):
        kind=decision.get("type","RESEARCH").upper()
        agent=ROLE_MAP.get(kind,"founder-advisor")
        title=f"[{kind}] {decision.get('title','Scientific review')}"
        criteria=decision.get("reason","Produce a traceable, reviewable output.")
        task=self.tasks.create_task(
            title=title,
            description=criteria,
            project_id=project_id,
            owner=agent,
            required_permissions=["READ"],
            priority={"CRITICAL":1.5,"HIGH":1.2,"NORMAL":1.0,"LOW":0.7}.get(decision.get("priority","NORMAL"),1.0),
            retry_limit=1,
        )
        self.db.audit("scientific.task_delegated","task",task["id"],"scientific-orchestrator",{
            "decision_type":kind,"agent":agent,"decision_id":decision.get("id")
        },now(),None)
        return task

    def delegate_pending(self,project_id,limit=5):
        from app.decision_center import DecisionCenter
        decisions=DecisionCenter(self.db).list(project_id)
        created=[]
        for d in decisions[:max(0,int(limit))]:
            existing=self.db.one(
                "SELECT id FROM tasks WHERE project_id=? AND title=? AND status NOT IN ('COMPLETED','CANCELLED')",
                (project_id,f"[{d['type']}] {d['title']}")
            )
            if existing: continue
            created.append(self.delegate(project_id,d))
        return created
