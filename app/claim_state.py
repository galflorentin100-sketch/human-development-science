from uuid import uuid4
from app.models import now

VALID_STATES={"DRAFT","PROPOSED","SUPPORTED","CONTRADICTED","UNCERTAIN","RETIRED"}
TERMINAL={"RETIRED"}
ALLOWED_TRANSITIONS={
    "DRAFT":{"PROPOSED","RETIRED"},
    "PROPOSED":{"SUPPORTED","CONTRADICTED","UNCERTAIN","RETIRED"},
    "SUPPORTED":{"UNCERTAIN","RETIRED"},
    "CONTRADICTED":{"UNCERTAIN","RETIRED"},
    "UNCERTAIN":{"SUPPORTED","CONTRADICTED","RETIRED"},
    "RETIRED":set(),
}

class ClaimStateService:
    def __init__(self,db): self.db=db

    def _evidence_summary(self,claim_id):
        from app.evidence_pipeline import EvidencePipeline
        rows=self.db.all("SELECT e.*,s.state AS source_state FROM evidence e JOIN sources s ON s.id=e.source_id WHERE e.claim_id=?",(claim_id,))
        resolved=[EvidencePipeline(self.db).resolve(r["id"]) for r in rows]
        verified_support=sum(1 for r in resolved if r["state"]=="VERIFIED" and r["stance"]=="SUPPORTS")
        verified_contradict=sum(1 for r in resolved if r["state"]=="VERIFIED" and r["stance"]=="CONTRADICTS")
        return verified_support,verified_contradict,resolved

    def transition(self,claim_id,new_status,actor,rationale,evidence_id=None):
        claim=self.db.one("SELECT * FROM claims WHERE id=?",(claim_id,))
        if not claim: raise ValueError("claim not found")
        if new_status not in VALID_STATES: raise ValueError("invalid claim state")
        old=claim["status"] or "DRAFT"
        if old in TERMINAL: raise ValueError("retired claims cannot transition")
        if new_status not in ALLOWED_TRANSITIONS.get(old,set()):
            raise ValueError(f"invalid claim transition: {old} -> {new_status}")
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

    def knowledge_version(self,claim_id,actor,rationale):
        claim=self.db.one("SELECT * FROM claims WHERE id=?",(claim_id,))
        if not claim: raise ValueError("claim not found")
        if not rationale or not rationale.strip(): raise ValueError("knowledge version rationale is required")
        from app.evidence_pipeline import EvidencePipeline
        state=EvidencePipeline(self.db).claim_evidence_state(claim_id)
        snapshot=__import__("hashlib").sha256(__import__("json").dumps(state,sort_keys=True,separators=(",",":")).encode()).hexdigest()
        latest=self.db.one("SELECT MAX(version) AS v FROM scientific_knowledge_versions WHERE claim_id=?",(claim_id,))
        version=int(latest["v"] or 0)+1
        self.db.execute("INSERT INTO scientific_knowledge_versions(id,claim_id,version,statement,classification,status,confidence,evidence_state,evidence_snapshot_hash,change_reason,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (str(uuid4()),claim_id,version,claim["statement"],claim["classification"],claim["status"],claim["confidence"],state["conflicted"] and "CONFLICTED" or state["verified_support"] and "SUPPORTED" or state["verified_contradict"] and "CONTRADICTED" or "UNVERIFIED",snapshot,rationale,now()))
        self.db.execute("INSERT INTO audit_logs(id,event_type,entity_type,entity_id,actor,payload,created_at) VALUES (?,?,?,?,?,?,?)",(str(uuid4()),"scientific_knowledge.versioned","claim",claim_id,actor,"version="+str(version),now()))
        return self.db.one("SELECT * FROM scientific_knowledge_versions WHERE claim_id=? AND version=?",(claim_id,version))

    def knowledge_history(self,claim_id):
        return self.db.all("SELECT * FROM scientific_knowledge_versions WHERE claim_id=? ORDER BY version",(claim_id,))

    def evidence_state(self,claim_id):
        from app.evidence_pipeline import EvidencePipeline
        state=EvidencePipeline(self.db).claim_evidence_state(claim_id)
        if state["conflicted"] or (state["verified_support"] and state["verified_contradict"]): label="CONFLICTED"
        elif state["verified_support"]: label="SUPPORTED_EVIDENCE"
        elif state["verified_contradict"]: label="CONTRADICTED_EVIDENCE"
        else: label="UNVERIFIED"
        return {"state":label,"verified_support":state["verified_support"],"verified_contradict":state["verified_contradict"],"conflicted":state["conflicted"],"evidence_count":len(state["evidence"])}
