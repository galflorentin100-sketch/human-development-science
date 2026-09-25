"""Dependency impact analysis for scientific knowledge changes.

This module is intentionally advisory: it identifies downstream records that may need review.
It never mutates claims, protocols, interventions or decisions automatically.
"""
from app.evidence_pipeline import EvidencePipeline

class KnowledgeImpactAnalyzer:
    def __init__(self,db): self.db=db

    def claim_impact(self,claim_id):
        claim=self.db.one("SELECT * FROM claims WHERE id=?",(claim_id,))
        if not claim: raise ValueError("claim not found")
        protocols=self.db.all("SELECT * FROM training_protocols WHERE source_claim_id=?",(claim_id,))
        decisions=self.db.all("SELECT * FROM organizational_decisions WHERE evidence LIKE ?",(f"%{claim_id}%",))
        findings=self.db.all("SELECT * FROM research_findings WHERE evidence_refs LIKE ?",(f"%{claim_id}%",))
        interventions=[]
        if protocols:
            ids=[p["intervention_id"] for p in protocols if p["intervention_id"]]
            for i in ids: 
                row=self.db.one("SELECT * FROM interventions WHERE id=?",(i,))
                if row: interventions.append(row)
        evidence=self.db.all("SELECT id FROM evidence WHERE claim_id=?",(claim_id,))
        resolved=[EvidencePipeline(self.db).resolve(e["id"]) for e in evidence]
        return {
            "claim":claim,
            "evidence":resolved,
            "downstream":{
                "training_protocols":protocols,
                "interventions":interventions,
                "organizational_decisions":decisions,
                "research_findings":findings
            },
            "review_required": bool(protocols or interventions or decisions),
            "policy":"impact analysis is advisory; no automatic retirement or downgrade"
        }

    def contradiction_scan(self):
        rows=self.db.all("SELECT id,statement,status FROM claims WHERE status IN ('SUPPORTED','CONTRADICTED')")
        findings=[]
        for c in rows:
            evidence=self.db.all("SELECT id FROM evidence WHERE claim_id=?",(c["id"],))
            states=[EvidencePipeline(self.db).resolve(e["id"])["state"] for e in evidence]
            if "CONFLICTED" in states or ("VERIFIED" in states and c["status"]=="CONTRADICTED"):
                findings.append({"claim_id":c["id"],"statement":c["statement"],"reason":"new or conflicting evidence may require review"})
        return {"claims_scanned":len(rows),"impacts":findings}
