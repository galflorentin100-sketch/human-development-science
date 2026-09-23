from uuid import uuid4
import json
from app.models import TaskStatus,now
class TaskEngine:
    def __init__(self,db): self.db=db
    def create_goal(self,title,description=""):
        i=str(uuid4()); self.db.execute("INSERT INTO goals(id,company_id,title,description,status,created_at) VALUES (?, 'hds', ?, ?, 'ACTIVE', ?)",(i,title,description,now())); return self.db.one("SELECT * FROM goals WHERE id=?",(i,))
    def create_task(self,title,description="",project_id=None,owner="coo",required_permissions=None):
        i=str(uuid4()); self.db.execute("INSERT INTO tasks(id,project_id,title,description,status,required_permissions,created_at) VALUES (?,?,?,?,?,?,?)",(i,project_id,title,description,"PLANNED",json.dumps(required_permissions or ["READ"]),now())); return self.db.one("SELECT * FROM tasks WHERE id=?",(i,))
    def get(self,i): return self.db.one("SELECT * FROM tasks WHERE id=?",(i,))
    def transition(self,i,status):
        self.db.execute("UPDATE tasks SET status=? WHERE id=?",(status.value if isinstance(status,TaskStatus) else status,i)); return self.get(i)
    def ready(self,i): return self.get(i)
    def record_attempt(self,*args,**kwargs): return None
