import json
from datetime import datetime, timezone, timedelta
from threading import Lock
class IdempotencyConflict(Exception): pass
class IdempotencyService:
    _locks={}
    _locks_guard=Lock()
    def __init__(self,db): self.db=db
    @classmethod
    def _lock_for(cls,key):
        with cls._locks_guard:
            return cls._locks.setdefault(key,Lock())
    def run(self,key,actor,operation,fn,ttl_hours=24):
        if ttl_hours <= 0: raise ValueError("ttl_hours must be positive")
        if not key: return fn()
        now=datetime.now(timezone.utc)
        expires=(now+timedelta(hours=ttl_hours)).isoformat()
        claim_token=str(__import__("uuid").uuid4())
        lease_expires=(now+timedelta(minutes=min(30,max(1,ttl_hours*60)))).isoformat()
        with self.db.transaction() as con:
            cur=con.execute("SELECT * FROM idempotency_keys WHERE key=?",(key,))
            row=cur.fetchone()
            if row:
                data=dict(row) if hasattr(row,"keys") else dict(zip([d.name for d in cur.description],row))
                if data["actor"]!=actor or data["operation"]!=operation:
                    raise IdempotencyConflict("key already used by another actor or operation")
                if data.get("status")=="IN_PROGRESS":
                    if data.get("lease_expires_at") and datetime.fromisoformat(data["lease_expires_at"]) > now:
                        raise IdempotencyConflict("idempotency operation is already in progress")
                    con.execute("DELETE FROM idempotency_keys WHERE key=?",(key,))
                elif data["expires_at"] and datetime.fromisoformat(data["expires_at"]) > now:
                    return json.loads(data["response"])
                else:
                    con.execute("DELETE FROM idempotency_keys WHERE key=?",(key,))
            con.execute("INSERT INTO idempotency_keys(key,actor,operation,response,created_at,expires_at,status,claim_token,lease_expires_at) VALUES (?,?,?,?,?,?,?,?,?)",
                        (key,actor,operation,json.dumps({"status":"IN_PROGRESS"}),now.isoformat(),expires,"IN_PROGRESS",claim_token,lease_expires))
        try:
            result=fn()
        except Exception:
            with self.db.transaction() as con:
                con.execute("DELETE FROM idempotency_keys WHERE key=? AND claim_token=?",(key,claim_token))
            raise
        with self.db.transaction() as con:
            cur=con.execute("UPDATE idempotency_keys SET response=?,status='COMPLETED',lease_expires_at=NULL WHERE key=? AND claim_token=?",
                            (json.dumps(result),key,claim_token))
            if cur.rowcount != 1:
                raise IdempotencyConflict("idempotency claim was lost before completion")
        return result
