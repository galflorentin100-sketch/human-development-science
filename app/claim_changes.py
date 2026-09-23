from uuid import uuid4
from app.models import now
class ClaimChangeService:
    def __init__(self,db): self.db=db
    def revise(self,claim_id,new_text,reason,actor="system"):
        old=self.db.one("SELECT * FROM claims WHERE id=?",(claim_id,))
        if not old: raise ValueError("claim not found")
        self.db.execute("INSERT INTO claim_revisions(id,claim_id,old_text,new_text,reason,created_at,created_by) VALUES (?,?,?,?,?,?,?)",(str(uuid4()),claim_id,old["text"],new_text,reason,now(),actor))
        self.db.execute("UPDATE claims SET text=?,updated_at=? WHERE id=?",(new_text,now(),claim_id)); return self.db.one("SELECT * FROM claims WHERE id=?",(claim_id,))
