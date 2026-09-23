from __future__ import annotations
from uuid import uuid4
from app.models import now
from app.tasks import TaskEngine
from app.planner import AutonomousPlanner
from app.execution import AgentExecutor
from app.evaluation import EvaluationService
from app.decision_engine import DecisionEngine
class CompanyOrchestrator:
    def __init__(self,db): self.db=db; self.tasks=TaskEngine(db); self.planner=AutonomousPlanner(db)
    def start_goal(self,goal_id):
        goal=self.db.one("SELECT * FROM goals WHERE id=?",(goal_id,))
        if not goal: raise ValueError("goal not found")
        project_id=str(uuid4()); ts=now()
        self.db.execute("INSERT INTO projects(id,company_id,objective,status,owner_agent_id,created_at,goal_id,updated_at) VALUES (?,?,?,?,?,?,?,?)",(project_id,"hds",goal["title"],"PLANNED","ceo",ts,goal_id,ts))
        candidates=[{"title":"Define scientific question and success criteria","agent_id":"chief-scientist","priority":1.0,"success_criteria":"Produce a falsifiable question and measurable outcome."},{"title":"Build evidence map","agent_id":"researcher","priority":0.95,"success_criteria":"Collect traceable evidence and identify uncertainty."},{"title":"Challenge assumptions","agent_id":"skeptic","priority":0.9,"success_criteria":"Document alternative explanations and failure modes."},{"title":"Audit evidence quality","agent_id":"evidence-auditor","priority":0.9,"success_criteria":"Classify evidence and flag unsupported claims."},{"title":"Design validation experiment","agent_id":"experiment-designer","priority":0.85,"success_criteria":"Create a testable design with outcomes, controls and retention/transfer measures."}]
        tasks=self.planner.create_next_tasks(project_id,candidates)
        self.db.execute("UPDATE projects SET status='RUNNING',updated_at=? WHERE id=?",(now(),project_id))
        self.db.execute("UPDATE goals SET actual_outcome=? WHERE id=?",(f"Project {project_id} created and planned",goal_id))
        self.db.audit("company.goal_started","goal",goal_id,"ceo",{"project_id":project_id,"task_count":len(tasks)},now(),str(uuid4()))
        return {"goal":goal,"project":self.db.one("SELECT * FROM projects WHERE id=?",(project_id,)),"tasks":tasks}
    def execute_next(self,project_id):
        task=self.db.one("SELECT * FROM tasks WHERE project_id=? AND status IN ('PLANNED','ASSIGNED') ORDER BY priority DESC LIMIT 1",(project_id,))
        if not task: return {"status":"NO_EXECUTABLE_TASK"}
        result=AgentExecutor(self.db).execute(task["assigned_agent_id"],task["id"],{"title":task["title"]},{"project_id":project_id,"success_criteria":task["success_criteria"]})
        run=self.db.one("SELECT id FROM agent_runs WHERE task_id=? ORDER BY started_at DESC LIMIT 1",(task["id"],))
        evaluation=EvaluationService(self.db).evaluate_run(run["id"],task["success_criteria"])
        if evaluation["passed"]:
            self.db.execute("UPDATE tasks SET status='COMPLETED',updated_at=? WHERE id=?",(now(),task["id"]))
            return {"status":"COMPLETED","task":task,"evaluation":evaluation}
        failure=EvaluationService(self.db).record_failure(project_id,"agent_execution",task["success_criteria"],"Unverified output","Execution produced no independently verified result.","Require verification before completion.","Add evidence-backed evaluator or external model.")
        self.db.execute("UPDATE tasks SET status='FAILED',updated_at=? WHERE id=?",(now(),task["id"]))
        replanned=self.planner.replan_after_failure(project_id,failure)
        return {"status":"FAILED","task":task,"evaluation":evaluation,"failure":failure,"replanned_tasks":replanned}
    def run_autonomous(self,project_id,max_steps=25):
        if max_steps>25: raise ValueError("autonomous loop is bounded to 25 steps")
        history=[]
        for step in range(max_steps):
            decision=self.decide_next(project_id)
            history.append({"step":step+1,"decision":decision})
            if decision.get("action")=="EXECUTE_NEXT_TASK":
                result=self.execute_next(project_id)
                history.append({"step":step+1,"execution":result})
                if result.get("status")=="FAILED":
                    continue
                continue
            if decision.get("action_required"):
                return {"status":"WAITING_FOR_APPROVAL","steps":len(history),"history":history}
            pending=self.db.one("SELECT COUNT(*) AS n FROM tasks WHERE project_id=? AND status IN ('PLANNED','ASSIGNED','RUNNING','REVIEW','BLOCKED')",(project_id,))["n"]
            if pending==0:
                self.db.execute("UPDATE projects SET status='COMPLETED',updated_at=? WHERE id=?",(now(),project_id))
                return {"status":"COMPLETED","steps":len(history),"history":history}
        return {"status":"STEP_LIMIT_REACHED","steps":len(history),"history":history}
    def decide_next(self,project_id):
        project=self.db.one("SELECT * FROM projects WHERE id=?",(project_id,))
        if not project: raise ValueError("project not found")
        failures=self.db.all("SELECT lesson FROM failures WHERE project_id=? ORDER BY created_at DESC LIMIT 5",(project_id,))
        claims=self.db.all("SELECT statement,classification,confidence FROM claims WHERE project_id=? ORDER BY created_at DESC LIMIT 10",(project_id,))
        pending=self.db.all("SELECT title,status FROM tasks WHERE project_id=? AND status IN ('PLANNED','ASSIGNED','RUNNING','REVIEW')",(project_id,))
        if failures:
            return DecisionEngine(self.db).assess(project_id,"Investigate and correct the latest failure",["Retry immediately","Run corrective validation"],claims,failures,0.65,"Resolve the failure and demonstrate corrected behavior",owner="ceo",risk_level="MEDIUM")
        if pending:
            return {"action":"EXECUTE_NEXT_TASK","task":pending[0],"reason":"There is actionable work remaining."}
        return DecisionEngine(self.db).assess(project_id,"Close project after evidence review",["Continue research","Close project"],claims,[],0.8,"Close only after required evidence and validation are complete",owner="ceo",risk_level="MEDIUM")
    def advance(self,project_id):
        project=self.db.one("SELECT * FROM projects WHERE id=?",(project_id,))
        if not project: raise ValueError("project not found")
        pending=self.db.all("SELECT * FROM tasks WHERE project_id=? AND status IN ('PLANNED','ASSIGNED','RUNNING') ORDER BY priority DESC",(project_id,))
        if pending: return {"status":"TASKS_PENDING","next_task":pending[0],"remaining":len(pending)}
        self.db.execute("UPDATE projects SET status='COMPLETED',updated_at=? WHERE id=?",(now(),project_id))
        return {"status":"COMPLETED","project":self.db.one("SELECT * FROM projects WHERE id=?",(project_id,))}
