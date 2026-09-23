class IntelligenceService:
    def __init__(self,db): self.db=db
    def findings(self):
        return self.db.all("SELECT * FROM findings ORDER BY created_at DESC LIMIT 20")
    def timeline(self): return self.db.all("SELECT event,entity_type,entity_id,actor,created_at FROM audit_logs ORDER BY created_at DESC LIMIT 30")
    def workforce(self): return self.db.all("SELECT status,COUNT(*) count FROM agents GROUP BY status")
    def health(self):
        return {"agents":self.db.one("SELECT COUNT(*) n FROM agents")["n"],"open_risks":self.db.one("SELECT COUNT(*) n FROM risks WHERE status='OPEN'")["n"],"pending_approvals":self.db.one("SELECT COUNT(*) n FROM approvals WHERE status='PENDING'")["n"]}
