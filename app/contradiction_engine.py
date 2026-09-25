"""Evidence contradiction detection and review queue.

Detection is mechanical: it flags conflicting evidence states and related
claims. It never decides which source is correct.
"""
import json
from uuid import uuid4
from app.models import now

class ContradictionEngine:
    def __init__(self, db):
        self.db=db
        self._ensure()

    def _ensure(self):
        self.db.execute("""CREATE TABLE IF NOT EXISTS scientific_contradictions (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            claim_id TEXT,
            evidence_a TEXT NOT NULL,
            evidence_b TEXT NOT NULL,
            description TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'OPEN',
            resolution TEXT,
            resolved_by TEXT,
            created_at TEXT NOT NULL,
            resolved_at TEXT
        )""")

    def scan_claim(self, claim_id):
        claim=self.db.one("SELECT * FROM claims WHERE id=?",(claim_id,))
        if not claim: raise ValueError("claim not found")
        evidence=self.db.all("SELECT id FROM evidence WHERE claim_id=? ORDER BY id",(claim_id,))
        # The EvidencePipeline is authoritative for evidence state.
        from app.evidence_pipeline import EvidencePipeline
        ep=EvidencePipeline(self.db)
        resolved=[(r["id"],ep.resolve(r["id"])["state"]) for r in evidence]
        pairs=[]
        for i,(a,sa) in enumerate(resolved):
            for b,sb in resolved[i+1:]:
                if {sa,sb}=={"VERIFIED","CONFLICTED"}:
                    pairs.append((a,b,"one evidence item is VERIFIED while another is CONFLICTED"))
        created=[]
        for a,b,description in pairs:
            exists=self.db.one(
                "SELECT id FROM scientific_contradictions WHERE claim_id=? AND evidence_a=? AND evidence_b=? AND status='OPEN'",
                (claim_id,a,b))
            if exists: continue
            i=str(uuid4())
            self.db.execute("""INSERT INTO scientific_contradictions
                (id,project_id,claim_id,evidence_a,evidence_b,description,status,created_at)
                VALUES (?,?,?,?,?,?,?,?)""",
                (i,claim["project_id"],claim_id,a,b,description,"OPEN",now()))
            created.append(self.db.one("SELECT * FROM scientific_contradictions WHERE id=?",(i,)))
        return {"claim_id":claim_id,"contradictions":created,"states":resolved}

    def list(self, project_id, status="OPEN"):
        return self.db.all(
            "SELECT * FROM scientific_contradictions WHERE project_id=? AND status=? ORDER BY created_at DESC",
            (project_id,status))

    def resolve(self, contradiction_id, actor, resolution):
        if not str(actor or "").strip() or not str(resolution or "").strip():
            raise ValueError("actor and resolution are required")
        row=self.db.one("SELECT * FROM scientific_contradictions WHERE id=?",(contradiction_id,))
        if not row: raise ValueError("contradiction not found")
        if row["status"]!="OPEN": raise ValueError("contradiction is not open")
        ts=now()
        self.db.execute(
            "UPDATE scientific_contradictions SET status='RESOLVED',resolution=?,resolved_by=?,resolved_at=? WHERE id=?",
            (resolution,actor,ts,contradiction_id))
        self.db.execute(
            "INSERT INTO audit_logs(id,event_type,entity_type,entity_id,actor,payload,created_at) VALUES (?,?,?,?,?,?,?)",
            (str(uuid4()),"scientific_contradiction.resolved","scientific_contradiction",
             contradiction_id,actor,json.dumps({"resolution":resolution}),ts))
        return self.db.one("SELECT * FROM scientific_contradictions WHERE id=?",(contradiction_id,))
