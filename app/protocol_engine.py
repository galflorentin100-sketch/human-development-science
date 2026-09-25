"""Execution layer for training protocols; records what happened, never invents performance."""
class ProtocolEngine:
    def __init__(self,db): self.db=db
    def next_session(self,protocol_id,participant_ref):
        p=self.db.one("SELECT * FROM training_protocols WHERE id=?",(protocol_id,))
        if not p: raise ValueError("training protocol not found")
        rows=self.db.all("SELECT * FROM training_sessions WHERE protocol_id=? AND participant_ref=? ORDER BY session_number DESC LIMIT 1",(protocol_id,str(participant_ref)))
        last=rows[0] if rows else None
        n=(int(last["session_number"])+1) if last else 1
        return {"protocol_id":protocol_id,"participant_ref":str(participant_ref),"session_number":n,
                "dosage":p["dosage"],"progression_rule":p["progression_rule"],
                "safety_constraints":p["safety_constraints"],"prior_session":last,
                "policy":"follow preregistered progression; do not infer a load from missing data"}
    def record(self,protocol_id,participant_ref,session_number,load_note,adherence,**metrics):
        from app.training import TrainingProtocolService
        return TrainingProtocolService(self.db).session(protocol_id,participant_ref,session_number,load_note,adherence,**metrics)
