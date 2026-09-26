"""Evidence audit for research synthesis.

The auditor checks only mechanical provenance constraints. Scientific validity
still requires human review.
"""
import json
from uuid import uuid4
from app.models import now

class ResearchEvidenceAuditor:
    def __init__(self,db): self.db=db

    def audit_synthesis(self,synthesis_id,reviewer="evidence-auditor"):
        syn=self.db.one("SELECT * FROM research_syntheses WHERE id=?",(synthesis_id,))
        if not syn: raise ValueError("synthesis not found")
        refs=json.loads(syn["evidence_refs"] or "[]")
        missing=[]; unverified=[]
        for ref in refs:
            ev=self.db.one("SELECT id,verified,state FROM evidence WHERE id=?",(str(ref),))
            if not ev: missing.append(str(ref))
            elif not ev["verified"] or ev["state"]!="VERIFIED": unverified.append(str(ref))
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
        self.db.audit("scientific.research_evidence_audit","research_synthesis",synthesis_id,reviewer,result,now(),str(uuid4()))
        return result
