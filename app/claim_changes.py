from uuid import uuid4
from app.models import now
class ClaimChangeService:
    def __init__(self,db): self.db=db
    def revise(self,claim_id,new_text,reason,actor="system",new_classification=None,new_confidence=None,evidence_id=None,review_required=True):
        old=self.db.one("SELECT * FROM claims WHERE id=?",(claim_id,))
        if not old: raise ValueError("claim not found")
        classification=new_classification or old["classification"]
        confidence=old["confidence"] if new_confidence is None else float(new_confidence)
        revision_id=str(uuid4())
        self.db.execute("INSERT INTO claim_revisions(id,claim_id,prior_classification,prior_confidence,new_classification,new_confidence,reason,evidence_id,review_required,created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",(revision_id,claim_id,old["classification"],old["confidence"],classification,confidence,reason,evidence_id,int(review_required),now()))
        self.db.execute("UPDATE claims SET statement=?,classification=?,confidence=?,updated_at=?,review_required=? WHERE id=?",(new_text,classification,confidence,now(),int(review_required),claim_id))
        return self.db.one("SELECT * FROM claims WHERE id=?",(claim_id,))
