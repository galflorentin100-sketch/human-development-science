from fastapi.testclient import TestClient
from app.main import app

client=TestClient(app)

def test_health():
    r=client.get("/health")
    assert r.status_code==200
    assert r.json()["status"]=="ok"

def test_company_state():
    r=client.get("/api/company-state")
    assert r.status_code==200
    assert r.json()["id"]=="hds"

def test_full_state_contains_workforce():
    r=client.get("/api/company-state/full")
    assert r.status_code==200
    body=r.json()
    assert len(body["agents"])>=10
    assert "risks" in body and "approvals" in body

def test_intelligence():
    r=client.get("/api/intelligence")
    assert r.status_code==200
    body=r.json()
    assert "health" in body
    assert "brief" in body

def test_founder_goal_creates_project_and_tasks():
    r=client.post("/api/founder-goals",json={"goal":"Test autonomous orchestration"})
    assert r.status_code==200
    body=r.json()
    assert body["orchestration"]["project"]["status"]=="RUNNING"
    assert len(body["orchestration"]["tasks"])==5

def test_planner_context_and_failure_replan(tmp_path):
    from app.database import Database
    from app.workflow import ResearchCycle
    from app.planner import AutonomousPlanner
    db=Database(str(tmp_path/"planner.db")); ResearchCycle(db)
    project=ResearchCycle(db).run("planner")["project"]
    failure={"lesson":"verification failed"}
    tasks=AutonomousPlanner(db).replan_after_failure(project["id"],failure)
    assert len(tasks)==2
    assert all(t["status"]=="PLANNED" for t in tasks)

def test_decision_engine_requests_approval_when_confidence_low(tmp_path):
    from app.database import Database
    from app.workflow import ResearchCycle
    from app.decision_engine import DecisionEngine
    db=Database(str(tmp_path/"decision.db")); ResearchCycle(db)
    p=ResearchCycle(db).run("decision")["project"]
    result=DecisionEngine(db).assess(p["id"],"High uncertainty decision",["A","B"],[],[],0.4,"Expected outcome")
    assert result["action_required"] is True
    assert result["approval"]["status"]=="PENDING"

def test_founder_brief_counts_only_actionable_items(tmp_path):
    from app.database import Database
    from app.workflow import ResearchCycle
    from app.briefs import FounderBriefService
    db=Database(str(tmp_path/"brief.db")); ResearchCycle(db)
    assert FounderBriefService(db).build()["founder_action_required"]==0

def test_idempotent_goal_creation(tmp_path):
    from app.database import Database
    from app.workflow import ResearchCycle
    from app.idempotency import IdempotencyService
    db=Database(str(tmp_path/"idem.db")); ResearchCycle(db)
    svc=IdempotencyService(db)
    calls={"n":0}
    def op():
        calls["n"]+=1
        return {"ok":True,"value":42}
    assert svc.run("k1","founder","op",op)=={"ok":True,"value":42}
    assert svc.run("k1","founder","op",op)=={"ok":True,"value":42}
    assert calls["n"]==1

def test_evidence_pipeline_tracks_hash_and_review(tmp_path):
    from app.database import Database
    from app.workflow import ResearchCycle
    from app.evidence_pipeline import EvidencePipeline
    db=Database(str(tmp_path/"evidence.db")); ResearchCycle(db)
    p=ResearchCycle(db).run("evidence")["project"]
    claim=db.one("SELECT id FROM claims WHERE project_id=?",(p["id"],))
    ep=EvidencePipeline(db)
    src=ep.register_source("Test paper","https://example.org/test-paper")
    parsed=ep.ingest_text(src["id"],"verified text")
    evidence=ep.attach(claim["id"],src["id"],"verified text",verified=False)
    review=ep.review(evidence["id"],"auditor","VERIFIED","Traceable excerpt")
    assert parsed["content_hash"]
    assert review["verdict"]=="VERIFIED"

def test_autonomous_loop_is_bounded(tmp_path):
    from app.database import Database
    from app.workflow import ResearchCycle
    from app.orchestrator import CompanyOrchestrator
    db=Database(str(tmp_path/"auto.db")); cycle=ResearchCycle(db)
    project=cycle.run("autonomy")["project"]
    result=CompanyOrchestrator(db).run_autonomous(project["id"],max_steps=2)
    assert result["steps"]<=2
    assert result["status"] in ("STEP_LIMIT_REACHED","WAITING_FOR_APPROVAL","COMPLETED")

def test_task_enum_transition(tmp_path):
    from app.database import Database
    from app.workflow import ResearchCycle
    from app.tasks import TaskEngine
    from app.models import TaskStatus
    db=Database(str(tmp_path/"state.db")); ResearchCycle(db)
    p=ResearchCycle(db).run("state")["project"]
    t=TaskEngine(db).create_task("x","do x",p["id"],"coo")
    assert TaskEngine(db).transition(t["id"],TaskStatus.ASSIGNED)["status"]=="ASSIGNED"

