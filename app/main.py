from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from pathlib import Path
from app.config import Settings
from app.database import Database
from app.workflow import ResearchCycle
from app.intelligence import IntelligenceService
from app.tasks import TaskEngine
from app.briefs import FounderBriefService
from app.research import ResearchRepository
from app.planner import AutonomousPlanner
from app.orchestrator import CompanyOrchestrator
from app.idempotency import IdempotencyService
from app.evidence_pipeline import EvidencePipeline
from app.autonomous_loop import AutonomousLoop
from app.sc001 import SC001Protocol
settings=Settings.load()
db=Database(settings.database_path)
cycle=ResearchCycle(db)
app=FastAPI(title="HDS Company OS")
class Goal(BaseModel): goal:str=Field(min_length=1,max_length=2000)
class ResearchRequest(BaseModel): question:str=Field(min_length=1,max_length=4000)
class ExperimentRequest(BaseModel):
    project_id:str; hypothesis:str=Field(min_length=1); design:str=Field(min_length=1)
@app.get("/health")
def health():
    checks={"database":False,"agents":False}
    try:
        db.migrate()
        checks["database"]=db.one("SELECT 1 AS ok")["ok"]==1
        checks["agents"]=db.one("SELECT COUNT(*) AS n FROM agents")["n"]>=1
    except Exception:
        pass
    return {"status":"ok" if all(checks.values()) else "degraded","service":"hds-company-os","environment":settings.environment,"checks":checks}
@app.get("/api/company-state")
def state(): return db.one("SELECT * FROM companies WHERE id='hds'")
@app.get("/api/company-state/full")
def full(): return {"company":db.one("SELECT * FROM companies WHERE id='hds'"),"goals":db.all("SELECT * FROM goals WHERE status='ACTIVE'"),"active_projects":db.all("SELECT * FROM projects WHERE status IN ('RUNNING','PLANNED')"),"active_tasks":db.all("SELECT * FROM tasks WHERE status IN ('PLANNED','ASSIGNED','RUNNING','BLOCKED')"),"agents":db.all("SELECT id,name,role,status,version,manager FROM agents"),"risks":db.all("SELECT * FROM risks WHERE status='OPEN'"),"opportunities":db.all("SELECT * FROM opportunities WHERE status='OPEN'"),"experiments":db.all("SELECT * FROM experiments WHERE status!='COMPLETED'"),"decisions":db.all("SELECT * FROM decisions ORDER BY created_at DESC LIMIT 10"),"failures":db.all("SELECT * FROM failures ORDER BY created_at DESC LIMIT 10"),"lessons":db.all("SELECT * FROM lessons ORDER BY created_at DESC LIMIT 10"),"approvals":db.all("SELECT * FROM approvals WHERE status='PENDING'")}
@app.get("/api/sc001/protocol")
def sc001_protocol():
    p=SC001Protocol().draft()
    return {"protocol":p.__dict__,"quality_gates":SC001Protocol().quality_gates(p)}
@app.get("/api/evidence/{project_id}")
def evidence(project_id:str): return {"claims":db.all("SELECT * FROM claims WHERE project_id=?",(project_id,)),"evidence":db.all("SELECT e.*,s.title,s.url FROM evidence e JOIN claims c ON c.id=e.claim_id JOIN sources s ON s.id=e.source_id WHERE c.project_id=?",(project_id,)),"reviews":db.all("SELECT er.* FROM evidence_reviews er JOIN evidence e ON e.id=er.evidence_id JOIN claims c ON c.id=e.claim_id WHERE c.project_id=?",(project_id,))}
@app.get("/api/intelligence")
def intelligence():
    s=IntelligenceService(db); return {"findings":s.findings(),"timeline":s.timeline(),"workforce":s.workforce(),"health":s.health(),"brief":FounderBriefService(db).build()}
@app.get("/api/agents")
def agents(): return db.all("SELECT * FROM agents ORDER BY id")
@app.post("/api/founder-goals")
def founder_goal(body:Goal, idempotency_key: str|None = None):
    def operation():
        goal=TaskEngine(db).create_goal(body.goal,body.goal)
        return {"goal":goal,"orchestration":CompanyOrchestrator(db).start_goal(goal["id"])}
    return IdempotencyService(db).run(idempotency_key,"founder","founder-goal",operation)
@app.post("/api/projects/{project_id}/autonomous-run")
def autonomous_run(project_id:str): return CompanyOrchestrator(db).run_autonomous(project_id)
@app.post("/api/projects/{project_id}/autonomous-run")
def autonomous_run(project_id:str): return AutonomousLoop(db).run(project_id)
@app.post("/api/projects/{project_id}/decide-next")
def decide_next(project_id:str): return CompanyOrchestrator(db).decide_next(project_id)
@app.post("/api/projects/{project_id}/execute-next")
def execute_next(project_id:str): return CompanyOrchestrator(db).execute_next(project_id)
@app.post("/api/projects/{project_id}/advance")
def advance_project(project_id:str): return CompanyOrchestrator(db).advance(project_id)
@app.post("/api/research/run")
def research_run(body:ResearchRequest): return cycle.run(body.question)
@app.post("/api/experiments")
def create_experiment(body:ExperimentRequest):
    if not db.one("SELECT 1 FROM projects WHERE id=?",(body.project_id,)): raise HTTPException(404,"project not found")
    return ResearchRepository(db).experiment(body.project_id,body.hypothesis,body.design)
@app.post("/api/projects/{project_id}/next-tasks")
def next_tasks(project_id:str):
    if not db.one("SELECT 1 FROM projects WHERE id=?",(project_id,)): raise HTTPException(404,"project not found")
    return AutonomousPlanner(db).create_next_tasks(project_id,[{"title":"Collect evidence","agent_id":"researcher","priority":1.0},{"title":"Challenge evidence","agent_id":"skeptic","priority":0.9},{"title":"Audit evidence","agent_id":"evidence-auditor","priority":0.9}])
@app.get("/")
def dashboard(): return HTMLResponse((Path(__file__).parent/"dashboard.html").read_text())
