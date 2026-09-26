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
        task=self.db.one("SELECT * FROM tasks WHERE id=?",(run["task_id"],))
        if not task: raise ValueError("agent run task not found")
        if project_id is not None and str(project_id)!=str(task["project_id"]):
            raise ValueError("project_id does not match task project")
        project_id=task["project_id"]
        existing=self.db.one("SELECT * FROM agent_output_reviews WHERE agent_run_id=? ORDER BY created_at DESC LIMIT 1",(agent_run_id,))
        if existing: return existing
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
        run=self.db.one("SELECT * FROM agent_runs WHERE id=?",(row["agent_run_id"],))
        if not run: raise ValueError("agent run not found")
        try: refs=json.loads(row["evidence_refs"] or "[]")
        except (TypeError,ValueError): refs=[]
        if decision=="ACCEPT":
            if not refs: raise ValueError("accepted output requires evidence")
            for ref in refs:
                evidence=self.db.one("SELECT verified,claim_id FROM evidence WHERE id=?",(str(ref),))
                if not evidence or not evidence["verified"]:
                    raise ValueError("all output evidence must be verified before acceptance")
        ts=now()
        with self.db.transaction() as con:
            updated=con.execute("UPDATE agent_output_reviews SET status=?,reviewer=?,rationale=?,reviewed_at=? WHERE id=? AND status='READY_FOR_REVIEW'",(status,reviewer,rationale,ts,review_id))
            if updated.rowcount != 1: raise ValueError("output review was already resolved")
            if decision=="ACCEPT":
                con.execute("UPDATE agent_runs SET verified=1,confidence=1.0 WHERE id=?",(row["agent_run_id"],))
                con.execute("UPDATE tasks SET status='COMPLETED',updated_at=? WHERE id=? AND status='REVIEW'",(ts,row["task_id"]))
            elif decision=="REJECT":
                con.execute("UPDATE tasks SET status='FAILED',updated_at=? WHERE id=? AND status='REVIEW'",(ts,row["task_id"]))
            con.execute("INSERT INTO audit_logs(id,event_type,entity_type,entity_id,actor,payload,created_at) VALUES (?,?,?,?,?,?,?)",
                        (str(uuid4()),"scientific.agent_output_reviewed","agent_output_review",review_id,reviewer,
                         json.dumps({"decision":decision,"task_id":row["task_id"],"agent_run_id":row["agent_run_id"]},sort_keys=True),ts))
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
