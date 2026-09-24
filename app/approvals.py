from enum import Enum
import json
from uuid import uuid4
from app.models import now
from datetime import datetime,timezone,timedelta
class ApprovalStatus(str,Enum): PENDING="PENDING"; APPROVED="APPROVED"; REJECTED="REJECTED"; EXPIRED="EXPIRED"; CANCELLED="CANCELLED"
class ApprovalRequired(Exception): pass
class ApprovalService:
    def __init__(self,db): self.db=db
    def request(self,action,requested_by,reason="",risk_level="MEDIUM",context=None,correlation_id=None,expires_hours=24):
        if not action or not requested_by: raise ValueError("action and requested_by are required")
        if correlation_id is None: correlation_id=str(uuid4())
        i=str(uuid4()); expires_at=(datetime.now(timezone.utc)+timedelta(hours=expires_hours)).isoformat()
        self.db.execute("INSERT INTO approvals(id,company_id,action,risk_level,status,requested_by,context,reason,expires_at,correlation_id,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",(i,"hds",action,risk_level,"PENDING",requested_by,json.dumps(context or {}),reason,expires_at,correlation_id,now()))
        return self.get(i)
    def get(self,i): return self.db.one("SELECT * FROM approvals WHERE id=?",(i,))
    def resolve(self,i,status,actor):
        s=status.value if isinstance(status,ApprovalStatus) else status
        if s not in {ApprovalStatus.APPROVED.value,ApprovalStatus.REJECTED.value,ApprovalStatus.CANCELLED.value}: raise ValueError("approval can only resolve to APPROVED, REJECTED, or CANCELLED")
        row=self.get(i)
        if row is None or row["status"]!="PENDING": raise ApprovalRequired(i)
        if row["expires_at"] and datetime.fromisoformat(row["expires_at"])<=datetime.now(timezone.utc):
            self._expire(row,actor); raise ApprovalRequired(i)
        self.db.execute("UPDATE approvals SET status=?,approved_by=?,resolved_at=? WHERE id=?",(s,actor,now(),i))
        self.db.execute("INSERT INTO approval_events(id,approval_id,actor,action,payload,created_at) VALUES (?,?,?,?,?,?)",(str(uuid4()),i,actor,s,"{}",now()))
        return self.get(i)
    def _expire(self,row,actor="system"):
        self.db.execute("UPDATE approvals SET status=?,resolved_at=? WHERE id=?",(ApprovalStatus.EXPIRED.value,now(),row["id"]))
        self.db.execute("INSERT INTO approval_events(id,approval_id,actor,action,payload,created_at) VALUES (?,?,?,?,?,?)",(str(uuid4()),row["id"],actor,"EXPIRED","{}",now()))
    def require(self,i,correlation_id=None):
        row=self.get(i)
        if row is None: raise ApprovalRequired(i)
        if row["status"]=="PENDING" and row["expires_at"] and datetime.fromisoformat(row["expires_at"])<=datetime.now(timezone.utc): self._expire(row); raise ApprovalRequired(i)
        if row["status"]!="APPROVED": raise ApprovalRequired(i)
        if row["expires_at"] and datetime.fromisoformat(row["expires_at"])<=datetime.now(timezone.utc): self._expire(row); raise ApprovalRequired(i)
        if correlation_id is not None and row.get("correlation_id")!=correlation_id: raise ApprovalRequired(i)
        return row
