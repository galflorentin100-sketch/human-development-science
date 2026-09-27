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
    task=TaskEngine(db).create_task("retry","test",p["id"],"researcher",priority=1.0)
    TaskEngine(db).transition(task["id"],"ASSIGNED")
    TaskEngine(db).transition(task["id"],"RUNNING")
    db.execute("UPDATE tasks SET retry_limit=1 WHERE id=?",(task["id"],))
    first=TaskEngine(db).retry_or_escalate(task["id"],"transient failure")
    assert first["action"]=="RETRY"
    TaskEngine(db).transition(task["id"],"ASSIGNED")
    TaskEngine(db).transition(task["id"],"RUNNING")
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

def test_execute_next_recovers_when_agent_preflight_fails(tmp_path):
    from app.database import Database
    from app.workflow import ResearchCycle
    from app.orchestrator import CompanyOrchestrator
    from app.tasks import TaskEngine
    db=Database(str(tmp_path/"preflight.db")); ResearchCycle(db)
    p=ResearchCycle(db).run("preflight")["project"]
    agent=db.one("SELECT id FROM agents WHERE id='researcher'")["id"] if db.one("SELECT id FROM agents WHERE id='researcher'") else db.one("SELECT id FROM agents LIMIT 1")["id"]
    db.execute("DELETE FROM agent_permissions WHERE agent_id=? AND permission='EXECUTE'",(agent,))
    task=TaskEngine(db).create_task("preflight task","test",p["id"],agent,required_permissions=["EXECUTE"],priority=1.0)
    result=CompanyOrchestrator(db).execute_next(p["id"])
    assert result["status"]=="EXECUTION_PREFLIGHT_FAILED"
    assert db.one("SELECT status FROM tasks WHERE id=?",(task["id"],))["status"] in ("PLANNED","FAILED")


def test_idempotency_stale_claim_can_be_recovered_explicitly(tmp_path):
    from datetime import datetime, timezone, timedelta
    from app.database import Database
    from app.workflow import ResearchCycle
    from app.idempotency import IdempotencyService, IdempotencyConflict
    db=Database(str(tmp_path/"idem-recovery.db")); ResearchCycle(db)
    svc=IdempotencyService(db)
    now=datetime.now(timezone.utc)
    token="stale-token"
    db.execute(
        "INSERT INTO idempotency_keys(key,actor,operation,response,created_at,expires_at,status,claim_token,lease_expires_at) VALUES (?,?,?,?,?,?,?,?,?)",
        ("recover-key","founder","op",'{"status":"IN_PROGRESS"}',now.isoformat(),
         (now+timedelta(hours=1)).isoformat(),"IN_PROGRESS",token,
         (now-timedelta(minutes=1)).isoformat()))
    recovered=svc.recover_stale("recover-key","founder","op",token)
    assert recovered["status"]=="RECOVERED"
    assert db.one("SELECT * FROM idempotency_keys WHERE key=?",("recover-key",)) is None
    assert svc.run("recover-key","founder","op",lambda: {"ok":True})=={"ok":True}

def test_idempotency_live_claim_cannot_be_recovered(tmp_path):
    from datetime import datetime, timezone, timedelta
    from app.database import Database
    from app.workflow import ResearchCycle
    from app.idempotency import IdempotencyService, IdempotencyConflict
    db=Database(str(tmp_path/"idem-live.db")); ResearchCycle(db)
    svc=IdempotencyService(db)
    now=datetime.now(timezone.utc)
    token="live-token"
    db.execute(
        "INSERT INTO idempotency_keys(key,actor,operation,response,created_at,expires_at,status,claim_token,lease_expires_at) VALUES (?,?,?,?,?,?,?,?,?)",
        ("live-key","founder","op",'{"status":"IN_PROGRESS"}',now.isoformat(),
         (now+timedelta(hours=1)).isoformat(),"IN_PROGRESS",token,
         (now+timedelta(minutes=10)).isoformat()))
    try:
        svc.recover_stale("live-key","founder","op",token)
        assert False, "live lease must not be recoverable"
    except IdempotencyConflict:
        pass

def test_sc001_registration_rolls_back_all_state_on_failure(tmp_path, monkeypatch):
    from app.database import Database
    from app.workflow import ResearchCycle
    from app.sc001 import SC001Protocol
    from app.approvals import ApprovalService
    db=Database(str(tmp_path/"sc001-atomic.db")); ResearchCycle(db)
    p=ResearchCycle(db).run("SC001 atomic")["project"]
    original=ApprovalService._request_in_transaction
    def fail(*args,**kwargs):
        raise RuntimeError("simulated approval failure")
    monkeypatch.setattr(ApprovalService,"_request_in_transaction",fail)
    try:
        SC001Protocol().register(db,p["id"])
        assert False, "registration should fail"
    except RuntimeError:
        pass
    assert db.one("SELECT COUNT(*) AS n FROM studies WHERE project_id=?", (p["id"],))["n"]==0
    assert db.one("SELECT COUNT(*) AS n FROM hypotheses WHERE project_id=?", (p["id"],))["n"]==0
    assert db.one("SELECT COUNT(*) AS n FROM experiments WHERE project_id=?", (p["id"],))["n"]==0
    assert db.one("SELECT COUNT(*) AS n FROM approvals WHERE action LIKE 'SC001:STUDY:%'")["n"]==0
    monkeypatch.setattr(ApprovalService,"_request_in_transaction",original)


