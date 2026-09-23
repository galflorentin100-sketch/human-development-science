from __future__ import annotations
import json
from uuid import uuid4
from app.models import now
class DecisionEngine:
    HIGH_RISK={"PUBLISH","SPEND","DEPLOY","DELETE","CONTACT_EXTERNAL_PARTY"}
    def __init__(self,db): self.db=db
    def assess(self,project_id,decision,alternatives,evidence,assumptions,confidence,expected_outcome,owner="ceo",risk_level="MEDIUM"):
        confidence=float(confidence)
        missing=[]
        if not evidence: missing.append("no evidence supplied")
        if not alternatives: missing.append("no alternatives considered")
        if not expected_outcome: missing.append("no expected outcome")
        action_required=confidence<0.8 or bool(missing) or risk_level in ("HIGH","CRITICAL")
        if decision in self.HIGH_RISK: action_required=True
        did=str(uuid4())
        self.db.execute("INSERT INTO decisions(id,company_id,decision,alternatives,evidence,assumptions,confidence,expected_outcome,actual_outcome,owner,follow_up,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",(did,"hds",decision,json.dumps(alternatives),json.dumps(evidence),json.dumps(assumptions),confidence,expected_outcome,None,owner,"Resolve approval or gather missing evidence." if action_required else "Execute and measure outcome.",now()))
        approval=None
        if action_required:
            aid=str(uuid4())
            self.db.execute("INSERT INTO approvals(id,company_id,action,risk_level,status,requested_by,context,created_at) VALUES (?,?,?,?,?,?,?,?)",(aid,"hds","DECISION:"+did,risk_level,"PENDING",owner,json.dumps({"decision_id":did,"missing":missing}),now()))
            approval=self.db.one("SELECT * FROM approvals WHERE id=?",(aid,))
        self.db.audit("decision.assessed","decision",did,owner,{"confidence":confidence,"action_required":action_required,"missing":missing},now(),str(uuid4()))
        return {"decision":self.db.one("SELECT * FROM decisions WHERE id=?",(did,)),"approval":approval,"action_required":action_required,"missing":missing}
    def record_outcome(self,decision_id,actual_outcome):
        self.db.execute("UPDATE decisions SET actual_outcome=? WHERE id=?",(actual_outcome,decision_id))
        self.db.audit("decision.outcome","decision",decision_id,"system",{"actual_outcome":actual_outcome},now(),str(uuid4()))
        return self.db.one("SELECT * FROM decisions WHERE id=?",(decision_id,))
