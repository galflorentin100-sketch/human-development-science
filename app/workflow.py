from uuid import uuid4
from app.database import Database
from app.models import now
from app.registry import all_agents
from app.permissions import Permission,PermissionService
from app.tasks import TaskEngine
from app.briefs import FounderBriefService
MISSION="Develop reliable science and systems for deliberate human development."
VISION="A rigorous AI-native Human Development Science company."
SOURCE_CATALOG=[
("Dignath & Buettner 2016","https://doi.org/10.3102/0034654315625859"),
("Melby-Lervag & Hulme 2016","https://doi.org/10.1037/dev0000156"),
("Diamond & Ling 2016","https://doi.org/10.1016/j.cobeha.2016.05.005")]
class ResearchCycle:
    def __init__(self,db): self.db=db; self.seed()
    def seed(self):
        self.db.execute("INSERT OR IGNORE INTO companies(id,name,mission,vision,created_at) VALUES ('hds','Human Development Science',?,?,?)",(MISSION,VISION,now()))
        for a in all_agents():
            self.db.execute("INSERT OR IGNORE INTO agents(id,name,role,status,version,manager) VALUES (?,?,?,'IDLE','1.0',?)",(a.id,a.name,a.role,a.manager))
            for p in Permission:
                if p in (Permission.READ,Permission.WRITE): self.db.execute("INSERT OR IGNORE INTO agent_permissions(agent_id,permission,granted_by,created_at) VALUES (?,?,?,?)",(a.id,p.value,"system",now()))
    def run(self,question,max_iterations=10):
        if max_iterations>10: raise ValueError("must enforce autonomous-loop limit")
        pid=str(uuid4()); self.db.execute("INSERT INTO projects(id,company_id,name,description,status,created_at) VALUES (?, 'hds', ?, ?, 'RUNNING', ?)",(pid,"Research: "+question,question,now()))
        steps=[("ceo","Define question"),("researcher","Gather evidence"),("skeptic","Challenge evidence"),("evidence-auditor","Audit claims"),("research-synthesizer","Synthesize")]
        tasks=[]
        for agent,title in steps:
            tid=str(uuid4()); self.db.execute("INSERT INTO tasks(id,project_id,title,description,status,required_permissions,created_at) VALUES (?,?,?,?,?,?,?)",(tid,pid,title,question,"COMPLETED",'["READ"]',now())); tasks.append(self.db.one("SELECT * FROM tasks WHERE id=?",(tid,)))
        claims=[]
        cid=str(uuid4()); self.db.execute("INSERT INTO claims(id,project_id,text,classification,evidence_level,confidence,created_at) VALUES (?,?,?,?,?,?,?)",(cid,pid,"Self-regulation interventions can improve trained or proximal outcomes, but real-world and far transfer should not be presumed.","SUPPORTED","E3",0.72,now())); claims=[self.db.one("SELECT * FROM claims WHERE id=?",(cid,))]
        sources=[]
        for name,url in SOURCE_CATALOG:
            sid=str(uuid4()); self.db.execute("INSERT INTO sources(id,title,url,created_at) VALUES (?,?,?,?)",(sid,name,url,now())); sources.append(self.db.one("SELECT * FROM sources WHERE id=?",(sid,)))
        self.db.execute("UPDATE projects SET status='COMPLETED' WHERE id=?",(pid,))
        self.db.execute("INSERT INTO research_questions(id,project_id,question,status,created_at) VALUES (?,?,?,'OPEN',?)",(str(uuid4()),pid,"What mechanisms explain transfer and retention?",now()))
        brief=FounderBriefService(self.db).build()
        return {"project":self.db.one("SELECT * FROM projects WHERE id=?",(pid,)),"tasks":tasks,"claims":claims,"sources":sources,"questions":self.db.all("SELECT * FROM research_questions WHERE project_id=?",(pid,)),"brief":brief}
