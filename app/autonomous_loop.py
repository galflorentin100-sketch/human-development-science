from uuid import uuid4
from app.orchestrator import CompanyOrchestrator
from app.models import now

class AutonomousLoop:
    def __init__(self,db):
        self.db=db
        self.orchestrator=CompanyOrchestrator(db)

    def run(self,project_id,max_steps=25):
        if not 1<=max_steps<=25:
            raise ValueError("max_steps must be 1..25")
        history=[]
        consecutive_failures=0
        for step in range(max_steps):
            decision=self.orchestrator.decide_next(project_id)
            action=decision.get("action","WAIT")
            if action=="EXECUTE_NEXT_TASK":
                result=self.orchestrator.execute_next(project_id)
                if result.get("status") in {"FAILED","RETRY_SCHEDULED"}:
                    consecutive_failures += 1
                else:
                    consecutive_failures = 0
                status="ESCALATED" if consecutive_failures>=3 else ("FAILED" if result.get("status")=="FAILED" else "RUNNING")
                self.db.execute(
                    "INSERT INTO autonomy_iterations(id,project_id,iteration_number,status,action,outcome,failure_count,escalated,created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                    (str(uuid4()),project_id,step+1,status,action,result.get("status","UNKNOWN"),consecutive_failures,1 if consecutive_failures>=3 else 0,now()))
                history.append({"step":step+1,"decision":decision,"execution":result})
                if consecutive_failures>=3:
                    return {"status":"ESCALATED","steps":step+1,"reason":"Three consecutive failed/retry execution cycles require human review.","history":history}
                continue
            if decision.get("action_required"):
                self.db.execute("INSERT INTO autonomy_iterations(id,project_id,iteration_number,status,action,outcome,failure_count,escalated,created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                    (str(uuid4()),project_id,step+1,"WAITING_FOR_APPROVAL",action,"approval_required",consecutive_failures,0,now()))
                return {"status":"WAITING_FOR_APPROVAL","steps":step+1,"history":history}
            result=self.orchestrator.advance(project_id)
            self.db.execute("INSERT INTO autonomy_iterations(id,project_id,iteration_number,status,action,outcome,failure_count,escalated,created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                (str(uuid4()),project_id,step+1,result.get("status","RUNNING"),action,result.get("status","UNKNOWN"),consecutive_failures,0,now()))
            history.append({"step":step+1,"decision":decision,"advance":result})
            if result.get("status")=="COMPLETED":
                return {"status":"COMPLETED","steps":step+1,"history":history}
        return {"status":"STEP_LIMIT_REACHED","steps":max_steps,"history":history}
