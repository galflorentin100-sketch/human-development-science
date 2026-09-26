"""Deterministic experiment result analysis.

Describes recorded outcomes without claiming causal efficacy. Any scientific
finding remains a candidate until the existing finding review gate.
"""
import json
from uuid import uuid4
from app.models import now

class ExperimentAnalyzer:
    def __init__(self,db): self.db=db

    def analyze(self,experiment_id):
        exp=self.db.one("SELECT * FROM hds_experiments WHERE id=?",(experiment_id,))
        if not exp: raise ValueError("experiment not found")
        result=self.db.one("SELECT * FROM hds_experiment_results WHERE experiment_id=?",(experiment_id,))
        if not result: return {"experiment":exp,"result":None,"status":"NO_RESULT"}
        refs=json.loads(result["evidence_refs"] or "[]")
        verified=[]
        for ref in refs:
            ev=self.db.one("SELECT id,verified FROM evidence WHERE id=?",(str(ref),))
            verified.append(bool(ev and ev["verified"]))
        return {"experiment":exp,"result":result,"status":"RESULT_AVAILABLE","evidence_refs":refs,
                "verified_evidence_count":sum(verified),
                "evidence_complete":bool(refs) and all(verified),
                "interpretation_type":"DESCRIPTIVE",
                "causal_claim_supported":False}

    def candidate_finding(self,experiment_id,actor):
        a=self.analyze(experiment_id)
        if a["status"]=="NO_RESULT": raise ValueError("experiment has no result")
        if not a["evidence_complete"]: raise ValueError("experiment result requires complete verified evidence")
        from app.research import ResearchFindingService
        interpretation=json.dumps({
            "experiment_id":experiment_id,
            "outcome":a["result"]["outcome"],
            "interpretation":a["result"]["interpretation"],
            "analysis_type":"DESCRIPTIVE",
            "causal_claim_supported":False,
            "evidence_refs":a["evidence_refs"],
        },sort_keys=True)
        return ResearchFindingService(self.db).create(
            a["experiment"]["project_id"],
            a["result"]["outcome"],
            classification="INFERENCE",
            source_type="MEASUREMENT",
            source_id=experiment_id,
            evidence_refs=a["evidence_refs"],
            interpretation=interpretation,
            created_by=actor)
