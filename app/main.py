from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from app.auth import AuthService, Principal
from app.config import Settings
from app.database import database_from_settings
from app.workflow import ResearchCycle
from app.intelligence import IntelligenceService
from app.tasks import TaskEngine
from app.briefs import FounderBriefService
from app.research import ResearchRepository, StudyExecution
from app.planner import AutonomousPlanner
from app.orchestrator import CompanyOrchestrator
from app.idempotency import IdempotencyService
from app.autonomous_loop import AutonomousLoop
from app.sc001 import SC001Protocol

settings = Settings.load()
db = database_from_settings(settings)
db.migrate()
auth = AuthService(db)
cycle = ResearchCycle(db)

@asynccontextmanager
async def lifespan(app: FastAPI):
    db.migrate()
    yield

app = FastAPI(title="HDS Company OS", lifespan=lifespan)

class Goal(BaseModel):
    goal: str = Field(min_length=1, max_length=2000)
class ResearchRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
class ExperimentRequest(BaseModel):
    project_id: str; hypothesis: str = Field(min_length=1); design: str = Field(min_length=1)
class StudyParticipantRequest(BaseModel):
    study_id: str; external_ref: str = Field(min_length=1, max_length=200); consent_status: str = "CONSENTED"
class StudyOutcomeRequest(BaseModel):
    study_id: str; participant_id: str; outcome_name: str = Field(min_length=1); value: float | None = None; unit: str | None = None; session_id: str | None = None; missing_reason: str | None = None; observation_type: str = "TRAINING"

def principal_from_header(x_external_subject: str | None = Header(default=None)) -> Principal:
    if not x_external_subject:
        if settings.environment != "production":
            return Principal("local-development", "founder", {"READ","WRITE","EXECUTE","PUBLISH","SPEND","DELETE","DEPLOY","CONTACT_EXTERNAL_PARTY","APPROVE"})
        raise HTTPException(status_code=401, detail="authentication required")
    try:
        return auth.authorize(x_external_subject)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

def require_permission(principal: Principal, permission: str) -> None:
    if principal.user_id == "local-development" and settings.environment != "production":
        return
    if not principal.can(permission):
        raise HTTPException(status_code=403, detail=f"{permission} permission required")

def require_read(principal: Principal) -> None:
    require_permission(principal, "READ")

def require_write(principal: Principal) -> None:
    require_permission(principal, "WRITE")

@app.get("/health")
def health():
    return {"status": "ok", "service": "hds-company-os", "environment": settings.environment}

@app.get("/ready")
def ready():
    try:
        db.one("SELECT 1 AS ok")
        agents = db.one("SELECT COUNT(*) AS n FROM agents")
        if not agents or agents["n"] < 1: raise RuntimeError("agent registry unavailable")
    except Exception as exc:
        raise HTTPException(status_code=503, detail="service not ready") from exc
    return {"status": "ready", "database": True, "agents": True}

@app.get("/api/operations")
def operations(principal: Principal = Depends(principal_from_header)):
    require_read(principal)
    budget=db.one("SELECT * FROM budgets WHERE company_id='hds' AND status='ACTIVE' ORDER BY created_at DESC LIMIT 1")
    return {
        "budget": budget,
        "autonomy": db.all("SELECT * FROM autonomy_iterations ORDER BY created_at DESC LIMIT 25"),
        "costs": db.all("SELECT * FROM cost_events ORDER BY created_at DESC LIMIT 25"),
        "model_calls": db.all("SELECT * FROM model_calls ORDER BY created_at DESC LIMIT 25"),
    }

@app.get("/api/health/deep")
def deep_health(principal: Principal = Depends(principal_from_header)):
    require_read(principal)
    checks={}
    try:
        checks["database"]=db.one("SELECT 1 AS ok")["ok"]==1
        checks["agents"]=db.one("SELECT COUNT(*) AS n FROM agents")["n"]>=1
        checks["migrations"]=True
        checks["budget_control"]=db.one("SELECT COUNT(*) AS n FROM budgets") is not None
    except Exception:
        checks["migrations"]=False
    return {"status":"ok" if all(checks.values()) else "degraded","checks":checks}

