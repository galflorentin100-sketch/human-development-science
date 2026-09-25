from uuid import uuid4
from app.models import now

VALID_STATES={"DRAFT","PROPOSED","SUPPORTED","CONTRADICTED","UNCERTAIN","RETIRED"}
TERMINAL={"RETIRED"}

class ClaimStateService:
    def __init__(self,db): self.db=db

    def _evidence_summary(self,claim_id):
        rows=self.db.all("SELECT e.*,s.state AS source_state FROM evidence e JOIN sources s ON s.id=e.source_id WHERE e.claim_id=?",(claim_id,))
        verified_support=sum(1 for r in rows if r["verified"] and r["stance"]=="SUPPORTS")
        verified_contradict=sum(1 for r in rows if r["verified"] and r["stance"]=="CONTRADICTS")
        return verified_support,verified_contradict,rows

    def transition(self,claim_id,new_status,actor,rationale,evidence_id=None):
        claim=self.db.one("SELECT * FROM claims WHERE id=?",(claim_id,))
        if not claim: raise ValueError("claim not found")
        if new_status not in VALID_STATES: raise ValueError("invalid claim state")
        old=claim["status"] or "DRAFT"
        if old in TERMINAL: raise ValueError("retired claims cannot transition")
        if not rationale.strip(): raise ValueError("rationale is required")
        if evidence_id:
            ev=self.db.one("SELECT * FROM evidence WHERE id=? AND claim_id=?",(evidence_id,claim_id))
            if not ev: raise ValueError("evidence does not belong to claim")
        support,contradict,_=self._evidence_summary(claim_id)
        if new_status=="SUPPORTED":
            if support < 1 or evidence_id is None: raise ValueError("SUPPORTED requires verified supporting evidence")
            if contradict > 0: raise ValueError("conflicting verified evidence requires UNCERTAIN status")
        if new_status=="CONTRADICTED":
            if contradict < 1 or evidence_id is None: raise ValueError("CONTRADICTED requires verified contradicting evidence")
            if support > 0: raise ValueError("conflicting verified evidence requires UNCERTAIN status")
        ts=now(); tid=str(uuid4())
        with self.db.transaction() as con:
            con.execute("UPDATE claims SET status=?,updated_at=?,review_required=? WHERE id=?",(new_status,ts,1 if new_status in {"PROPOSED","UNCERTAIN"} else 0,claim_id))
            con.execute("INSERT INTO claim_state_transitions(id,claim_id,prior_status,new_status,actor,rationale,evidence_id,created_at) VALUES (?,?,?,?,?,?,?,?)",(tid,claim_id,old,new_status,actor,rationale,evidence_id,ts))
        return self.db.one("SELECT * FROM claims WHERE id=?",(claim_id,))

    def evidence_state(self,claim_id):
        support,contradict,rows=self._evidence_summary(claim_id)
        if support and contradict: state="CONFLICTED"
        elif support: state="SUPPORTED_EVIDENCE"
        elif contradict: state="CONTRADICTED_EVIDENCE"
        else: state="UNVERIFIED"
        return {"state":state,"verified_support":support,"verified_contradict":contradict,"evidence_count":len(rows)}
