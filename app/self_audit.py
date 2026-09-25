"""Self-audit engine for HDS.

The audit identifies gaps and risks; it never silently changes scientific truth.
Findings are diagnostics that require review.
"""
from datetime import datetime, timezone
import uuid

def _now():
    return datetime.now(timezone.utc).isoformat()

class SelfAuditEngine:
    def __init__(self, db):
        self.db=db

    def run(self):
        findings=[]
        checks=[
            ("CLAIMS_WITHOUT_EVIDENCE",
             "SELECT id FROM claims WHERE status IN ('SUPPORTED','CONTRADICTED') AND id NOT IN (SELECT claim_id FROM evidence)",
             "Claim has a decisive status but no linked evidence."),
            ("UNRESOLVED_EVIDENCE",
             "SELECT id FROM evidence WHERE id NOT IN (SELECT evidence_id FROM evidence_reviews)",
             "Evidence has not been independently reviewed."),
            ("TRAINING_WITHOUT_BASIS",
             "SELECT id FROM training_protocols WHERE status IN ('PILOT','SUPPORTED') AND source_claim_id IS NULL AND intervention_id IS NULL",
             "Training protocol has no explicit scientific basis link."),
            ("TRAINING_WITHOUT_TRANSFER",
             "SELECT id FROM training_protocols WHERE status='SUPPORTED' AND transfer_target=''",
             "Supported training protocol lacks a transfer target."),
            ("TRAINING_WITHOUT_RETENTION",
             "SELECT id FROM training_protocols WHERE status='SUPPORTED' AND retention_target=''",
             "Supported training protocol lacks a retention target."),
            ("ACTIVE_IMPROVEMENTS_WITHOUT_BASELINE",
             "SELECT id FROM improvement_proposals WHERE status='EXPERIMENT' AND (baseline_note IS NULL OR baseline_note='')",
             "Active improvement experiment has no recorded baseline."),
            ("INCONCLUSIVE_IMPROVEMENTS",
             "SELECT id FROM improvement_proposals WHERE experiment_result='INCONCLUSIVE'",
             "An organizational experiment remains inconclusive and may need a follow-up decision.")
        ]
        for kind,sql,message in checks:
            for row in self.db.all(sql):
                findings.append({"id":str(uuid.uuid4()),"kind":kind,"entity_id":row["id"],"severity":"HIGH" if "WITHOUT_EVIDENCE" in kind or "UNRESOLVED" in kind else "MEDIUM","message":message})
        return {"run_at":_now(),"finding_count":len(findings),"findings":findings}
