"""Integration contract for HDS scientific integrity.

This module exposes a single read-only system status surface for operators/tests.
"""
class ScientificSystemStatus:
    def __init__(self,db): self.db=db
    def snapshot(self):
        def count(q): return int(self.db.one(q)["n"])
        return {
          "claims":count("SELECT COUNT(*) n FROM claims"),
          "supported_claims":count("SELECT COUNT(*) n FROM claims WHERE status='SUPPORTED'"),
          "uncertain_claims":count("SELECT COUNT(*) n FROM claims WHERE status='UNCERTAIN'"),
          "unreviewed_evidence":count("SELECT COUNT(*) n FROM evidence e WHERE NOT EXISTS (SELECT 1 FROM evidence_reviews r WHERE r.evidence_id=e.id)"),
          "training_protocols":count("SELECT COUNT(*) n FROM training_protocols"),
          "supported_training_protocols":count("SELECT COUNT(*) n FROM training_protocols WHERE status='SUPPORTED'"),
          "open_improvements":count("SELECT COUNT(*) n FROM improvement_proposals WHERE status IN ('PROPOSED','EXPERIMENT')"),
          "open_decisions":count("SELECT COUNT(*) n FROM organizational_decisions WHERE status='OPEN'"),
          "policy":"descriptive system health only; counts do not establish scientific efficacy"
        }
