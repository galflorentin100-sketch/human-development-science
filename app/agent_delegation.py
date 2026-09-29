"""Scientific-to-company agent delegation bridge.

Turns approved/reviewable scientific work into normal HDS tasks while keeping
high-risk actions and scientific state changes behind existing gates.
"""
from app.tasks import TaskEngine
from app.planner import AutonomousPlanner
from app.models import now
from app.approvals import ApprovalService, ApprovalRequired

ROLE_MAP={
    "RESEARCH":"researcher",
    "SKEPTIC":"skeptic",
    "CONTRADICTION":"skeptic",
    "IMPACT":"chief-scientist",
    "EXPERIMENT":"experiment-designer",
    "INTEGRITY":"evidence-auditor",
    "AGENT_OUTPUT":"chief-scientist",
}

class AgentDelegation:
    def __init__(self,db):
        self.db=db
        self.tasks=TaskEngine(db)

    def delegate(self,project_id,decision):
        kind=decision.get("type","RESEARCH").upper()
        agent=ROLE_MAP.get(kind,"ceo")
        title=f"[{kind}] {decision.get('title','Scientific review')}"
        criteria=decision.get("reason","Produce a traceable, reviewable output.")

        # Governance-sensitive decisions must be explicitly approved before execution.
        if decision.get("requires_founder_approval"):
            kind=kind.upper()
            action=f"FOUNDER_DECISION:{kind}:{decision.get('id')}"
            approval=self.db.one(
                "SELECT * FROM approvals WHERE action=? AND status IN ('PENDING','APPROVED') ORDER BY created_at DESC LIMIT 1",
                (action,))
            if approval is None:
                approval=ApprovalService(self.db).request(
                    action=action,
                    requested_by="scientific-orchestrator",
                    reason=f"Founder approval required before delegating {title}.",
                    risk_level="HIGH" if decision.get("priority") in {"HIGH","CRITICAL"} else "MEDIUM",
                    context={"project_id":str(project_id),"decision_type":kind,"decision_id":str(decision.get("id"))},
                )
            if approval["status"] != "APPROVED":
                return {"status":"WAITING_FOR_APPROVAL","approval":approval,"decision":decision}
            try:
                ApprovalService(self.db).consume(
                    approval["id"],
                    expected_action=action,
                    expected_context={"project_id":str(project_id),"decision_type":kind,"decision_id":str(decision.get("id"))},
                    actor="scientific-orchestrator",
                )
            except ApprovalRequired:
                return {"status":"WAITING_FOR_APPROVAL","approval":self.db.one("SELECT * FROM approvals WHERE id=?",(approval["id"],)),"decision":decision}
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
