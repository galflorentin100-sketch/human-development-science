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
        if not str(action or "").strip() or not str(requested_by or "").strip(): raise ValueError("action and requested_by are required")
        if expires_hours <= 0: raise ValueError("expires_hours must be positive")
        if risk_level not in {"LOW","MEDIUM","HIGH","CRITICAL"}: raise ValueError("invalid risk_level")
        if correlation_id is None: correlation_id=str(uuid4())
        i=str(uuid4()); expires_at=(datetime.now(timezone.utc)+timedelta(hours=expires_hours)).isoformat(); ts=now()
        with self.db.transaction() as con:
            con.execute("INSERT OR IGNORE INTO companies(id,name,mission,vision,core_principle,created_at) VALUES (?,?,?,?,?,?)",("hds","Human Development Science","","","Truth before all; evidence over hype.",ts))
            con.execute("INSERT INTO approvals(id,company_id,action,risk_level,status,requested_by,context,reason,expires_at,correlation_id,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",(i,"hds",action,risk_level,"PENDING",requested_by,json.dumps(context or {}),reason,expires_at,correlation_id,ts))
        return self.get(i)
    def get(self,i): return self.db.one("SELECT * FROM approvals WHERE id=?",(i,))
    def resolve(self,i,status,actor):
        s=status.value if isinstance(status,ApprovalStatus) else status
        if not str(actor or "").strip(): raise ValueError("actor is required")
        if s not in {ApprovalStatus.APPROVED.value,ApprovalStatus.REJECTED.value,ApprovalStatus.CANCELLED.value}: raise ValueError("approval can only resolve to APPROVED, REJECTED, or CANCELLED")
        row=self.get(i)
        if row is None or row["status"]!="PENDING": raise ApprovalRequired(i)
        if row["expires_at"] and datetime.fromisoformat(row["expires_at"])<=datetime.now(timezone.utc):
            self._expire(row,actor); raise ApprovalRequired(i)
        resolved_at=now()
        event_id=str(uuid4())
        with self.db.transaction() as con:
            updated=con.execute("UPDATE approvals SET status=?,approved_by=?,resolved_at=? WHERE id=? AND status='PENDING'",(s,actor,resolved_at,i))
            if getattr(updated,"rowcount",1) != 1:
                raise ApprovalRequired(i)
            con.execute("INSERT INTO approval_events(id,approval_id,actor,action,payload,created_at) VALUES (?,?,?,?,?,?)",(event_id,i,actor,s,"{}",resolved_at))
        return self.get(i)
    def _expire(self,row,actor="system"):
        resolved_at=now()
        with self.db.transaction() as con:
            updated=con.execute("UPDATE approvals SET status=?,resolved_at=? WHERE id=? AND status='PENDING'",(ApprovalStatus.EXPIRED.value,resolved_at,row["id"]))
            if getattr(updated,"rowcount",1) != 1:
                return self.get(row["id"])
            con.execute("INSERT INTO approval_events(id,approval_id,actor,action,payload,created_at) VALUES (?,?,?,?,?,?)",(str(uuid4()),row["id"],actor,"EXPIRED","{}",resolved_at))
        return self.get(row["id"])
    def require(self,i,correlation_id=None):
        row=self.get(i)
        if row is None: raise ApprovalRequired(i)
        if row["status"]=="PENDING" and row["expires_at"] and datetime.fromisoformat(row["expires_at"])<=datetime.now(timezone.utc): self._expire(row); raise ApprovalRequired(i)
        if row["status"]!="APPROVED": raise ApprovalRequired(i)
        if row["expires_at"] and datetime.fromisoformat(row["expires_at"])<=datetime.now(timezone.utc): self._expire(row); raise ApprovalRequired(i)
        if correlation_id is not None and row.get("correlation_id")!=correlation_id: raise ApprovalRequired(i)
        return row
