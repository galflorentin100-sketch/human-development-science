from enum import Enum
import json
from uuid import uuid4
from app.models import now
from datetime import datetime, timezone, timedelta
class ApprovalStatus(str,Enum): PENDING="PENDING"; APPROVED="APPROVED"; REJECTED="REJECTED"; EXPIRED="EXPIRED"; CANCELLED="CANCELLED"
class ApprovalRequired(Exception): pass
class ApprovalService:
    def __init__(self,db): self.db=db
    def request(self,action,requested_by,reason="",risk_level="MEDIUM",context=None):
        i=str(uuid4())
        expires_at=(datetime.now(timezone.utc)+timedelta(hours=24)).isoformat()
        self.db.execute("INSERT INTO approvals(id,company_id,action,risk_level,status,requested_by,context,reason,expires_at,created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",(i,"hds",action,risk_level,"PENDING",requested_by,json.dumps(context or {}),reason,expires_at,now()))
        return self.get(i)
    def get(self,i): return self.db.one("SELECT * FROM approvals WHERE id=?",(i,))
    def resolve(self,i,status,actor):
        s=status.value if isinstance(status,ApprovalStatus) else status
        if s not in {x.value for x in ApprovalStatus}:
            raise ValueError("invalid approval status")
        row=self.get(i)
        if row is None:
            raise ApprovalRequired(i)
        if row["status"] != ApprovalStatus.PENDING.value:
            raise ApprovalRequired(i)
        if row["expires_at"] and datetime.fromisoformat(row["expires_at"]) <= datetime.now(timezone.utc):
            self.db.execute("UPDATE approvals SET status=?,resolved_at=? WHERE id=?",(ApprovalStatus.EXPIRED.value,now(),i))
            self.db.execute("INSERT INTO approval_events(id,approval_id,actor,action,payload,created_at) VALUES (?,?,?,?,?,?)",(str(uuid4()),i,actor,"EXPIRED","{}",now()))
            raise ApprovalRequired(i)
        self.db.execute("UPDATE approvals SET status=?,approved_by=?,resolved_at=? WHERE id=?",(s,actor,now(),i))
        self.db.execute("INSERT INTO approval_events(id,approval_id,actor,action,payload,created_at) VALUES (?,?,?,?,?,?)",(str(uuid4()),i,actor,s,"{}",now()))
        return self.get(i)
    def require(self,i):
        row=self.get(i)
        if row is None: raise ApprovalRequired(i)
        if row["status"]=="PENDING" and row["expires_at"] and datetime.fromisoformat(row["expires_at"]) <= datetime.now(timezone.utc):
            self.db.execute("UPDATE approvals SET status=?,resolved_at=? WHERE id=?",(ApprovalStatus.EXPIRED.value,now(),i))
            raise ApprovalRequired(i)
        if row["status"]!="APPROVED": raise ApprovalRequired(i)
        if row["expires_at"] and datetime.fromisoformat(row["expires_at"]) <= datetime.now(timezone.utc):
            self.db.execute("UPDATE approvals SET status=?,resolved_at=? WHERE id=?",(ApprovalStatus.EXPIRED.value,now(),i))
            raise ApprovalRequired(i)
        return row
