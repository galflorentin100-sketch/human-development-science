from enum import Enum
from uuid import uuid4
from app.models import now
class ApprovalStatus(str,Enum): PENDING="PENDING"; APPROVED="APPROVED"; REJECTED="REJECTED"; EXPIRED="EXPIRED"; CANCELLED="CANCELLED"
class ApprovalRequired(Exception): pass
class ApprovalService:
    def __init__(self,db): self.db=db
    def request(self,action,requested_by,reason="",risk_level="MEDIUM",context=None):
        i=str(uuid4()); self.db.execute("INSERT INTO approvals(id,company_id,action,risk_level,status,requested_by,context,created_at) VALUES (?,? ,? ,?,'PENDING',?,?,?)",(i,"hds",action,risk_level,requested_by,reason or "{}",now())); return self.get(i)
    def get(self,i): return self.db.one("SELECT * FROM approvals WHERE id=?",(i,))
    def resolve(self,i,status,actor):
        s=status.value if isinstance(status,ApprovalStatus) else status
        self.db.execute("UPDATE approvals SET status=?,approved_by=?,resolved_at=? WHERE id=?",(s,actor,now(),i))
        self.db.execute("INSERT INTO approval_events(id,approval_id,actor,action,payload,created_at) VALUES (?,?,?,?,?,?)",(str(uuid4()),i,actor,s,"{}",now()))
        return self.get(i)
    def require(self,i):
        row=self.get(i)
        if row is None or row["status"]!="APPROVED": raise ApprovalRequired(i)
