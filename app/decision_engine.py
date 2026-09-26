from __future__ import annotations
import json
from uuid import uuid4
from app.models import now
from app.approvals import ApprovalService
class DecisionEngine:
    HIGH_RISK={"PUBLISH","SPEND","DEPLOY","DELETE","CONTACT_EXTERNAL_PARTY"}
    def __init__(self,db): self.db=db
    def assess(self,project_id,decision,alternatives,evidence,assumptions,confidence,expected_outcome,owner="ceo",risk_level="MEDIUM"):
        confidence=float(confidence)
        if not 0.0<=confidence<=1.0: raise ValueError("confidence must be between 0 and 1")
        if risk_level not in {"LOW","MEDIUM","HIGH","CRITICAL"}: raise ValueError("invalid risk_level")
        missing=[]
        if not evidence: missing.append("no evidence supplied")
        if not alternatives: missing.append("no alternatives considered")
        if not expected_outcome: missing.append("no expected outcome")
        action_required=confidence<0.8 or bool(missing) or risk_level in ("HIGH","CRITICAL")
        if decision in self.HIGH_RISK: action_required=True
        did=str(uuid4()); ts=now()
        with self.db.transaction() as con:
            con.execute("INSERT INTO decisions(id,company_id,decision,alternatives,evidence,assumptions,confidence,expected_outcome,actual_outcome,owner,follow_up,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                        (did,"hds",decision,json.dumps(alternatives),json.dumps(evidence),json.dumps(assumptions),confidence,expected_outcome,None,owner,"Resolve approval or gather missing evidence." if action_required else "Execute and measure outcome.",ts))
            approval=None
            if action_required:
                approval=ApprovalService(self.db)._request_in_transaction(
                    con,
                    action="DECISION:"+did,
                    requested_by=owner,
                    reason="Decision requires approval because evidence/confidence/risk gates were not satisfied.",
                    risk_level=risk_level,
                    context={"decision_id":did,"missing":missing},
                )
            con.execute("INSERT INTO audit_logs(id,event_type,entity_type,entity_id,actor,payload,created_at) VALUES (?,?,?,?,?,?,?)",
                        (str(uuid4()),"decision.assessed","decision",did,owner,
                         json.dumps({"confidence":confidence,"action_required":action_required,"missing":missing},sort_keys=True),ts))
        return {"decision":self.db.one("SELECT * FROM decisions WHERE id=?",(did,)),"approval":approval,"action_required":action_required,"missing":missing}

    def record_outcome(self,decision_id,actual_outcome):
        self.db.execute("UPDATE decisions SET actual_outcome=? WHERE id=?",(actual_outcome,decision_id))
        self.db.audit("decision.outcome","decision",decision_id,"system",{"actual_outcome":actual_outcome},now(),str(uuid4()))
        return self.db.one("SELECT * FROM decisions WHERE id=?",(decision_id,))