@app.get("/api/company-state")
def state(): return db.one("SELECT * FROM companies WHERE id='hds'")
@app.get("/api/company-state/full")
def full(principal: Principal = Depends(principal_from_header)):
    require_read(principal)
    return {"company": db.one("SELECT * FROM companies WHERE id='hds'"), "goals": db.all("SELECT * FROM goals WHERE status='ACTIVE'"), "active_projects": db.all("SELECT * FROM projects WHERE status IN ('RUNNING','PLANNED')"), "active_tasks": db.all("SELECT * FROM tasks WHERE status IN ('PLANNED','ASSIGNED','RUNNING','BLOCKED')"), "agents": db.all("SELECT id,name,role,status,version,manager FROM agents"), "risks": db.all("SELECT * FROM risks WHERE status='OPEN'"), "opportunities": db.all("SELECT * FROM opportunities WHERE status='OPEN'"), "experiments": db.all("SELECT * FROM experiments WHERE status!='COMPLETED'"), "decisions": db.all("SELECT * FROM decisions ORDER BY created_at DESC LIMIT 10"), "failures": db.all("SELECT * FROM failures ORDER BY created_at DESC LIMIT 10"), "lessons": db.all("SELECT * FROM lessons ORDER BY created_at DESC LIMIT 10"), "approvals": db.all("SELECT * FROM approvals WHERE status='PENDING'")}
@app.get("/api/sc001/protocol")
def sc001_protocol(principal: Principal = Depends(principal_from_header)):
    require_read(principal)
    p = SC001Protocol().draft(); return {"protocol": p.__dict__, "quality_gates": SC001Protocol().quality_gates(p)}
@app.get("/api/evidence/{project_id}")
def evidence(project_id: str, principal: Principal = Depends(principal_from_header)):
    require_read(principal)
    return {"claims": db.all("SELECT * FROM claims WHERE project_id=?", (project_id,)), "evidence": db.all("SELECT e.*,s.title,s.url FROM evidence e JOIN claims c ON c.id=e.claim_id JOIN sources s ON s.id=e.source_id WHERE c.project_id=?", (project_id,)), "reviews": db.all("SELECT er.* FROM evidence_reviews er JOIN evidence e ON e.id=er.evidence_id JOIN claims c ON c.id=e.claim_id WHERE c.project_id=?", (project_id,))}
@app.get("/api/intelligence")
def intelligence(principal: Principal = Depends(principal_from_header)):
    require_read(principal)
    s = IntelligenceService(db); return {"findings": s.findings(), "timeline": s.timeline(), "workforce": s.workforce(), "health": s.health(), "brief": FounderBriefService(db).build()}
@app.get("/api/agents")
def agents(principal: Principal = Depends(principal_from_header)):
    require_read(principal)
    return db.all("SELECT * FROM agents ORDER BY id")

@app.post("/api/founder-goals")
def founder_goal(body: Goal, principal: Principal = Depends(principal_from_header), idempotency_key: str | None = None):
    require_write(principal)
    def operation():
        goal = TaskEngine(db).create_goal(body.goal, body.goal)
        return {"goal": goal, "orchestration": CompanyOrchestrator(db).start_goal(goal["id"])}
    return IdempotencyService(db).run(idempotency_key, principal.user_id, "founder-goal", operation)

@app.post("/api/projects/{project_id}/autonomous-run")
def autonomous_run(project_id: str, principal: Principal = Depends(principal_from_header)):
    require_write(principal); return AutonomousLoop(db).run(project_id)
@app.post("/api/projects/{project_id}/decide-next")
def decide_next(project_id: str, principal: Principal = Depends(principal_from_header)):
    require_write(principal); return CompanyOrchestrator(db).decide_next(project_id)
