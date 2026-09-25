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
from app.science import ScientificRegistry
from app.scientific_ai import ScientificAIGuard
from app.measurement import MeasurementRegistry
from app.claim_state import ClaimStateService
from app.scientific_analysis import ScientificAnalysisEngine

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
class ConstructRequest(BaseModel):
    name: str = Field(min_length=1, max_length=300); definition: str = Field(min_length=1, max_length=5000); construct_type: str = "CAPABILITY"; project_id: str | None = None
class MeasureRequest(BaseModel):
    construct_id: str; name: str = Field(min_length=1); operational_definition: str = Field(min_length=1); method: str = Field(min_length=1); unit: str | None = None; reliability_note: str = ""; validity_note: str = ""
class InterventionRequest(BaseModel):
    name: str = Field(min_length=1); rationale: str = Field(min_length=1); mechanism: str = Field(min_length=1); evidence_level: str; dosage: str = Field(min_length=1); population: str = Field(min_length=1); target_construct_id: str | None = None
class StudyParticipantRequest(BaseModel):
    study_id: str; external_ref: str = Field(min_length=1, max_length=200); consent_status: str = "CONSENTED"
class StudyOutcomeRequest(BaseModel):
    study_id: str; participant_id: str; outcome_name: str = Field(min_length=1); value: float | None = None; unit: str | None = None; session_id: str | None = None; missing_reason: str | None = None; observation_type: str = "TRAINING"; measure_id: str | None = None; timepoint: str | None = None

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
def state(principal: Principal = Depends(principal_from_header)):
    require_read(principal)
    return db.one("SELECT * FROM companies WHERE id='hds'")
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
    require_permission(principal, "EXECUTE"); return AutonomousLoop(db).run(project_id)
@app.post("/api/projects/{project_id}/decide-next")
def decide_next(project_id: str, principal: Principal = Depends(principal_from_header)):
    require_permission(principal, "EXECUTE"); return CompanyOrchestrator(db).decide_next(project_id)
@app.post("/api/projects/{project_id}/execute-next")
def execute_next(project_id: str, principal: Principal = Depends(principal_from_header)):
    require_permission(principal, "EXECUTE"); return CompanyOrchestrator(db).execute_next(project_id)
@app.post("/api/projects/{project_id}/advance")
def advance_project(project_id: str, principal: Principal = Depends(principal_from_header)):
    require_permission(principal, "EXECUTE"); return CompanyOrchestrator(db).advance(project_id)
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
class InterpretationRequest(BaseModel):
    text: str = Field(min_length=1, max_length=10000)
    evidence_refs: list[str] = []
    causal_design: bool = False
    retention_observed: bool = False
    transfer_observed: bool = False

@app.post("/api/science/interpretation/validate")
def validate_scientific_interpretation(req: InterpretationRequest, principal: Principal = Depends(principal_from_header)):
    require_write(principal)
    return ScientificAIGuard().validate_interpretation(
        req.text,
        evidence_refs=tuple(req.evidence_refs),
        causal_design=req.causal_design,
        retention_observed=req.retention_observed,
        transfer_observed=req.transfer_observed,
    ).__dict__


@app.post("/api/science/claims/{claim_id}/knowledge-version")
def create_knowledge_version(claim_id: str, rationale: str, principal: Principal = Depends(principal_from_header)):
    require_write(principal)
    from app.claim_state import ClaimStateService
    return ClaimStateService(db).knowledge_version(claim_id, principal.user_id, rationale)

@app.get("/api/science/claims/{claim_id}/knowledge-history")
def knowledge_history(claim_id: str, principal: Principal = Depends(principal_from_header)):
    require_read(principal)
    from app.claim_state import ClaimStateService
    return ClaimStateService(db).knowledge_history(claim_id)

@app.post("/api/science/findings")
def create_research_finding(payload: dict, principal: Principal = Depends(principal_from_header)):
    require_write(principal)
    from app.research import ResearchFindingService
    return ResearchFindingService(db).create(
        payload["project_id"],payload["statement"],payload.get("classification","HYPOTHESIS"),
        payload.get("source_type","OBSERVATION"),payload.get("source_id"),
        payload.get("evidence_refs",()),payload.get("interpretation"),principal.user_id)

@app.post("/api/science/findings/{finding_id}/review")
def review_research_finding(finding_id: str, payload: dict, principal: Principal = Depends(principal_from_header)):
    require_write(principal)
    from app.research import ResearchFindingService
    return ResearchFindingService(db).review(finding_id,principal.user_id,payload["decision"],payload["rationale"])

@app.get("/api/science/projects/{project_id}/findings")
def list_research_findings(project_id: str, status: str | None = None, principal: Principal = Depends(principal_from_header)):
    require_read(principal)
    from app.research import ResearchFindingService
    return ResearchFindingService(db).list(project_id,status)

@app.get("/api/science/evidence/{evidence_id}/resolution")
def evidence_resolution(evidence_id: str, principal: Principal = Depends(principal_from_header)):
    require_read(principal)
    from app.evidence_pipeline import EvidencePipeline
    return EvidencePipeline(db).resolve(evidence_id)

@app.get("/api/science/claims/{claim_id}/evidence-resolution")
def claim_evidence_resolution(claim_id: str, principal: Principal = Depends(principal_from_header)):
    require_read(principal)
    from app.evidence_pipeline import EvidencePipeline
    return EvidencePipeline(db).claim_evidence_state(claim_id)

@app.get("/api/studies/{study_id}/analysis/{analysis_plan_id}/audit")

