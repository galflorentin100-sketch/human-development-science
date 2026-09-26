"""Scientific knowledge freshness and dependency tracking.

Advisory only: stale knowledge is flagged for review, never silently downgraded.
"""
from datetime import datetime, timezone
from uuid import uuid4
from app.models import now

class KnowledgeFreshness:
    VALID_STATUSES={"ACTIVE","REVIEW_REQUIRED","REVALIDATED","RETIRED"}
    def __init__(self,db): self.db=db

    def _iso(self,s):
        if not s: return None
        try: return datetime.fromisoformat(str(s).replace("Z","+00:00"))
        except ValueError: return None

    def register(self,entity_type,entity_id,review_interval_days=90,owner="system",project_id=None):
        if entity_type not in {"CLAIM","INTERVENTION","TRAINING_PROTOCOL"}: raise ValueError("invalid entity_type")
        if int(review_interval_days)<1: raise ValueError("review interval must be positive")
        table={"CLAIM":"claims","INTERVENTION":"interventions","TRAINING_PROTOCOL":"training_protocols"}[entity_type]
        entity=self.db.one(f"SELECT * FROM {table} WHERE id=?",(entity_id,))
        if not entity: raise ValueError("entity not found")
        if project_id is not None and "project_id" in entity.keys() and str(entity.get("project_id")) != str(project_id):
            raise ValueError("entity belongs to another project")
        existing=self.db.one("SELECT * FROM knowledge_freshness WHERE entity_type=? AND entity_id=?",(entity_type,entity_id))
        if existing: return existing
        i=str(uuid4())
        self.db.execute("INSERT INTO knowledge_freshness(id,entity_type,entity_id,review_interval_days,last_validated_at,next_review_at,status,owner,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (i,entity_type,entity_id,int(review_interval_days),now(),now(),"ACTIVE",owner,now(),now()))
        return self.db.one("SELECT * FROM knowledge_freshness WHERE id=?",(i,))

    def validate(self,entity_type,entity_id,actor,rationale):
        row=self.db.one("SELECT * FROM knowledge_freshness WHERE entity_type=? AND entity_id=?",(entity_type,entity_id))
        if not row: raise ValueError("freshness record not found")
        if not str(rationale).strip(): raise ValueError("validation rationale is required")
        from datetime import timedelta
        t=datetime.now(timezone.utc)
        nxt=(t+timedelta(days=int(row["review_interval_days"]))).isoformat()
        self.db.execute("UPDATE knowledge_freshness SET last_validated_at=?,next_review_at=?,status='REVALIDATED',updated_at=? WHERE id=?",(t.isoformat(),nxt,t.isoformat(),row["id"]))
        self.db.execute("INSERT INTO audit_logs(id,event_type,entity_type,entity_id,actor,payload,created_at) VALUES (?,?,?,?,?,?,?)",
            (str(uuid4()),"knowledge.revalidated",entity_type.lower(),entity_id,actor,'{"rationale":'+__import__("json").dumps(rationale)+ '}',now()))
        return self.db.one("SELECT * FROM knowledge_freshness WHERE id=?",(row["id"],))

    def scan(self):
        rows=self.db.all("SELECT * FROM knowledge_freshness ORDER BY next_review_at")
        t=datetime.now(timezone.utc)
        stale=[]
        for r in rows:
            nxt=self._iso(r["next_review_at"])
            if nxt and nxt<=t:
                stale.append({"id":r["id"],"entity_type":r["entity_type"],"entity_id":r["entity_id"],"status":"REVIEW_REQUIRED","reason":"review interval elapsed","next_review_at":r["next_review_at"]})
        return {"checked":len(rows),"stale_count":len(stale),"stale":stale,"policy":"flag only; no automatic scientific downgrade"}
