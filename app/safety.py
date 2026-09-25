"""Training safety gate. Conservative, explicit, auditable; never diagnoses or overrides a qualified human."""
from uuid import uuid4
from app.models import now

class SafetyGate:
    VALID={"CLEAR","CAUTION","STOP","REVIEW_REQUIRED"}
    def __init__(self,db): self.db=db
    def assess(self,protocol_id,participant_ref,checks):
        protocol=self.db.one("SELECT * FROM training_protocols WHERE id=?",(protocol_id,))
        if not protocol: raise ValueError("training protocol not found")
        if not str(protocol["safety_constraints"]).strip(): raise ValueError("protocol has no safety constraints")
        if not isinstance(checks,dict): raise ValueError("checks must be an object")
        status="CLEAR"
        for k,v in checks.items():
            if str(v).upper() in {"STOP","UNSAFE","ADVERSE_EVENT"}: status="STOP"
            elif str(v).upper() in {"CAUTION","UNKNOWN"} and status!="STOP": status="CAUTION"
        aid=str(uuid4())
        self.db.execute("INSERT INTO audit_logs(id,event_type,entity_type,entity_id,actor,payload,created_at) VALUES (?,?,?,?,?,?,?)",
            (aid,"training.safety_assessed","training_protocol",protocol_id,"system",__import__("json").dumps({"participant_ref":participant_ref,"status":status,"checks":checks},sort_keys=True),now()))
        return {"protocol_id":protocol_id,"participant_ref":participant_ref,"status":status,"checks":checks,
                "action":"STOP_AND_REVIEW" if status=="STOP" else ("CAUTION_AND_REVIEW" if status=="CAUTION" else "PROCEED_SUBJECT_TO_PROTOCOL")}
