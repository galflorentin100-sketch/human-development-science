from uuid import uuid4
from app.models import now
class ClaimChangeService:
    def __init__(self,db): self.db=db
    def revise(self,claim_id,new_text,reason,actor="system"):
        old=self.db.one("SELECT * FROM claims WHERE id=?",(claim_id,))
        if not old: raise ValueError("claim not found")
        old_text=old.get("statement",old.get("text"))
        self.db.execute("INSERT INTO claim_revisions(id,claim_id,prior_classification,prior_confidence,prior_evidence_level,change_reason,changed_by,changed_at) VALUES (?,?,?,?,?,?,?,?)",(str(uuid4()),claim_id,old.get("classification"),old.get("confidence"),old.get("evidence_level"),reason,actor,now()))
        self.db.execute("UPDATE claims SET statement=? WHERE id=?",(new_text,claim_id))
        return self.db.one("SELECT * FROM claims WHERE id=?",(claim_id,))
