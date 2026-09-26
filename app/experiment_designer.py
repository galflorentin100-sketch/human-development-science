from app.tasks import TaskEngine
from app.models import now

class ExperimentDesigner:
    def __init__(self,db):
        self.db=db
        self.tasks=TaskEngine(db)
        self.db.execute("CREATE TABLE IF NOT EXISTS experiment_design_tasks (task_id TEXT PRIMARY KEY, project_id TEXT NOT NULL, research_question TEXT NOT NULL, created_at TEXT NOT NULL)")

    def create_task(self,project_id,research_question,hypothesis=""):
        if not str(research_question or "").strip():
            raise ValueError("research question is required")
        existing=self.db.one("SELECT task_id FROM experiment_design_tasks WHERE project_id=? AND research_question=?",(project_id,research_question))
        if existing:
            return self.db.one("SELECT * FROM tasks WHERE id=?",(existing["task_id"],))
        agent=self.db.one("SELECT id FROM agents WHERE id='experiment-designer' AND status IN ('ACTIVE','IDLE')")
        if not agent:
            raise ValueError("experiment-designer agent not found")
        task=self.tasks.create_task(title="[EXPERIMENT_DESIGN] "+research_question,description="Design a preregisterable experiment for: "+research_question+" Hypothesis: "+hypothesis,project_id=project_id,owner=agent["id"],required_permissions=["READ"],priority=1.7,retry_limit=1)
        self.db.execute("INSERT INTO experiment_design_tasks(task_id,project_id,research_question,created_at) VALUES (?,?,?,?)",(task["id"],project_id,research_question,now()))
        return task
