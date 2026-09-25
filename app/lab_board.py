"""Founder/Lab Board aggregation.

This is a read-only operational view. It does not promote claims or change state.
"""
class LabBoard:
    def __init__(self,db):
        self.db=db

    def snapshot(self):
        from app.self_audit import SelfAuditEngine
        audit=SelfAuditEngine(self.db).run()
        improvements=self.db.all("SELECT * FROM improvement_proposals ORDER BY created_at DESC LIMIT 20")
        decisions=self.db.all("SELECT * FROM organizational_decisions ORDER BY created_at DESC LIMIT 20")
        experiments=self.db.all("SELECT * FROM experiments ORDER BY created_at DESC LIMIT 20")
        claims=self.db.all("SELECT id,statement,classification,evidence_level,confidence,status,review_required,updated_at FROM claims ORDER BY created_at DESC LIMIT 30")
        training=self.db.all("SELECT id,name,status,evidence_level,source_claim_id,intervention_id,transfer_target,retention_target FROM training_protocols ORDER BY created_at DESC LIMIT 20")
        unknowns=self.db.all("SELECT id,question,status,created_at FROM research_questions WHERE status NOT IN ('RESOLVED','CLOSED') ORDER BY created_at DESC LIMIT 20")
        return {
            "audit":audit,
            "improvements":improvements,
            "decisions":decisions,
            "experiments":experiments,
            "claims":claims,
            "training_protocols":training,
            "open_questions":unknowns,
            "system_health":self._health(),
        }

    def _health(self):
        def count(sql):
            row=self.db.one(sql)
            return int(row["n"]) if row else 0
        return {
            "agents":count("SELECT COUNT(*) n FROM agents"),
            "active_projects":count("SELECT COUNT(*) n FROM projects WHERE status IN ('RUNNING','PLANNED')"),
            "open_risks":count("SELECT COUNT(*) n FROM risks WHERE status='OPEN'"),
            "pending_approvals":count("SELECT COUNT(*) n FROM approvals WHERE status='PENDING'"),
            "blocked_tasks":count("SELECT COUNT(*) n FROM tasks WHERE status='BLOCKED'"),
            "completed_tasks":count("SELECT COUNT(*) n FROM tasks WHERE status='COMPLETED'"),
            "failed_tasks":count("SELECT COUNT(*) n FROM tasks WHERE status='FAILED'"),
            "active_improvements":count("SELECT COUNT(*) n FROM improvement_proposals WHERE status='EXPERIMENT'"),
            "adopted_improvements":count("SELECT COUNT(*) n FROM improvement_proposals WHERE status='ADOPTED'"),
            "open_decisions":count("SELECT COUNT(*) n FROM organizational_decisions WHERE status='OPEN'"),
            "unreviewed_evidence":count("SELECT COUNT(*) n FROM evidence e WHERE e.id NOT IN (SELECT evidence_id FROM evidence_reviews)"),
            "supported_claims":count("SELECT COUNT(*) n FROM claims WHERE status='SUPPORTED'"),
            "uncertain_claims":count("SELECT COUNT(*) n FROM claims WHERE status='UNCERTAIN'"),
        }
