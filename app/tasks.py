from uuid import uuid4
import json
from app.models import now,TaskStatus
class TaskEngine:
    def __init__(self,db): self.db=db
    def create_goal(self,title,description=""):
        i=str(uuid4()); self.db.execute("INSERT INTO goals(id,company_id,title,status,priority,owner,expected_outcome,created_at,updated_at) VALUES (?,? ,?,'ACTIVE',?,?,?,?,?)",(i,"hds",title,1.0,"ceo",description,now(),now())); return self.db.one("SELECT * FROM goals WHERE id=?",(i,))
    def create_task(self,title,description="",project_id=None,owner="coo",required_permissions=None,priority=1.0,retry_limit=2):
        if project_id is None: raise ValueError("project_id is required")
        i=str(uuid4()); self.db.execute("INSERT INTO tasks(id,project_id,title,status,assigned_agent_id,priority,success_criteria,created_at,updated_at,owner,required_permissions) VALUES (?,?,?,?,?,?,?,?,?,?,?)",(i,project_id,title,"PLANNED",owner,float(priority),description or "Complete task",now(),now(),owner,json.dumps(required_permissions or ["READ"])); self.db.execute("UPDATE tasks SET retry_limit=? WHERE id=?",(max(0,int(retry_limit)),i)); return self.db.one("SELECT * FROM tasks WHERE id=?",(i,))
    def get(self,i): return self.db.one("SELECT * FROM tasks WHERE id=?",(i,))
    def transition(self,i,status):
        row=self.get(i)
        if not row: raise ValueError("task not found")
        allowed={"PLANNED":{"ASSIGNED","CANCELLED"},"ASSIGNED":{"RUNNING","CANCELLED"},"RUNNING":{"COMPLETED","FAILED","BLOCKED","REVIEW"},"REVIEW":{"COMPLETED","FAILED","BLOCKED"},"BLOCKED":{"PLANNED","CANCELLED"},"FAILED":{"PLANNED","CANCELLED"}}
        current=row["status"]; target=status.value if isinstance(status,TaskStatus) else status
        if target!=current and target not in allowed.get(current,set()): raise ValueError(f"invalid task transition {current}->{target}")
        updated=self.db.execute("UPDATE tasks SET status=?,updated_at=? WHERE id=? AND status=?",(target,now(),i,current))
        if getattr(updated,"rowcount",1) != 1:
            raise ValueError("task transition lost due to concurrent state change")
        return self.get(i)
    def ready(self,i): return self.get(i)
    def retry_or_escalate(self,task_id,reason):
        if not reason or not str(reason).strip(): raise ValueError("retry reason is required")
        with self.db.transaction() as con:
            cur=con.execute("SELECT * FROM tasks WHERE id=?",(task_id,))
            row=cur.fetchone()
            if row is None: raise ValueError("task not found")
            task=dict(row) if hasattr(row,"keys") else dict(zip([d.name for d in cur.description],row))
            current=task["status"]
            if current not in {"RUNNING","REVIEW"}:
                raise ValueError(f"task is not retryable from {current}")
            count=int(task.get("retry_count") or 0)
            limit=int(task["retry_limit"] or 0)
            next_attempt=count+1
            if next_attempt<=limit:
                updated=con.execute("UPDATE tasks SET status='PLANNED',retry_count=?,updated_at=? WHERE id=? AND status IN ('RUNNING','REVIEW') AND retry_count=?",(next_attempt,now(),task_id,count))
                if getattr(updated,"rowcount",1)!=1: raise ValueError("retry state changed concurrently")
                con.execute("INSERT INTO task_attempts(id,task_id,attempt_number,outcome,error,created_at) VALUES (?,?,?,?,?,?)",(str(uuid4()),task_id,next_attempt,"RETRY",reason,now()))
                con.execute("INSERT INTO retry_events(id,task_id,attempt,reason,action,created_at) VALUES (?,?,?,?,?,?)",(str(uuid4()),task_id,next_attempt,reason,"RETRY",now()))
                return {"action":"RETRY","attempt":next_attempt,"limit":limit}
            updated=con.execute("UPDATE tasks SET status='FAILED',retry_count=?,escalation_required=1,updated_at=? WHERE id=? AND status IN ('RUNNING','REVIEW') AND retry_count=?",(next_attempt,now(),task_id,count))
            if getattr(updated,"rowcount",1)!=1: raise ValueError("escalation state changed concurrently")
            con.execute("INSERT INTO retry_events(id,task_id,attempt,reason,action,created_at) VALUES (?,?,?,?,?,?)",(str(uuid4()),task_id,next_attempt,reason,"ESCALATE",now()))
            return {"action":"ESCALATE","attempt":next_attempt,"limit":limit}
    def record_attempt(self,task_id,outcome,error=None):
        row=self.db.one("SELECT COALESCE(MAX(attempt_number),0)+1 AS n FROM task_attempts WHERE task_id=?",(task_id,))
        attempt=row["n"]; self.db.execute("INSERT INTO task_attempts(id,task_id,attempt_number,outcome,error,created_at) VALUES (?,?,?,?,?,?)",(str(uuid4()),task_id,attempt,outcome,error,now())); return self.db.one("SELECT * FROM task_attempts WHERE task_id=? AND attempt_number=?",(task_id,attempt))
