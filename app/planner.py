from uuid import uuid4
from app.models import now
class AutonomousPlanner:
    def __init__(self,db): self.db=db
    @staticmethod
    def priority(impact,urgency,confidence,feasibility,cost): return impact*urgency*confidence*feasibility/max(cost,0.01)
    def context(self,project_id):
        return {"project":self.db.one("SELECT * FROM projects WHERE id=?",(project_id,)),"goal":self.db.one("SELECT g.* FROM goals g JOIN projects p ON p.goal_id=g.id WHERE p.id=?",(project_id,)),"failures":self.db.all("SELECT * FROM failures WHERE project_id=? ORDER BY created_at DESC LIMIT 10",(project_id,)),"risks":self.db.all("SELECT * FROM risks WHERE status='OPEN' ORDER BY created_at DESC LIMIT 10"),"claims":self.db.all("SELECT * FROM claims WHERE project_id=? ORDER BY created_at DESC LIMIT 20",(project_id,)),"questions":self.db.all("SELECT * FROM research_questions WHERE project_id=? AND status='OPEN'",(project_id,))}
    def plan(self,project_id,candidates):
        ctx=self.context(project_id); failures=len(ctx["failures"]); risks=len(ctx["risks"]); unanswered=len(ctx["questions"]); ranked=[]
        for c in candidates:
            impact=c.get("impact",1)+min(failures,3)*0.2; urgency=c.get("urgency",1)+min(risks,3)*0.15
            if c.get("addresses_failure"): impact+=0.6
            if c.get("answers_question") and unanswered: impact+=0.4
            ranked.append((self.priority(impact,urgency,c.get("confidence",1),c.get("feasibility",1),c.get("cost",1)),c))
        return [c for _,c in sorted(ranked,key=lambda x:x[0],reverse=True)]
    def create_next_tasks(self,project_id,candidates,limit=5):
        created=[]
        for c in self.plan(project_id,candidates)[:limit]:
            tid=str(uuid4()); priority=self.priority(c.get("impact",1),c.get("urgency",1),c.get("confidence",1),c.get("feasibility",1),c.get("cost",1))
            self.db.execute("INSERT INTO tasks(id,project_id,title,status,assigned_agent_id,priority,success_criteria,created_at,updated_at,owner,required_permissions) VALUES (?,?,?,?,?,?,?,?,?,?,?)",(tid,project_id,c.get("title","Untitled task"),"PLANNED",c.get("agent_id","coo"),priority,c.get("success_criteria","Produce a verifiable output."),now(),now(),c.get("agent_id","coo"),'["READ"]'))
            created.append(self.db.one("SELECT * FROM tasks WHERE id=?",(tid,)))
        return created
    def replan_after_failure(self,project_id,failure):
        lesson=failure.get("lesson","unknown failure")
        return self.create_next_tasks(project_id,[{"title":"Analyze failure and revise plan","agent_id":"skeptic","impact":1.5,"urgency":1.5,"confidence":0.9,"feasibility":0.9,"addresses_failure":True,"success_criteria":f"Explain root cause and corrective action. Lesson: {lesson}"},{"title":"Validate corrective action","agent_id":"qa","impact":1.4,"urgency":1.2,"confidence":0.85,"feasibility":0.8,"addresses_failure":True,"success_criteria":"Demonstrate that the corrective action addresses the failure."}],2)
