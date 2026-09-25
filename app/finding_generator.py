"""Generate reviewable findings from observed analysis outputs.

Generated findings are always candidates and are never silently promoted to FACT.
"""
import json
from app.research_findings import ResearchFindingService

class FindingGenerator:
    def __init__(self, db):
        self.db=db

    def from_training_outcomes(self, project_id, protocol_id):
        from app.training_outcomes import TrainingOutcomeAnalyzer
        analyzer=TrainingOutcomeAnalyzer(self.db)
        summary=analyzer.summarize(protocol_id)
        if summary.get("session_count",0)==0:
            return []
        changes=[]
        for metric in ("task_success","transfer_score","retention_score"):
            try:
                change=analyzer.change(protocol_id,metric)
            except (KeyError,ValueError):
                continue
            if change.get("n",0)>=2:
                changes.append((metric,change))
        if not changes:
            return []
        refs=[]
        rows=self.db.all(
            "SELECT evidence_ref FROM training_protocol_evidence WHERE protocol_id=?",
            (protocol_id,))
        refs.extend(str(r["evidence_ref"]) for r in rows if r["evidence_ref"])
        statement="Observed training-session outcome changes were detected; the direction and magnitude are descriptive and require review."
        detail={"protocol_id":protocol_id,"changes":changes}
        finding=ResearchFindingService(self.db).create(
            project_id,statement,classification="INFERENCE",
            source_type="MEASUREMENT",source_id=protocol_id,
            evidence_refs=refs,interpretation=json.dumps(detail,sort_keys=True),
            created_by="finding-generator")
        return [finding]
