"""Human-reviewed claim revision with immutable history."""
import json
from uuid import uuid4
from app.models import now

class ClaimRevisionService:
    def __init__(self, db):
        self.db=db
        self._ensure()

    def _ensure(self):
        self.db.execute("""CREATE TABLE IF NOT EXISTS claim_revisions (
            id TEXT PRIMARY KEY, claim_id TEXT NOT NULL,
            previous_statement TEXT NOT NULL DEFAULT '', new_statement TEXT NOT NULL DEFAULT '',
            previous_status TEXT NOT NULL DEFAULT 'PROPOSED', new_status TEXT NOT NULL DEFAULT 'PROPOSED',
            rationale TEXT NOT NULL DEFAULT '', evidence_refs TEXT NOT NULL DEFAULT '[]',
            revised_by TEXT NOT NULL DEFAULT 'system', status TEXT NOT NULL DEFAULT 'PROPOSED',
            created_at TEXT NOT NULL
        )""")
        existing={r["name"] for r in self.db.all("PRAGMA table_info(claim_revisions)")}
        additions={"previous_statement":"TEXT NOT NULL DEFAULT ''","new_statement":"TEXT NOT NULL DEFAULT ''","previous_status":"TEXT NOT NULL DEFAULT 'PROPOSED'","new_status":"TEXT NOT NULL DEFAULT 'PROPOSED'","rationale":"TEXT NOT NULL DEFAULT ''","evidence_refs":"TEXT NOT NULL DEFAULT '[]'","revised_by":"TEXT NOT NULL DEFAULT 'system'","status":"TEXT NOT NULL DEFAULT 'PROPOSED'"}
        for name,definition in additions.items():
            if name not in existing: self.db.execute(f"ALTER TABLE claim_revisions ADD COLUMN {name} {definition}")

    def propose(self, claim_id, new_statement, new_status, rationale, evidence_refs=(), actor="system"):
        claim=self.db.one("SELECT * FROM claims WHERE id=?",(claim_id,))
        if not claim: raise ValueError("claim not found")
        if not str(new_statement or "").strip() or not str(rationale or "").strip():
            raise ValueError("new statement and rationale are required")
        if new_status not in {"PROPOSED","UNCERTAIN","SUPPORTED","RETIRED"}:
            raise ValueError("invalid claim status")
        i=str(uuid4())
        refs=list(evidence_refs); evidence_id=str(refs[0]) if refs else None
        self.db.execute("""INSERT INTO claim_revisions
            (id,claim_id,prior_classification,prior_confidence,new_classification,new_confidence,
             reason,evidence_id,review_required,previous_statement,new_statement,previous_status,
             new_status,rationale,evidence_refs,revised_by,status,created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (i,claim_id,claim.get("classification",""),claim.get("confidence",0.0),
             claim.get("classification",""),claim.get("confidence",0.0),rationale,evidence_id,1,
             claim["statement"],new_statement,claim["status"],new_status,rationale,
             json.dumps(refs,sort_keys=True),actor,"PROPOSED",now()))
        return self.db.one("SELECT * FROM claim_revisions WHERE id=?",(i,))

    def approve(self, revision_id, reviewer):
        rev=self.db.one("SELECT * FROM claim_revisions WHERE id=?",(revision_id,))
        if not rev: raise ValueError("revision not found")
        if rev.get("status","PROPOSED")!="PROPOSED": raise ValueError("revision is no longer pending")
        if not str(reviewer or "").strip(): raise ValueError("reviewer is required")
        if rev["revised_by"]==reviewer and reviewer!="system":
            raise ValueError("revision requires an independent reviewer")
        with self.db.transaction() as con:
            current=con.execute("SELECT * FROM claims WHERE id=?",(rev["claim_id"],)).fetchone()
            if not current: raise ValueError("claim not found")
            if current["statement"]!=rev["previous_statement"] or current["status"]!=rev["previous_status"]:
                raise ValueError("claim changed since revision was proposed")
            con.execute("UPDATE claims SET statement=?,status=?,updated_at=? WHERE id=?",
                        (rev["new_statement"],rev["new_status"],now(),rev["claim_id"]))
            con.execute("UPDATE claim_revisions SET status='APPROVED' WHERE id=?",(revision_id,))
            con.execute(
                "INSERT INTO audit_logs(id,event_type,entity_type,entity_id,actor,payload,created_at) VALUES (?,?,?,?,?,?,?)",
                (str(uuid4()),"claim.revised","claim",rev["claim_id"],reviewer,
                 json.dumps({"revision_id":revision_id,"rationale":rev["rationale"],
                             "evidence_refs":json.loads(rev["evidence_refs"] or "[]")},sort_keys=True),now()))
        return self.db.one("SELECT * FROM claims WHERE id=?",(rev["claim_id"],))

    def history(self, claim_id):
        return self.db.all("SELECT * FROM claim_revisions WHERE claim_id=? ORDER BY created_at",(claim_id,))
