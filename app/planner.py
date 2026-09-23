from uuid import uuid4
from app.models import now
class AutonomousPlanner:
    def __init__(self,db): self.db=db
    @staticmethod
    def priority(impact,urgency,confidence,feasibility,cost): return impact*urgency*confidence*feasibility/max(cost,0.01)
    def plan(self,project_id,candidates):
        ranked=sorted(candidates,key=lambda x:self.priority(x.get("impact",1),x.get("urgency",1),x.get("confidence",1),x.get("feasibility",1),x.get("cost",1)),reverse=True)
        return ranked
    def create_next_tasks(self,project_id,candidates,limit=5):
        created=[]
        for c in self.plan(project_id,candidates)[:limit]:
            tid=str(uuid4())
            self.db.execute("INSERT INTO tasks(id,project_id,title,status,assigned_agent_id,priority,success_criteria,created_at,updated_at,owner,required_permissions) VALUES (?,?,?,?,?,?,?,?,?,?,?)",(tid,project_id,c.get("title","Untitled task"),"PLANNED",c.get("agent_id","coo"),float(c.get("priority",1)),c.get("success_criteria","Produce a verifiable output."),now(),now(),c.get("agent_id","coo"),'["READ"]'))
            created.append(self.db.one("SELECT * FROM tasks WHERE id=?",(tid,)))
        return created
    def replan_after_failure(self,project_id,failure):
        lesson=failure.get("lesson","unknown failure")
        return [{"title":"Analyze failure and revise plan","agent_id":"skeptic","impact":1.5,"urgency":1.5,"confidence":0.9,"feasibility":0.9,"cost":1,"success_criteria":"Document root cause and corrective action."},{"title":"Validate corrective action","agent_id":"qa","impact":1.4,"urgency":1.2,"confidence":0.85,"feasibility":0.8,"cost":1,"success_criteria":"Demonstrate that the corrective action addresses the failure."}]
