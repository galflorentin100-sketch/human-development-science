from enum import Enum
from uuid import uuid4
from app.models import now
class ApprovalStatus(str,Enum): PENDING="PENDING"; APPROVED="APPROVED"; REJECTED="REJECTED"; EXPIRED="EXPIRED"; CANCELLED="CANCELLED"
class ApprovalRequired(Exception): pass
class ApprovalService:
    def __init__(self,db): self.db=db
    def request(self,action,requested_by,reason=""):
        i=str(uuid4()); self.db.execute("INSERT INTO approvals(id,company_id,action,requested_by,status,reason,created_at) VALUES (?, 'hds', ?, ?, 'PENDING', ?, ?)",(i,action,requested_by,reason,now())); return self.db.one("SELECT * FROM approvals WHERE id=?",(i,))
    def get(self,i): return self.db.one("SELECT * FROM approvals WHERE id=?",(i,))
    def resolve(self,i,status,actor):
        self.db.execute("UPDATE approvals SET status=?,resolved_by=?,resolved_at=? WHERE id=?",(status.value if isinstance(status,ApprovalStatus) else status,actor,now(),i)); return self.get(i)
    def require(self,i): 
        if (r:=self.get(i)) is None or r["status"]!="APPROVED": raise ApprovalRequired(i)