def study_analysis_audit(study_id: str, analysis_plan_id: str, outcome_name: str | None = None, principal: Principal = Depends(principal_from_header)):
    require_read(principal)
    return ScientificAnalysisEngine(db).analysis_audit(study_id, analysis_plan_id, outcome_name)

@app.get("/api/studies/{study_id}/analysis/{analysis_plan_id}/missingness")
def study_missingness(study_id: str, analysis_plan_id: str, outcome_name: str, principal: Principal = Depends(principal_from_header)):
    require_read(principal)
    ScientificAnalysisEngine(db)._plan(study_id, analysis_plan_id)
    return ScientificAnalysisEngine(db).missingness_report(study_id, outcome_name)

@app.post("/api/studies/{study_id}/analysis/{analysis_plan_id}/retention")
def study_retention_analysis(study_id: str, analysis_plan_id: str, body: dict, principal: Principal = Depends(principal_from_header)):
    require_read(principal)
    return ScientificAnalysisEngine(db).longitudinal_retention_analysis(study_id, analysis_plan_id, body["outcome_name"])

@app.post("/api/studies/{study_id}/analysis/{analysis_plan_id}/inferential")
def inferential_study_analysis(study_id: str, analysis_plan_id: str, body: dict, principal: Principal = Depends(principal_from_header)):
    require_read(principal)
    return ScientificAnalysisEngine(db).inferential_randomized_arm_analysis(study_id, analysis_plan_id, body["outcome_name"])

@app.post("/api/studies/{study_id}/analysis/{analysis_plan_id}/randomized")
def analyze_randomized_study(study_id: str, analysis_plan_id: str, body: dict, principal: Principal = Depends(principal_from_header)):
    require_read(principal)
    return ScientificAnalysisEngine(db).randomized_arm_analysis(study_id, analysis_plan_id, body["outcome_name"])

@app.post("/api/studies/{study_id}/analysis/{analysis_plan_id}")
def analyze_study(study_id: str, analysis_plan_id: str, body: dict, principal: Principal = Depends(principal_from_header)):
    require_read(principal)
    return ScientificAnalysisEngine(db).analyze(study_id, analysis_plan_id, body["outcome_name"])

@app.post("/api/science/claims/{claim_id}/transition")
def transition_claim(claim_id: str, body: dict, principal: Principal = Depends(principal_from_header)):
    require_write(principal)
    return ClaimStateService(db).transition(claim_id, body["status"], principal.subject, body["rationale"], body.get("evidence_id"))

@app.get("/api/science/claims/{claim_id}/evidence-state")
def claim_evidence_state(claim_id: str, principal: Principal = Depends(principal_from_header)):
    require_read(principal)
    return ClaimStateService(db).evidence_state(claim_id)

@app.post("/api/science/constructs")
def science_construct(body: ConstructRequest, principal: Principal = Depends(principal_from_header)):
    require_write(principal)
    return ScientificRegistry(db).construct(body.name, body.definition, body.construct_type, body.project_id)

@app.post("/api/science/measures")
def science_measure(body: MeasureRequest, principal: Principal = Depends(principal_from_header)):
    require_write(principal)
    return ScientificRegistry(db).measure(body.construct_id, body.name, body.operational_definition, body.method, body.unit, body.reliability_note, body.validity_note)

@app.post("/api/science/interventions")
def science_intervention(body: InterventionRequest, principal: Principal = Depends(principal_from_header)):
    require_write(principal)
    return ScientificRegistry(db).intervention(body.name, body.rationale, body.mechanism, body.evidence_level, body.dosage, body.population, body.target_construct_id)

@app.get("/api/science/ai-constraints")
def science_ai_constraints(principal: Principal = Depends(principal_from_header)):
    require_read(principal)
    return {"constraints": ScientificAIGuard().prompt_constraints()}

@app.post("/api/research/run")
def research_run(body: ResearchRequest, principal: Principal = Depends(principal_from_header)):
    require_permission(principal, "EXECUTE"); return cycle.run(body.question)
@app.post("/api/studies/participants")
def study_participant(body: StudyParticipantRequest, principal: Principal = Depends(principal_from_header)):
    require_write(principal); return StudyExecution(db).participant(body.study_id, body.external_ref, body.consent_status)
@app.post("/api/studies/outcomes")
def study_outcome(body: StudyOutcomeRequest, principal: Principal = Depends(principal_from_header)):
    require_write(principal); return StudyExecution(db).outcome(body.study_id, body.participant_id, body.outcome_name, body.value, body.unit, body.session_id, body.missing_reason, body.observation_type, body.measure_id, body.timepoint)
@app.post("/api/studies/measures")
def study_measure(body: dict, principal: Principal = Depends(principal_from_header)):
    require_write(principal)
    return MeasurementRegistry(db).define(body["study_id"], body["name"], body["operational_definition"], body["method"], body["scale_type"], body.get("unit"), body.get("reliability_note",""), body.get("validity_note",""), body.get("construct_id"))

@app.post("/api/studies/measure-bindings")
def study_measure_binding(body: dict, principal: Principal = Depends(principal_from_header)):
    require_write(principal)
    return MeasurementRegistry(db).bind(body["study_id"], body["measure_id"], body["observation_type"], body["timepoint"], body.get("required",True))

@app.post("/api/studies/{study_id}/start")
def study_start(study_id: str, principal: Principal = Depends(principal_from_header)):
    require_permission(principal, "EXECUTE")
    return StudyExecution(db).start(study_id)

@app.post("/api/studies/{study_id}/complete")
def study_complete(study_id: str, principal: Principal = Depends(principal_from_header)):
    require_permission(principal, "EXECUTE")
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
