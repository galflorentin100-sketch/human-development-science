class IntelligenceService:
    def __init__(self,db): self.db=db
    def findings(self):
        rows=self.db.all("SELECT * FROM research_findings ORDER BY created_at DESC LIMIT 20")
        return [dict(r, scientific_state=self._finding_state(r)) for r in rows]

    def _finding_state(self,row):
        status=str(row.get("status") or "").upper()
        if status=="ACCEPTED":
            return "ACCEPTED_FINDING_REQUIRES_CLAIM_GOVERNANCE"
        if status=="CANDIDATE":
            return "CANDIDATE_REQUIRES_INDEPENDENT_REVIEW"
        if status=="REJECTED":
            return "REJECTED_NOT_SCIENTIFIC_KNOWLEDGE"
        return f"UNRESOLVED_{status or 'UNKNOWN'}"

    def scientific_state(self,project_id=None):
        params=() if project_id is None else (project_id,)
        scope="" if project_id is None else " WHERE c.project_id=?"
        claims=self.db.all(
            "SELECT c.id,c.project_id,c.statement,c.status,c.evidence_level,c.confidence "
            "FROM claims c"+scope+" ORDER BY c.updated_at DESC LIMIT 100",params)
        return {
            "accepted_claims":[dict(r,scientific_state="SUPPORTED_ACTIVE_CANDIDATE_FOR_KNOWLEDGE") for r in claims if str(r["status"]).upper()=="SUPPORTED"],
            "claims_requiring_review":[dict(r,scientific_state="NOT_ACTIVE_KNOWLEDGE") for r in claims if str(r["status"]).upper()!="SUPPORTED"],
            "policy":"Only scientifically admitted SUPPORTED claims may enter active knowledge; all other claim states are explicitly non-active.",
        }

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
