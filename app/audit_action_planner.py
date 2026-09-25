"""Self-audit action generation.

Audit findings become proposed organizational work, never silent mutations.
"""
import uuid
from datetime import datetime, timezone

def _now():
    return datetime.now(timezone.utc).isoformat()

class AuditActionPlanner:
    def __init__(self,db):
        self.db=db

    def plan(self):
        from app.self_audit import SelfAuditEngine
        audit=SelfAuditEngine(self.db).run()
        actions=[]
        for finding in audit["findings"]:
            title=f"Resolve audit finding: {finding['kind']}"
            actions.append({
                "id":str(uuid.uuid4()),
                "title":title,
                "finding_id":finding["id"],
                "kind":finding["kind"],
                "entity_id":finding["entity_id"],
                "priority":"HIGH" if finding["severity"]=="HIGH" else "MEDIUM",
                "recommended_action":self._recommend(finding["kind"]),
                "status":"PROPOSED",
                "created_at":_now(),
            })
        return {"generated_at":_now(),"count":len(actions),"actions":actions}

    def _recommend(self,kind):
        mapping={
            "CLAIMS_WITHOUT_EVIDENCE":"Collect and review evidence before changing claim status.",
            "UNRESOLVED_EVIDENCE":"Assign an independent reviewer and resolve the evidence.",
            "TRAINING_WITHOUT_BASIS":"Link the protocol to an explicit claim or intervention.",
            "TRAINING_WITHOUT_TRANSFER":"Define and measure a preregistered transfer target.",
            "TRAINING_WITHOUT_RETENTION":"Define and measure a preregistered retention target.",
            "ACTIVE_IMPROVEMENTS_WITHOUT_BASELINE":"Stop adoption decisions until a baseline is recorded.",
            "INCONCLUSIVE_IMPROVEMENTS":"Design a follow-up experiment or explicitly retire the proposal.",
        }
        return mapping.get(kind,"Review the finding and define a measurable corrective action.")
