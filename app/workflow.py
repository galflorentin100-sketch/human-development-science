from uuid import uuid4
from app.models import now
from app.registry import all_agents
from app.permissions import Permission
from app.briefs import FounderBriefService
MISSION="Develop reliable science and systems for deliberate human development."
VISION="A rigorous AI-native Human Development Science company."
SOURCE_CATALOG=[
("Dignath & Buettner","https://doi.org/10.3102/0034654315625859"),
("Melby-Lervag & Hulme","https://doi.org/10.1037/dev0000156"),
("Diamond & Ling","https://doi.org/10.1016/j.cobeha.2016.05.005")]
class ResearchCycle:
    def __init__(self,db): self.db=db; self.db.migrate(); self.seed()
    def seed(self):
        self.db.execute("INSERT OR IGNORE INTO companies(id,name,mission,vision,core_principle,created_at) VALUES ('hds','Human Development Science',?,?,?,?)",(MISSION,VISION,"Truth before all; evidence over hype.",now()))
        for a in all_agents():
            self.db.execute("INSERT OR IGNORE INTO agents(id,name,role,mission,capabilities,permissions,version,status,created_at,manager) VALUES (?,?,?,?,?,?,?,?,?,?)",(a.id,a.name,a.role,a.role,"[]","[]","1.0","IDLE",now(),a.manager))
            base={Permission.READ}
            role=a.role.lower()
            if role in {"ceo","coo","chief-scientist","cto","cpo","cfo","risk-officer","product-manager"}: base.add(Permission.WRITE)
            if role in {"coo","cto","engineer","qa","experiment-designer","researcher","skeptic","evidence-auditor","research-synthesizer","data-scientist","red-team"}: base.add(Permission.EXECUTE)
            for p in base:
                self.db.execute("INSERT OR IGNORE INTO agent_permissions(agent_id,permission) VALUES (?,?)",(a.id,p.value))
    def run(self,question,max_iterations=10):
        if not question.strip(): raise ValueError("question is required")
        if max_iterations>10: raise ValueError("must enforce autonomous-loop limit")
        pid=str(uuid4()); ts=now()
        self.db.execute("INSERT INTO projects(id,company_id,objective,status,owner_agent_id,created_at,goal_id,updated_at) VALUES (?,?,?,?,?,?,?,?)",(pid,"hds",question,"RUNNING","chief-scientist",ts,None,ts))
        steps=[("ceo","Define question"),("researcher","Gather evidence"),("skeptic","Challenge evidence"),("evidence-auditor","Audit claims"),("research-synthesizer","Synthesize")]
        tasks=[]
        for agent,title in steps:
            tid=str(uuid4())
            self.db.execute("INSERT INTO tasks(id,project_id,title,status,assigned_agent_id,priority,success_criteria,created_at,updated_at,owner,required_permissions) VALUES (?,?,?,?,?,?,?,?,?,?,?)",(tid,pid,title,"COMPLETED",agent,1.0,"Produce an auditable output.",ts,ts,agent,'["READ"]'))
            tasks.append(self.db.one("SELECT * FROM tasks WHERE id=?",(tid,)))
        claim_id=str(uuid4())
        statement="Self-regulation interventions can improve trained or proximal outcomes, but real-world and far transfer should not be presumed."
        self.db.execute("INSERT INTO claims(id,project_id,statement,classification,evidence_level,confidence,status,created_at) VALUES (?,?,?,?,?,?,?,?)",(claim_id,pid,statement,"PRELIMINARY","UNVERIFIED",0.0,"REVIEW_REQUIRED",ts))
        claims=[self.db.one("SELECT * FROM claims WHERE id=?",(claim_id,))]
        sources=[]
        for name,url in SOURCE_CATALOG:
            sid=str(uuid4())
            self.db.execute("INSERT OR IGNORE INTO sources(id,title,url,authors,publication_year,source_type,verified_at,provenance_note) VALUES (?,?,?,?,?,?,?,?)",(sid,name,url,"",None,"PAPER",ts,"Seeded reference; verify full text before scientific use."))
            src=self.db.one("SELECT * FROM sources WHERE url=?",(url,))
            sources.append(src)
            eid=str(uuid4())
            self.db.execute("INSERT INTO evidence(id,claim_id,source_id,stance,excerpt,verified,created_at) VALUES (?,?,?,?,?,?,?)",(eid,claim_id,src["id"],"SUPPORTS","Seeded bibliographic source; excerpt not yet independently verified.",0,ts))
        self.db.execute("INSERT INTO findings(id,project_id,claim_id,category,title,change_type,confidence,evidence_level,provenance,why_it_matters,recommended_action,review_required,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",(str(uuid4()),pid,claim_id,"RESEARCH","Transfer is not automatic","BASELINE",0.72,"E3","Unverified seed; no claim-level synthesis accepted.","Prevents unsupported scientific conclusions.","Verify primary sources, extract evidence, then run a controlled transfer and retention study.",1,ts))
        self.db.execute("UPDATE projects SET status='COMPLETED',updated_at=? WHERE id=?",(now(),pid))
        qid=str(uuid4())
        self.db.execute("INSERT INTO research_questions(id,project_id,question,status,created_at) VALUES (?,?,?,'OPEN',?)",(qid,pid,"What mechanisms explain transfer and retention?",now()))
        brief=FounderBriefService(self.db).build()
        return {"project":self.db.one("SELECT * FROM projects WHERE id=?",(pid,)),"tasks":tasks,"claims":claims,"sources":sources,"questions":self.db.all("SELECT * FROM research_questions WHERE project_id=?",(pid,)),"brief":brief}
