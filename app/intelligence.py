class IntelligenceService:
    def __init__(self,db): self.db=db
    def findings(self): return self.db.all("SELECT * FROM findings ORDER BY created_at DESC LIMIT 20")
    def timeline(self): return self.db.all("SELECT event_type,entity_type,entity_id,actor,created_at FROM audit_logs ORDER BY created_at DESC LIMIT 30")
    def workforce(self):
        return self.db.all("""SELECT a.id,a.name,a.role,a.status,a.manager,
          COUNT(r.id) AS run_count,COALESCE(AVG(r.confidence),0) AS confidence
          FROM agents a LEFT JOIN agent_runs r ON r.agent_id=a.id GROUP BY a.id ORDER BY a.id""")
    def health(self):
        return {"agents":self.db.one("SELECT COUNT(*) AS n FROM agents")["n"],
                "open_risks":self.db.one("SELECT COUNT(*) AS n FROM risks WHERE status='OPEN'")["n"],
                "pending_approvals":self.db.one("SELECT COUNT(*) AS n FROM approvals WHERE status='PENDING'")["n"],
                "blocked_tasks":self.db.one("SELECT COUNT(*) AS n FROM tasks WHERE status='BLOCKED'")["n"],
                "completed_tasks":self.db.one("SELECT COUNT(*) AS n FROM tasks WHERE status='COMPLETED'")["n"],
                "failed_tasks":self.db.one("SELECT COUNT(*) AS n FROM tasks WHERE status='FAILED'")["n"],
                "agent_runs":self.db.one("SELECT COUNT(*) AS n FROM agent_runs")["n"],
                "model_calls":self.db.one("SELECT COUNT(*) AS n FROM model_calls")["n"],
                "audit_events":self.db.one("SELECT COUNT(*) AS n FROM audit_logs")["n"]}
