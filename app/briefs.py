class FounderBriefService:
    def __init__(self,db): self.db=db
    def build(self):
        blocked=self.db.one("SELECT COUNT(*) n FROM tasks WHERE status='BLOCKED'")["n"]
        failures=self.db.one("SELECT COUNT(*) n FROM failures")["n"]
        approvals=self.db.one("SELECT COUNT(*) n FROM approvals WHERE status='PENDING'")["n"]
        n=blocked+failures+approvals
        return {"founder_action_required":n,"content":"NO FOUNDER ACTION REQUIRED" if n==0 else f"FOUNDER ACTION REQUIRED: {n}"}
