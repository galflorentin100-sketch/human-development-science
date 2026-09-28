from uuid import uuid4
from app.models import now

VALID_CLASSIFICATIONS={"FACT","HYPOTHESIS","INTERPRETATION","OPINION"}
APPROVAL_REQUIRED={"WEAKENED","CONTRADICTED","RETIRED"}

class ClaimChangeService:
    def __init__(self,db): self.db=db
    def revise(self,claim_id,new_text,reason,actor="system",new_classification=None,new_confidence=None,evidence_id=None,review_required=True,change_type=None,correlation_id=None):
        revision_id=str(uuid4()); ts=now()
        with self.db.transaction() as con:
            old=con.execute("SELECT * FROM claims WHERE id=?",(claim_id,)).fetchone()
            if not old: raise ValueError("claim not found")
            old=dict(old)
            classification=new_classification or old["classification"]
            if classification not in VALID_CLASSIFICATIONS: raise ValueError("invalid claim classification")
            if classification=="FACT":
                if old["status"]!="SUPPORTED":
                    raise ValueError("FACT classification requires SUPPORTED claim state")
                from app.evidence_pipeline import EvidencePipeline
                evidence_state=EvidencePipeline(self.db).claim_evidence_state(claim_id)
                if evidence_state["verified_support"] < 1:
                    raise ValueError("FACT classification requires verified supporting evidence")
                if evidence_state["verified_contradict"] > 0 or evidence_state["conflicted"] > 0:
                    raise ValueError("FACT classification blocked while contradictory or conflicted evidence exists")
            confidence=old["confidence"] if new_confidence is None else float(new_confidence)
            if not 0.0<=confidence<=1.0: raise ValueError("confidence must be between 0 and 1")
            if evidence_id is not None:
                evidence=con.execute("SELECT * FROM evidence WHERE id=?",(evidence_id,)).fetchone()
                if not evidence: raise ValueError("evidence not found")
                if evidence["claim_id"]!=claim_id: raise ValueError("evidence does not belong to claim")
            approval_id=None
            if change_type in APPROVAL_REQUIRED:
                if not correlation_id: raise ValueError("correlation_id required for high-impact scientific claim changes")
                approval=con.execute("SELECT * FROM approvals WHERE correlation_id=? AND status='APPROVED' ORDER BY resolved_at DESC LIMIT 1",(correlation_id,)).fetchone()
                if not approval: raise ValueError("unexpired founder approval required")
                approval=dict(approval)
                if approval["action"] != "SCIENTIFIC_CLAIM_CHANGE":
                    raise ValueError("approval is not scoped to scientific claim changes")
                try:
                    approval_context=__import__("json").loads(approval["context"] or "{}")
                except (TypeError,ValueError):
                    raise ValueError("approval context is invalid")
                if str(approval_context.get("claim_id")) != str(claim_id):
                    raise ValueError("approval is scoped to a different claim")
                from datetime import datetime,timezone
                if approval["expires_at"] and datetime.fromisoformat(approval["expires_at"])<=datetime.now(timezone.utc):
                    raise ValueError("founder approval expired")
                consumed=con.execute(
                    "SELECT 1 FROM approval_events WHERE approval_id=? AND action='CONSUMED' LIMIT 1",
                    (approval["id"],)).fetchone()
                if consumed:
                    raise ValueError("scientific claim approval has already been consumed")
                approval_id=approval["id"]
            con.execute("INSERT INTO claim_revisions(id,claim_id,prior_classification,prior_confidence,new_classification,new_confidence,reason,evidence_id,review_required,created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                        (revision_id,claim_id,old["classification"],old["confidence"],classification,confidence,reason,evidence_id,int(review_required),ts))
            updated=con.execute("UPDATE claims SET statement=?,classification=?,confidence=?,updated_at=?,review_required=? WHERE id=?",
                                (new_text,classification,confidence,ts,int(review_required),claim_id))
            if updated.rowcount != 1:
                raise ValueError("claim changed concurrently")
            finding_id=str(uuid4())
            con.execute("INSERT INTO findings(id,project_id,claim_id,category,title,change_type,confidence,evidence_level,provenance,why_it_matters,recommended_action,review_required,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (finding_id,old["project_id"],claim_id,"SCIENTIFIC_CLAIM","Claim revision",change_type or "UPDATED",confidence,old["evidence_level"],
                         f"claim:{claim_id};revision:{revision_id}",reason,"Review updated claim against cited evidence",int(review_required),ts))
            if approval_id:
                con.execute("INSERT INTO approval_events(id,approval_id,actor,action,payload,created_at) VALUES (?,?,?,?,?,?)",
                            (str(uuid4()),approval_id,actor,"CONSUMED",
                             __import__("json").dumps({"claim_id":claim_id,"revision_id":revision_id,"change_type":change_type},sort_keys=True),ts))
            con.execute("INSERT INTO audit_logs(id,event_type,entity_type,entity_id,actor,payload,created_at) VALUES (?,?,?,?,?,?,?)",
                        (str(uuid4()),"scientific_claim.revised","claim",claim_id,actor,"{}",ts))
        return self.db.one("SELECT * FROM claims WHERE id=?",(claim_id,))
