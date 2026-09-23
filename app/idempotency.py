import json
from datetime import datetime, timezone, timedelta
class IdempotencyConflict(Exception): pass
class IdempotencyService:
    def __init__(self,db): self.db=db
    def run(self,key,actor,operation,fn,ttl_hours=24):
        if not key: return fn()
        row=self.db.one("SELECT * FROM idempotency_keys WHERE key=?",(key,))
        if row:
            if row["actor"]!=actor or row["operation"]!=operation:
                raise IdempotencyConflict("key already used by another actor or operation")
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
