from __future__ import annotations
import json
from uuid import uuid4
from app.models import now
class EvaluationService:
    def __init__(self,db): self.db=db
    def evaluate_run(self,agent_run_id,expected="Produce a verifiable output."):
        run=self.db.one("SELECT * FROM agent_runs WHERE id=?",(agent_run_id,))
        if not run: raise ValueError("agent run not found")
        output=json.loads(run["output_payload"] or "{}")
        uncertainties=output.get("uncertainties",[])
        verified=bool(run["verified"]) and not uncertainties
        passed=1 if verified else 0
        score=1.0 if verified else 0.0
        details={"expected":expected,"verified":verified,"uncertainties":uncertainties}
        eid=str(uuid4())
        self.db.execute("INSERT INTO evaluations(id,agent_run_id,evaluator,passed,score,details,created_at) VALUES (?,?,?,?,?,?,?)",(eid,agent_run_id,"qa",passed,score,json.dumps(details),now()))
        return self.db.one("SELECT * FROM evaluations WHERE id=?",(eid,))
    def record_failure(self,project_id,stage,expected,actual,root_cause,lesson,corrective_action=None):
        fid=str(uuid4())
        self.db.execute("INSERT INTO failures(id,project_id,stage,expected_result,actual_result,root_cause,lesson,created_at,contributing_factors,corrective_action,owner) VALUES (?,?,?,?,?,?,?,?,?,?,?)",(fid,project_id,stage,expected,actual,root_cause,lesson,now(),"[]",corrective_action,"qa"))
        self.db.execute("INSERT INTO lessons(id,company_id,lesson,source_failure_id,created_at) VALUES (?,?,?,?,?)",(str(uuid4()),"hds",lesson,fid,now()))
        return self.db.one("SELECT * FROM failures WHERE id=?",(fid,))