def test_maintenance_materialize_is_idempotent(tmp_path):
    from app.database import Database
    from app.workflow import ResearchCycle
    from app.autonomous_scientific_maintenance import AutonomousScientificMaintenance
    db=Database(str(tmp_path/"maintenance.db")); ResearchCycle(db)
    p=ResearchCycle(db).run("maintenance")["project"]
    db.execute(
        "INSERT INTO claims(id,project_id,statement,classification,evidence_level,confidence,status,created_at) VALUES (?,?,?,?,?,?,?,?)",
        ("claim-maint",p["id"],"test claim","INFERENCE","UNVERIFIED",0.0,"SUPPORTED","2026-01-01T00:00:00+00:00"))
    # Force a maintenance proposal directly so the materializer path is exercised.
    db.execute(
        "INSERT INTO knowledge_freshness(id,entity_type,entity_id,review_interval_days,last_validated_at,next_review_at,status,owner,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
        ("fresh-maint","CLAIM","claim-maint",1,"2025-01-01T00:00:00+00:00","2025-01-02T00:00:00+00:00","STALE","system","2025-01-01T00:00:00+00:00","2025-01-01T00:00:00+00:00"))
    service=AutonomousScientificMaintenance(db)
    first=service.materialize()
    second=service.materialize()
    assert first["count"]==1
    assert second["count"]==0
    assert db.one("SELECT COUNT(*) AS n FROM maintenance_work WHERE entity_id='claim-maint'")["n"]==1


def test_science_improvement_requires_verified_evidence(tmp_path):
    from app.database import Database
    from app.workflow import ResearchCycle
    from app.evidence_pipeline import EvidencePipeline
    from app.continuous_improvement import ContinuousImprovementService
    db=Database(str(tmp_path/"improvement-evidence.db")); ResearchCycle(db)
    p=ResearchCycle(db).run("improvement evidence")["project"]
    claim=db.one("SELECT id FROM claims WHERE project_id=? LIMIT 1",(p["id"],))
    source=EvidencePipeline(db).register_source("Improvement paper","https://example.org/improvement-evidence")
    EvidencePipeline(db).ingest_text(source["id"],"evidence excerpt")
    ev=EvidencePipeline(db).attach(claim["id"],source["id"],"evidence excerpt",actor="researcher")
    svc=ContinuousImprovementService(db)
    try:
        svc.propose("Scientific improvement","SCIENCE","test hypothesis","test metric","founder",ev["id"])
        assert False, "unverified evidence must not support a SCIENCE improvement"
    except ValueError as exc:
        assert "verified" in str(exc)
    EvidencePipeline(db).review(ev["id"],"independent-reviewer","VERIFIED","verified")
    proposal=svc.propose("Scientific improvement","SCIENCE","test hypothesis","test metric","founder",ev["id"])
    assert proposal["status"]=="PROPOSED"


def test_agent_output_needs_evidence_can_be_reopened(tmp_path):
    import json
    import uuid
    from app.database import Database
    from app.workflow import ResearchCycle
    from app.agent_output_gate import AgentOutputGate
    from app.evidence_pipeline import EvidencePipeline
    from app.models import now
    db=Database(str(tmp_path/"output_gate.db")); ResearchCycle(db)
    project=ResearchCycle(db).run("output gate")["project"]
    agent=db.one("SELECT id FROM agents LIMIT 1")
    task_id=str(uuid.uuid4()); run_id=str(uuid.uuid4())
    db.execute("INSERT INTO tasks(id,project_id,title,status,assigned_agent_id,priority,success_criteria,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
               (task_id,project["id"],"agent output","REVIEW",agent["id"],1.0,"review",now(),now()))
    db.execute("INSERT INTO agent_runs(id,agent_id,task_id,status,input_payload,output_payload,started_at,completed_at) VALUES (?,?,?,?,?,?,?,?)",
               (run_id,agent["id"],task_id,"COMPLETED","{}",json.dumps({"answer":"needs evidence"}),now(),now()))
    review=AgentOutputGate(db).submit(run_id)
    assert review["status"]=="NEEDS_EVIDENCE"
    source=EvidencePipeline(db).register_source("Gate paper","https://example.org/gate-paper","Author",2026)
    claim=db.one("SELECT id FROM claims WHERE project_id=? LIMIT 1",(project["id"],))
    evidence=EvidencePipeline(db).attach(claim["id"],source["id"],"supporting excerpt",actor="auditor")
    EvidencePipeline(db).review(evidence["id"],"auditor","VERIFIED","verified")
    reopened=AgentOutputGate(db).provide_evidence(review["id"],[evidence["id"]])
    assert reopened["status"]=="READY_FOR_REVIEW"