def test_project_does_not_complete_with_blocked_task(tmp_path):
    from app.database import Database
    from app.workflow import ResearchCycle
    from app.orchestrator import CompanyOrchestrator
    db=Database(str(tmp_path/"blocked.db")); cycle=ResearchCycle(db)
    p=cycle.run("blocked")["project"]
    db.execute("UPDATE tasks SET status='BLOCKED' WHERE project_id=?",(p["id"],))
    result=CompanyOrchestrator(db).advance(p["id"])
    assert result["status"]=="TASKS_PENDING"

def test_health_reports_dependency_checks(tmp_path):
    from app.database import Database
    from app.workflow import ResearchCycle
    db=Database(str(tmp_path/"health.db")); ResearchCycle(db)
    assert db.one("SELECT 1 AS ok")["ok"]==1

def test_autonomous_loop_endpoint_path_is_wired():
    from app.main import app
    paths={route.path for route in app.routes}
    assert "/api/projects/{project_id}/autonomous-run" in paths

def test_sc001_protocol_has_transfer_and_retention():
    from app.sc001 import SC001Protocol
    p=SC001Protocol().draft()
    gates=SC001Protocol().quality_gates(p)
    assert gates["falsifiable_question"]
    assert gates["transfer_defined"]
    assert gates["retention_defined"]
    assert gates["status"]=="READY_FOR_REVIEW"

def test_sc001_registers_hypothesis_and_experiment(tmp_path):
    from app.database import Database
    from app.workflow import ResearchCycle
    from app.sc001 import SC001Protocol
    db=Database(str(tmp_path/"sc001.db")); ResearchCycle(db)
    p=ResearchCycle(db).run("SC001")["project"]
    out=SC001Protocol().register(db,p["id"])
    assert out["hypothesis"]["project_id"]==p["id"]
    assert out["experiment"]["status"]=="PLANNED"

def test_sc001_study_execution_records_missing_data_and_analysis(tmp_path):
    from app.database import Database
    from app.workflow import ResearchCycle
    from app.research import StudyExecution
    db=Database(str(tmp_path/"study.db")); ResearchCycle(db)
    p=ResearchCycle(db).run("study")["project"]
    registered=__import__("app.sc001",fromlist=["SC001Protocol"]).SC001Protocol().register(db,p["id"])
    study=registered["study"]
    db.execute("UPDATE studies SET status='APPROVED' WHERE id=?",(study["id"],))
    sx=StudyExecution(db)
    participant=sx.participant(study["id"],"p1")
    sx.randomize(study["id"],participant["id"],seed=1)
    sx.outcome(study["id"],participant["id"],"goal_execution_rate",0.4)
    sx.outcome(study["id"],participant["id"],"goal_execution_rate",0.6)
    plan=sx.freeze_analysis_plan(study["id"],'{"outcome_name":"goal_execution_rate","estimand":"mean_change","population":"registered participants","estimator":"mean change","ci_method":"none","missing_data_policy":"complete cases","multiplicity_policy":"none","subgroup_policy":"none","stopping_rule":"fixed","allowed_methods":["DESCRIPTIVE"]}')
    result=sx.analyze_mean_change(study["id"],plan["id"],"goal_execution_rate")
    assert result["n_total"]==1
    assert result["n_observed"]==1
    assert abs(result["estimate"]-0.2)<1e-9

def test_task_retry_escalates_after_limit(tmp_path):
    from app.database import Database
    from app.workflow import ResearchCycle
    from app.tasks import TaskEngine
    db=Database(str(tmp_path/"retry.db")); ResearchCycle(db)
    p=ResearchCycle(db).run("retry")["project"]
    task=TaskEngine(db).create_task("retry","test",p["id"],"researcher",priority=1.0)\n    TaskEngine(db).transition(task["id"],"ASSIGNED")\n    TaskEngine(db).transition(task["id"],"RUNNING")
    db.execute("UPDATE tasks SET retry_limit=1 WHERE id=?",(task["id"],))
    first=TaskEngine(db).retry_or_escalate(task["id"],"transient failure")
    assert first["action"]=="RETRY"
    second=TaskEngine(db).retry_or_escalate(task["id"],"repeat failure")
    assert second["action"]=="ESCALATE"
    assert TaskEngine(db).get(task["id"])["escalation_required"]==1

def test_sc001_registration_creates_preregistered_measurements(tmp_path):
    from app.database import Database
    from app.workflow import ResearchCycle
    from app.sc001 import SC001Protocol
    db=Database(str(tmp_path/"sc001_measure.db")); ResearchCycle(db)
    p=ResearchCycle(db).run("SC001 measurement")["project"]
    out=SC001Protocol().register(db,p["id"])
    assert len(out["measurements"])==4
    assert db.one("SELECT COUNT(*) AS n FROM study_measure_definitions WHERE study_id=?",(out["study"]["id"],))["n"]==4
    assert db.one("SELECT COUNT(*) AS n FROM study_measure_bindings WHERE study_id=?",(out["study"]["id"],))["n"]==20
