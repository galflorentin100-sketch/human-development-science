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
        existing=set(self.db.table_columns("claim_revisions"))
        additions={"prior_classification":"TEXT NOT NULL DEFAULT ''","prior_confidence":"REAL NOT NULL DEFAULT 0","new_classification":"TEXT NOT NULL DEFAULT ''","new_confidence":"REAL NOT NULL DEFAULT 0","reason":"TEXT NOT NULL DEFAULT ''","evidence_id":"TEXT","review_required":"INTEGER NOT NULL DEFAULT 1","previous_statement":"TEXT NOT NULL DEFAULT ''","new_statement":"TEXT NOT NULL DEFAULT ''","previous_status":"TEXT NOT NULL DEFAULT 'PROPOSED'","new_status":"TEXT NOT NULL DEFAULT 'PROPOSED'","rationale":"TEXT NOT NULL DEFAULT ''","evidence_refs":"TEXT NOT NULL DEFAULT '[]'","revised_by":"TEXT NOT NULL DEFAULT 'system'","status":"TEXT NOT NULL DEFAULT 'PROPOSED'","source_finding_id":"TEXT"}
        for name,definition in additions.items():
            if name not in existing: self.db.execute(f"ALTER TABLE claim_revisions ADD COLUMN {name} {definition}")

    def propose(self, claim_id, new_statement, new_status, rationale, evidence_refs=(), actor="system", source_finding_id=None):
        claim=self.db.one("SELECT * FROM claims WHERE id=?",(claim_id,))
        if not claim: raise ValueError("claim not found")
        if not str(new_statement or "").strip() or not str(rationale or "").strip():
            raise ValueError("new statement and rationale are required")
        if new_status not in {"PROPOSED","UNCERTAIN","SUPPORTED","CONTRADICTED","RETIRED"}:
            raise ValueError("invalid claim status")
        i=str(uuid4())
        refs=list(evidence_refs or ()); evidence_id=str(refs[0]) if refs else None
        for ref in refs:
            ev=self.db.one("SELECT e.id,c.project_id,e.verified FROM evidence e JOIN claims c ON c.id=e.claim_id WHERE e.id=?",(str(ref),))
            if not ev: raise ValueError("claim revision evidence not found")
            if str(ev["project_id"])!=str(claim["project_id"]): raise ValueError("claim revision evidence belongs to another project")
        self.db.execute("""INSERT INTO claim_revisions
            (id,claim_id,prior_classification,prior_confidence,new_classification,new_confidence,
             reason,evidence_id,review_required,previous_statement,new_statement,previous_status,
             new_status,rationale,evidence_refs,revised_by,status,source_finding_id,created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (i,claim_id,claim.get("classification",""),claim.get("confidence",0.0),
             claim.get("classification",""),claim.get("confidence",0.0),rationale,evidence_id,1,
             claim["statement"],new_statement,claim["status"],new_status,rationale,
             json.dumps(refs,sort_keys=True),actor,"PROPOSED",source_finding_id,now()))
        return self.db.one("SELECT * FROM claim_revisions WHERE id=?",(i,))

    def approve(self, revision_id, reviewer):
        rev=self.db.one("SELECT * FROM claim_revisions WHERE id=?",(revision_id,))
        if not rev: raise ValueError("revision not found")
        if rev.get("status","PROPOSED")!="PROPOSED": raise ValueError("revision is no longer pending")
        if not str(reviewer or "").strip(): raise ValueError("reviewer is required")
        refs=json.loads(rev.get("evidence_refs") or "[]")
        claim_project=self.db.one("SELECT project_id FROM claims WHERE id=?",(rev["claim_id"],))
        if not claim_project: raise ValueError("claim not found")
        for ref in refs:
            ev=self.db.one("SELECT e.id,e.verified,c.project_id FROM evidence e JOIN claims c ON c.id=e.claim_id WHERE e.id=?",(str(ref),))
            if not ev or not ev["verified"]: raise ValueError("claim revision evidence must reference verified evidence")
            if str(ev["project_id"])!=str(claim_project["project_id"]): raise ValueError("claim revision evidence belongs to another project")
        evidence_snapshot=[{"evidence_id":str(x),"state_at_approval":"VERIFIED"} for x in refs]
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
                             "evidence_refs":json.loads(rev["evidence_refs"] or "[]"),"evidence_snapshot":evidence_snapshot},sort_keys=True),now()))
        updated=self.db.one("SELECT * FROM claims WHERE id=?",(rev["claim_id"],))
        if updated and updated.get("project_id"):
            from app.knowledge_graph import KnowledgeDependencyGraph
            from app.knowledge_impact_engine import KnowledgeImpactEngine
            KnowledgeDependencyGraph(self.db).sync_project(updated["project_id"], actor=reviewer)
            impact=KnowledgeImpactEngine(self.db).propagate(
                updated["project_id"],"claims",rev["claim_id"],
                reason=f"Approved claim revision {revision_id} may affect dependent knowledge.")
        return updated

    def history(self, claim_id):
        return self.db.all("SELECT * FROM claim_revisions WHERE claim_id=? ORDER BY created_at",(claim_id,))
