from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from pathlib import Path
from app.config import Settings
from app.database import Database
from app.workflow import ResearchCycle
from app.intelligence import IntelligenceService
from app.tasks import TaskEngine
from app.briefs import FounderBriefService
settings=Settings.load()
db=Database(settings.db_path)
cycle=ResearchCycle(db)
app=FastAPI(title="HDS Company OS")
class Goal(BaseModel): goal:str
@app.get("/health")
def health(): return {"status":"ok","service":"hds-company-os"}
@app.get("/api/company-state")
def state(): return db.one("SELECT * FROM companies WHERE id='hds'")
@app.get("/api/company-state/full")
def full():
    return {"company":db.one("SELECT * FROM companies WHERE id='hds'"),"goals":db.all("SELECT * FROM goals WHERE status='ACTIVE'"),"active_projects":db.all("SELECT * FROM projects WHERE status IN ('RUNNING','PLANNED')"),"active_tasks":db.all("SELECT * FROM tasks WHERE status IN ('PLANNED','ASSIGNED','RUNNING','BLOCKED')"),"agents":db.all("SELECT id,name,role,status,version,manager FROM agents"),"risks":db.all("SELECT * FROM risks WHERE status='OPEN'"),"opportunities":db.all("SELECT * FROM opportunities WHERE status='OPEN'"),"experiments":db.all("SELECT * FROM experiments WHERE status!='COMPLETED'"),"decisions":db.all("SELECT * FROM decisions ORDER BY created_at DESC LIMIT 10"),"failures":db.all("SELECT * FROM failures ORDER BY created_at DESC LIMIT 10"),"lessons":db.all("SELECT * FROM lessons ORDER BY created_at DESC LIMIT 10"),"approvals":db.all("SELECT * FROM approvals WHERE status='PENDING'")}
@app.get("/api/intelligence")
def intelligence():
    s=IntelligenceService(db)
    return {"findings":s.findings(),"timeline":s.timeline(),"workforce":s.workforce(),"health":s.health(),"brief":FounderBriefService(db).build()}
@app.get("/api/agents")
def agents(): return db.all("SELECT * FROM agents ORDER BY id")
@app.post("/api/founder-goals")
def founder_goal(body:Goal):
    return {"goal":TaskEngine(db).create_goal(body.goal,body.goal)}
@app.get("/")
def dashboard():
    return HTMLResponse((Path(__file__).parent/"dashboard.html").read_text())
