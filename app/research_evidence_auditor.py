"""Evidence audit for research synthesis.

The auditor checks only mechanical provenance constraints. Scientific validity
still requires human review.
"""
import json
from uuid import uuid4
from app.models import now

class ResearchEvidenceAuditor:
    def __init__(self,db):
        self.db=db
        self.db.execute("CREATE TABLE IF NOT EXISTS research_evidence_audits (id TEXT PRIMARY KEY, synthesis_id TEXT NOT NULL, status TEXT NOT NULL, evidence_count INTEGER NOT NULL, missing_evidence TEXT NOT NULL, unverified_evidence TEXT NOT NULL, reviewer TEXT NOT NULL, created_at TEXT NOT NULL)")

    def audit_synthesis(self,synthesis_id,reviewer="evidence-auditor",record_audit=True):
        syn=self.db.one("SELECT * FROM research_syntheses WHERE id=?",(synthesis_id,))
        if not syn: raise ValueError("synthesis not found")
        refs=json.loads(syn["evidence_refs"] or "[]")
        missing=[]; unverified=[]
        for ref in refs:
            ev=self.db.one("SELECT id,verified FROM evidence WHERE id=?",(str(ref),))
            if not ev: missing.append(str(ref))
            else:
                from app.evidence_pipeline import EvidencePipeline
                state=EvidencePipeline(self.db).resolve(str(ref))
                if not ev["verified"] or state["state"]!="VERIFIED": unverified.append(str(ref))
        sources=self.db.all("SELECT source_id FROM research_workspace_sources WHERE workspace_id=?",(syn["workspace_id"],))
        source_ids={str(x["source_id"]) for x in sources}
        # Evidence refs are authoritative only when they resolve to existing evidence.
        result={
            "synthesis_id":synthesis_id,
            "evidence_count":len(refs),
            "missing_evidence":missing,
            "unverified_evidence":unverified,
            "workspace_source_count":len(source_ids),
            "status":"PASS" if refs and not missing and not unverified else "REVIEW_REQUIRED"
        }
        if record_audit:
            self.db.execute("INSERT INTO research_evidence_audits(id,synthesis_id,status,evidence_count,missing_evidence,unverified_evidence,reviewer,created_at) VALUES (?,?,?,?,?,?,?,?)",(str(uuid4()),synthesis_id,result["status"],result["evidence_count"],json.dumps(missing),json.dumps(unverified),reviewer,now()))
            self.db.audit("scientific.research_evidence_audit","research_synthesis",synthesis_id,reviewer,result,now(),str(uuid4()))
        return result
