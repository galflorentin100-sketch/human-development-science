class IntelligenceService:
    def __init__(self,db): self.db=db
    def findings(self): return self.db.all("SELECT * FROM research_findings ORDER BY created_at DESC LIMIT 20")
    def timeline(self): return self.db.all("SELECT event_type,entity_type,entity_id,actor,created_at FROM audit_logs ORDER BY created_at DESC LIMIT 30")
    def workforce(self):
        return self.db.all("""SELECT a.id,a.name,a.role,a.status,a.manager,
          COUNT(r.id) AS run_count,COALESCE(AVG(r.confidence),0) AS confidence
          FROM agents a LEFT JOIN agent_runs r ON r.agent_id=a.id GROUP BY a.id ORDER BY a.id""")
    def scientific_knowledge(self, project_id=None):
        where = " WHERE project_id=?" if project_id else ""
        args = (project_id,) if project_id else ()
        claims = self.db.all("SELECT status, COUNT(*) AS n FROM claims" + where + " GROUP BY status", args)
        freshness_where = " WHERE c.project_id=?" if project_id else ""
        freshness_args = (project_id,) if project_id else ()
        active = self.db.all(
            "SELECT kf.entity_type, kf.status, COUNT(*) AS n FROM knowledge_freshness kf "
            "JOIN claims c ON kf.entity_type='CLAIM' AND kf.entity_id=c.id"
            + freshness_where + " GROUP BY kf.entity_type, kf.status",
            freshness_args,
        )
        return {
            "claims_by_status": {str(r["status"]).upper(): r["n"] for r in claims},
            "knowledge_freshness_by_type_and_status": {
                f"{str(r['entity_type']).upper()}:{str(r['status']).upper()}": r["n"] for r in active
            },
            "interpretation": {
                "supported_claims_are_scientifically_admitted_only_when_the_admission_gate_passes": True,
                "candidate_and_proposed_claims_are_not_active_knowledge": True,
                "uncertain_and_contradicted_claims_are_not_active_knowledge": True,
            },
        }
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
