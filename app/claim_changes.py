from uuid import uuid4
from app.models import now

VALID_CLASSIFICATIONS={"FACT","HYPOTHESIS","INTERPRETATION","OPINION"}
APPROVAL_REQUIRED={"WEAKENED","CONTRADICTED","RETIRED"}

class ClaimChangeService:
    def __init__(self,db): self.db=db
    def revise(self,claim_id,new_text,reason,actor="system",new_classification=None,new_confidence=None,evidence_id=None,review_required=True,change_type=None,correlation_id=None):
        old=self.db.one("SELECT * FROM claims WHERE id=?",(claim_id,))
        if not old: raise ValueError("claim not found")
        classification=new_classification or old["classification"]
        if classification not in VALID_CLASSIFICATIONS: raise ValueError("invalid claim classification")
        if classification=="FACT":
            if old["status"]!="SUPPORTED":
                raise ValueError("FACT classification requires SUPPORTED claim state")
            verified=self.db.one("SELECT 1 FROM evidence WHERE claim_id=? AND verified=1",(claim_id,))
            if not verified:
                raise ValueError("FACT classification requires verified evidence")
        confidence=old["confidence"] if new_confidence is None else float(new_confidence)
        if not 0.0<=confidence<=1.0: raise ValueError("confidence must be between 0 and 1")
        if evidence_id is not None:
            evidence=self.db.one("SELECT * FROM evidence WHERE id=?",(evidence_id,))
            if not evidence: raise ValueError("evidence not found")
            if evidence["claim_id"]!=claim_id: raise ValueError("evidence does not belong to claim")
        if change_type in APPROVAL_REQUIRED:
            if not correlation_id: raise ValueError("correlation_id required for high-impact scientific claim changes")
            approval=self.db.one("SELECT * FROM approvals WHERE correlation_id=? AND status='APPROVED' ORDER BY resolved_at DESC LIMIT 1",(correlation_id,))
            if not approval: raise ValueError("unexpired founder approval required")
            if approval["action"] != "SCIENTIFIC_CLAIM_CHANGE":
                raise ValueError("approval is not scoped to scientific claim changes")
            from datetime import datetime,timezone
            if approval["expires_at"] and datetime.fromisoformat(approval["expires_at"])<=datetime.now(timezone.utc): raise ValueError("founder approval expired")
        revision_id=str(uuid4()); ts=now()
        with self.db.transaction() as con:
            con.execute("INSERT INTO claim_revisions(id,claim_id,prior_classification,prior_confidence,new_classification,new_confidence,reason,evidence_id,review_required,created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",(revision_id,claim_id,old["classification"],old["confidence"],classification,confidence,reason,evidence_id,int(review_required),ts))
            con.execute("UPDATE claims SET statement=?,classification=?,confidence=?,updated_at=?,review_required=? WHERE id=?",(new_text,classification,confidence,ts,int(review_required),claim_id))
            finding_id=str(uuid4())
            con.execute("INSERT INTO findings(id,project_id,claim_id,category,title,change_type,confidence,evidence_level,provenance,why_it_matters,recommended_action,review_required,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",(finding_id,old["project_id"],claim_id,"SCIENTIFIC_CLAIM","Claim revision",change_type or "UPDATED",confidence,old["evidence_level"],f"claim:{claim_id};revision:{revision_id}",reason,"Review updated claim against cited evidence",int(review_required),ts))
            con.execute("INSERT INTO audit_logs(id,event_type,entity_type,entity_id,actor,payload,created_at) VALUES (?,?,?,?,?,?,?)",(str(uuid4()),"scientific_claim.revised","claim",claim_id,actor,"{}",ts))
        return self.db.one("SELECT * FROM claims WHERE id=?",(claim_id,))
