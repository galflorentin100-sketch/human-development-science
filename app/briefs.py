class FounderBriefService:
    def __init__(self,db): self.db=db
    def build(self):
        blocked=self.db.one("SELECT COUNT(*) AS n FROM tasks WHERE status='BLOCKED'")["n"]
        failed=self.db.one("SELECT COUNT(*) AS n FROM tasks WHERE status='FAILED' AND escalation_required=1")["n"]
        approvals=self.db.one("SELECT COUNT(*) AS n FROM approvals WHERE status='PENDING'")["n"]
        n=blocked+failed+approvals
        return {"founder_action_required":n,"content":"NO FOUNDER ACTION REQUIRED" if n==0 else f"FOUNDER ACTION REQUIRED: {n}","blocked_tasks":blocked,"failed_tasks":failed,"pending_approvals":approvals}
