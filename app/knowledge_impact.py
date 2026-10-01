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
        findings=self.db.all("""SELECT rf.* FROM research_findings rf
            WHERE rf.project_id=?
              AND EXISTS (
                  SELECT 1 FROM evidence e
                  WHERE e.claim_id=? AND instr(rf.evidence_refs, '"' || e.id || '"') > 0
              )""",(claim["project_id"],claim_id))
        interventions=[]
        if protocols:
            ids=[p["intervention_id"] for p in protocols if p["intervention_id"]]
            for i in ids: 
                row=self.db.one("SELECT * FROM interventions WHERE id=?",(i,))
                if row: interventions.append(row)
        evidence=self.db.all("SELECT id FROM evidence WHERE claim_id=?",(claim_id,))
        resolved=[EvidencePipeline(self.db).resolve(e["id"]) for e in evidence]
        conflict=any(x["state"]=="CONFLICTED" for x in resolved)
        versions=self.db.all("SELECT id FROM scientific_knowledge_versions WHERE claim_id=?",(claim_id,))
        return {
            "claim":claim,
            "evidence":resolved,
            "downstream":{
                "training_protocols":protocols,
                "interventions":interventions,
                "organizational_decisions":decisions,
                "research_findings":findings
            },
            "review_required": bool(protocols or interventions or decisions or findings or conflict or versions),
            "review_reasons": [
                *([ "evidence_conflict" ] if conflict else []),
                *([ "knowledge_version_exists" ] if versions else []),
                *([ "downstream_training_protocol" ] if protocols else []),
                *([ "downstream_intervention" ] if interventions else []),
                *([ "downstream_decision" ] if decisions else []),
                *([ "downstream_research_finding" ] if findings else []),
            ],
            "policy":"impact analysis is advisory; no automatic retirement or downgrade"
        }

    def contradiction_scan(self,project_id=None):
        if project_id is None:
            rows=self.db.all("SELECT id,statement,status FROM claims WHERE status IN ('SUPPORTED','CONTRADICTED')")
        else:
            rows=self.db.all("SELECT id,statement,status FROM claims WHERE project_id=? AND status IN ('SUPPORTED','CONTRADICTED')",(project_id,))
        findings=[]
        for c in rows:
            evidence=self.db.all("SELECT id FROM evidence WHERE claim_id=?",(c["id"],))
            states=[EvidencePipeline(self.db).resolve(e["id"])["state"] for e in evidence]
            if "CONFLICTED" in states or ("VERIFIED" in states and c["status"]=="CONTRADICTED"):
                findings.append({"claim_id":c["id"],"statement":c["statement"],"reason":"new or conflicting evidence may require review"})
        return {"claims_scanned":len(rows),"impacts":findings}