@app.post("/api/projects/{project_id}/execute-next")
def execute_next(project_id: str, principal: Principal = Depends(principal_from_header)):
    require_write(principal); return CompanyOrchestrator(db).execute_next(project_id)
@app.post("/api/projects/{project_id}/advance")
def advance_project(project_id: str, principal: Principal = Depends(principal_from_header)):
    require_write(principal); return CompanyOrchestrator(db).advance(project_id)
@app.post("/api/approvals/{approval_id}/resolve")
def resolve_approval(approval_id: str, status: str, principal: Principal = Depends(principal_from_header)):
    if principal.role != "founder" or not principal.can("APPROVE"):
        raise HTTPException(status_code=403, detail="founder approval required")
    require_write(principal)
    from app.approvals import ApprovalService, ApprovalStatus, ApprovalRequired
    try:
        resolved = ApprovalService(db).resolve(approval_id, ApprovalStatus(status), principal.user_id)
        if status == "APPROVED" and resolved["action"].startswith("SC001:STUDY:"):
            study_id = resolved["action"].split(":", 2)[2]
            db.execute("UPDATE studies SET status='APPROVED' WHERE id=? AND approval_id=?", (study_id, approval_id))
        return resolved
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ApprovalRequired as exc:
        raise HTTPException(status_code=409, detail="approval is not pending or has expired") from exc

@app.post("/api/sc001/register/{project_id}")
def sc001_register(project_id: str, principal: Principal = Depends(principal_from_header)):
    require_write(principal)
    if not db.one("SELECT 1 FROM projects WHERE id=?", (project_id,)): raise HTTPException(404, "project not found")
    return SC001Protocol().register(db, project_id)
@app.post("/api/research/run")
def research_run(body: ResearchRequest, principal: Principal = Depends(principal_from_header)):
    require_write(principal); return cycle.run(body.question)
@app.post("/api/studies/participants")
def study_participant(body: StudyParticipantRequest, principal: Principal = Depends(principal_from_header)):
    require_write(principal); return StudyExecution(db).participant(body.study_id, body.external_ref, body.consent_status)
@app.post("/api/studies/outcomes")
def study_outcome(body: StudyOutcomeRequest, principal: Principal = Depends(principal_from_header)):
    require_write(principal); return StudyExecution(db).outcome(body.study_id, body.participant_id, body.outcome_name, body.value, body.unit, body.session_id, body.missing_reason, body.observation_type)
@app.post("/api/studies/{study_id}/start")
def study_start(study_id: str, principal: Principal = Depends(principal_from_header)):
    require_write(principal)
    return StudyExecution(db).start(study_id)

@app.post("/api/studies/{study_id}/complete")
def study_complete(study_id: str, principal: Principal = Depends(principal_from_header)):
    require_write(principal)
    return StudyExecution(db).complete(study_id)

@app.post("/api/experiments")
def create_experiment(body: ExperimentRequest, principal: Principal = Depends(principal_from_header)):
    require_write(principal)
    if not db.one("SELECT 1 FROM projects WHERE id=?", (body.project_id,)): raise HTTPException(404, "project not found")
    return ResearchRepository(db).experiment(body.project_id, body.hypothesis, body.design)
@app.post("/api/projects/{project_id}/next-tasks")
def next_tasks(project_id: str, principal: Principal = Depends(principal_from_header)):
    require_write(principal)
    if not db.one("SELECT 1 FROM projects WHERE id=?", (project_id,)): raise HTTPException(404, "project not found")
    return AutonomousPlanner(db).create_next_tasks(project_id, [{"title":"Collect evidence","agent_id":"researcher","priority":1.0},{"title":"Challenge evidence","agent_id":"skeptic","priority":0.9},{"title":"Audit evidence","agent_id":"evidence-auditor","priority":0.9}])
@app.get("/")
def dashboard(): return HTMLResponse((Path(__file__).parent / "dashboard.html").read_text())
