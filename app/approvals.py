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
        with self.db.transaction() as con:
            row=self._request_in_transaction(con,action,requested_by,reason,risk_level,context,correlation_id,expires_hours)
        return self.get(row["id"])

    def _request_in_transaction(self,con,action,requested_by,reason="",risk_level="MEDIUM",context=None,correlation_id=None,expires_hours=24):
        if not str(action or "").strip() or not str(requested_by or "").strip():
            raise ValueError("action and requested_by are required")
        if expires_hours <= 0:
            raise ValueError("expires_hours must be positive")
        if risk_level not in {"LOW","MEDIUM","HIGH","CRITICAL"}:
            raise ValueError("invalid risk_level")
        if correlation_id is None:
            correlation_id=str(uuid4())
        i=str(uuid4())
        expires_at=(datetime.now(timezone.utc)+timedelta(hours=expires_hours)).isoformat()
        ts=now()
        con.execute("INSERT INTO companies(id,name,mission,vision,core_principle,created_at) VALUES (?,?,?,?,?,?) ON CONFLICT(id) DO NOTHING",
                    ("hds","Human Development Science","","","Truth before all; evidence over hype.",ts))
        con.execute("INSERT INTO approvals(id,company_id,action,risk_level,status,requested_by,context,reason,expires_at,correlation_id,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    (i,"hds",action,risk_level,"PENDING",requested_by,json.dumps(context or {}),reason,expires_at,correlation_id,ts))
        return dict(con.execute("SELECT * FROM approvals WHERE id=?",(i,)).fetchone())
    def get(self,i): return self.db.one("SELECT * FROM approvals WHERE id=?",(i,))
    def resolve(self,i,status,actor):
        s=status.value if isinstance(status,ApprovalStatus) else status
        if not str(actor or "").strip(): raise ValueError("actor is required")
        if s not in {ApprovalStatus.APPROVED.value,ApprovalStatus.REJECTED.value,ApprovalStatus.CANCELLED.value}: raise ValueError("approval can only resolve to APPROVED, REJECTED, or CANCELLED")
        with self.db.transaction() as con:
            self._resolve_in_transaction(con,i,s,actor)
        return self.get(i)

    def _resolve_in_transaction(self,con,i,status,actor):
        """Resolve an approval and its audit event inside the caller's transaction."""
        row=con.execute("SELECT * FROM approvals WHERE id=?",(i,)).fetchone()
        if not row or dict(row)["status"]!="PENDING":
            raise ApprovalRequired(i)
        row=dict(row)
        if str(row.get("requested_by")) == str(actor):
            raise ApprovalRequired(i)
        if row["expires_at"] and datetime.fromisoformat(row["expires_at"])<=datetime.now(timezone.utc):
            resolved_at=now()
            updated=con.execute(
                "UPDATE approvals SET status=?,resolved_at=? WHERE id=? AND status='PENDING'",
                (ApprovalStatus.EXPIRED.value,resolved_at,i))
            if getattr(updated,"rowcount",1)==1:
                con.execute(
                    "INSERT INTO approval_events(id,approval_id,actor,action,payload,created_at) VALUES (?,?,?,?,?,?)",
                    (str(uuid4()),i,actor,"EXPIRED","{}",resolved_at))
            raise ApprovalRequired(i)
        resolved_at=now()
        updated=con.execute(
            "UPDATE approvals SET status=?,approved_by=?,resolved_at=? WHERE id=? AND status='PENDING'",
            (status,actor,resolved_at,i))
        if getattr(updated,"rowcount",1) != 1:
            raise ApprovalRequired(i)
        con.execute(
            "INSERT INTO approval_events(id,approval_id,actor,action,payload,created_at) VALUES (?,?,?,?,?,?)",
            (str(uuid4()),i,actor,status,"{}",resolved_at))
        return dict(con.execute("SELECT * FROM approvals WHERE id=?",(i,)).fetchone())

    def _expire(self,row,actor="system"):
        resolved_at=now()
        with self.db.transaction() as con:
            updated=con.execute("UPDATE approvals SET status=?,resolved_at=? WHERE id=? AND status='PENDING'",(ApprovalStatus.EXPIRED.value,resolved_at,row["id"]))
            if getattr(updated,"rowcount",1) != 1:
                return self.get(row["id"])
            con.execute("INSERT INTO approval_events(id,approval_id,actor,action,payload,created_at) VALUES (?,?,?,?,?,?)",(str(uuid4()),row["id"],actor,"EXPIRED","{}",resolved_at))
        return self.get(row["id"])
    def require(self,i,correlation_id=None,expected_action=None):
        row=self.get(i)
        if row is None: raise ApprovalRequired(i)
        if row["status"]=="PENDING" and row["expires_at"] and datetime.fromisoformat(row["expires_at"])<=datetime.now(timezone.utc): self._expire(row); raise ApprovalRequired(i)
        if row["status"]!="APPROVED": raise ApprovalRequired(i)
        if row["expires_at"] and datetime.fromisoformat(row["expires_at"])<=datetime.now(timezone.utc): self._expire(row); raise ApprovalRequired(i)
        if expected_action is not None and row.get("action")!=expected_action: raise ApprovalRequired(i)
        if correlation_id is not None and row.get("correlation_id")!=correlation_id: raise ApprovalRequired(i)
        return row

    def _consume_in_transaction(self,con,i,expected_action=None,expected_context=None,correlation_id=None,actor="system"):
        row=con.execute("SELECT * FROM approvals WHERE id=?",(i,)).fetchone()
        if not row: raise ApprovalRequired(i)
        row=dict(row)
        if row["status"]!="APPROVED": raise ApprovalRequired(i)
        if row["expires_at"] and datetime.fromisoformat(row["expires_at"])<=datetime.now(timezone.utc): raise ApprovalRequired(i)
        if expected_action is not None and row["action"]!=expected_action: raise ApprovalRequired(i)
        if correlation_id is not None and row.get("correlation_id")!=correlation_id: raise ApprovalRequired(i)
        stored=json.loads(row.get("context") or "{}")
        for key,value in (expected_context or {}).items():
            if str(stored.get(key))!=str(value): raise ApprovalRequired(i)
        used=con.execute("SELECT 1 FROM approval_events WHERE approval_id=? AND action='CONSUMED' LIMIT 1",(i,)).fetchone()
        if used: raise ApprovalRequired(i)
        ts=now()
        con.execute("INSERT INTO approval_events(id,approval_id,actor,action,payload,created_at) VALUES (?,?,?,?,?,?)",
                    (str(uuid4()),i,actor,"CONSUMED",json.dumps({"action":expected_action,"context":expected_context or {}},sort_keys=True),ts))
        return row

    def consume(self,i,expected_action=None,expected_context=None,correlation_id=None,actor="system"):
        with self.db.transaction() as con:
            return self._consume_in_transaction(con,i,expected_action,expected_context,correlation_id,actor)
