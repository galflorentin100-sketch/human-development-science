from app.orchestrator import CompanyOrchestrator
class AutonomousLoop:
    def __init__(self,db): self.db=db; self.orchestrator=CompanyOrchestrator(db)
    def run(self,project_id,max_steps=25):
        if not 1<=max_steps<=25: raise ValueError("max_steps must be 1..25")
        history=[]
        for step in range(max_steps):
            decision=self.orchestrator.decide_next(project_id)
            history.append({"step":step+1,"decision":decision})
            if decision.get("action")=="EXECUTE_NEXT_TASK":
                result=self.orchestrator.execute_next(project_id)
                history.append({"step":step+1,"execution":result})
                continue
            if decision.get("action_required"):
                return {"status":"WAITING_FOR_APPROVAL","steps":step+1,"history":history}
            result=self.orchestrator.advance(project_id)
            history.append({"step":step+1,"advance":result})
            if result.get("status")=="COMPLETED":
                return {"status":"COMPLETED","steps":step+1,"history":history}
        return {"status":"STEP_LIMIT_REACHED","steps":max_steps,"history":history}
