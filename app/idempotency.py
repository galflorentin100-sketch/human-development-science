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
        lock=self._lock_for(key)
        with lock:
            row=self.db.one("SELECT * FROM idempotency_keys WHERE key=?",(key,))
            if row:
                if row["actor"]!=actor or row["operation"]!=operation:
                    raise IdempotencyConflict("key already used by another actor or operation")
                if row["expires_at"] and datetime.fromisoformat(row["expires_at"]) <= datetime.now(timezone.utc):
                    self.db.execute("DELETE FROM idempotency_keys WHERE key=?",(key,))
                else:
                    return json.loads(row["response"])
            result=fn()
            now=datetime.now(timezone.utc)
            expires=(now+timedelta(hours=ttl_hours)).isoformat()
            try:
                self.db.execute("INSERT INTO idempotency_keys(key,actor,operation,response,created_at,expires_at) VALUES (?,?,?,?,?,?)",(key,actor,operation,json.dumps(result),now.isoformat(),expires))
            except Exception:
                existing=self.db.one("SELECT * FROM idempotency_keys WHERE key=?",(key,))
                if existing and existing["actor"]==actor and existing["operation"]==operation:
                    return json.loads(existing["response"])
                raise
        return result
