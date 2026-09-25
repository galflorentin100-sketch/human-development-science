"""Gate for turning agent output into reviewable scientific material.

Agent output is never treated as evidence merely because an agent produced it.
"""
import hashlib, json
from uuid import uuid4
from app.models import now

class AgentOutputGate:
    def __init__(self,db): self.db=db

    def submit(self,agent_run_id,project_id=None):
        run=self.db.one("SELECT * FROM agent_runs WHERE id=?",(agent_run_id,))
        if not run: raise ValueError("agent run not found")
        payload=json.loads(run["output_payload"] or "{}")
        refs=payload.get("evidence_refs") or []
        if not isinstance(refs,list): refs=[]
        canonical=json.dumps(payload,sort_keys=True,separators=(",",":"))
        digest=hashlib.sha256(canonical.encode()).hexdigest()
        status="READY_FOR_REVIEW" if refs else "NEEDS_EVIDENCE"
        rid=str(uuid4())
        self.db.execute(
            "INSERT INTO agent_output_reviews(id,agent_run_id,project_id,task_id,evidence_refs,provenance_hash,status,created_at) VALUES (?,?,?,?,?,?,?,?)",
            (rid,agent_run_id,project_id,run["task_id"],json.dumps(refs),digest,status,now()))
        self.db.audit("scientific.agent_output_submitted","agent_output_review",rid,run["agent_id"],
                      {"agent_run_id":agent_run_id,"evidence_count":len(refs),"status":status},now(),str(uuid4()))
        return self.db.one("SELECT * FROM agent_output_reviews WHERE id=?",(rid,))

    def review(self,review_id,reviewer,decision,rationale):
        row=self.db.one("SELECT * FROM agent_output_reviews WHERE id=?",(review_id,))
        if not row: raise ValueError("output review not found")
        if not rationale or not str(rationale).strip(): raise ValueError("review rationale is required")
        decision=str(decision).upper()
        if decision not in {"ACCEPT","REJECT","NEEDS_EVIDENCE"}: raise ValueError("invalid review decision")
        status={"ACCEPT":"ACCEPTED","REJECT":"REJECTED","NEEDS_EVIDENCE":"NEEDS_EVIDENCE"}[decision]
        self.db.execute("UPDATE agent_output_reviews SET status=?,reviewer=?,rationale=?,reviewed_at=? WHERE id=? AND status='READY_FOR_REVIEW'",
                         (status,reviewer,rationale,now(),review_id))
        self.db.audit("scientific.agent_output_reviewed","agent_output_review",review_id,reviewer,
                      {"decision":decision},now(),str(uuid4()))
        return self.db.one("SELECT * FROM agent_output_reviews WHERE id=?",(review_id,))

    def get(self,review_id):
        return self.db.one("SELECT * FROM agent_output_reviews WHERE id=?",(review_id,))

    def list(self,project_id,status=None):
        sql="SELECT * FROM agent_output_reviews WHERE project_id=?"
        params=[project_id]
        if status:
            sql+=" AND status=?"; params.append(status)
        sql+=" ORDER BY created_at DESC"
        return self.db.all(sql,tuple(params))
