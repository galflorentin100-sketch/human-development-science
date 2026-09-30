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
        # A direct execution call must not bypass a pending DecisionEngine approval.
        # The autonomous loop already stops on action_required; this closes the
        # alternate HTTP path that could otherwise execute queued work directly.
        pending_decision=self.db.one(
            "SELECT id,action,status FROM approvals WHERE status='PENDING' AND action LIKE 'DECISION:%' ORDER BY created_at DESC LIMIT 1"
        )

