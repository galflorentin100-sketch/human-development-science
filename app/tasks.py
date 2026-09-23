from uuid import uuid4
import json
from app.models import TaskStatus,now
class TaskEngine:
    def __init__(self,db): self.db=db
    def create_goal(self,title,description=""):
        i=str(uuid4()); self.db.execute("INSERT INTO goals(id,company_id,title,status,priority,owner,expected_outcome,created_at,updated_at) VALUES (?,? ,?,'ACTIVE',?,?,?,?,?)",(i,"hds",title,1.0,"ceo",description,now(),now())); return self.db.one("SELECT * FROM goals WHERE id=?",(i,))
    def create_task(self,title,description="",project_id=None,owner="coo",required_permissions=None):
        if project_id is None: raise ValueError("project_id is required")
        i=str(uuid4()); self.db.execute("INSERT INTO tasks(id,project_id,title,status,assigned_agent_id,priority,success_criteria,created_at,updated_at,owner,required_permissions) VALUES (?,?,?,?,?,?,?,?,?,?,?)",(i,project_id,title,"PLANNED",owner,1.0,description or "Complete task",now(),now(),owner,json.dumps(required_permissions or ["READ"]))); return self.db.one("SELECT * FROM tasks WHERE id=?",(i,))
    def get(self,i): return self.db.one("SELECT * FROM tasks WHERE id=?",(i,))
    def transition(self,i,status):
        self.db.execute("UPDATE tasks SET status=?,updated_at=? WHERE id=?",(status.value if isinstance(status,TaskStatus) else status,now(),i)); return self.get(i)
    def ready(self,i): return self.get(i)
    def record_attempt(self,*args,**kwargs): return None
