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
    evidence=ep.attach(claim["id"],src["id"],"verified text",verified=True)
    review=ep.review(evidence["id"],"auditor","ACCEPT","Traceable excerpt")
    assert parsed["content_hash"]
    assert review["verdict"]=="ACCEPT"

def test_autonomous_loop_is_bounded(tmp_path):
    from app.database import Database
    from app.workflow import ResearchCycle
    from app.orchestrator import CompanyOrchestrator
    db=Database(str(tmp_path/"auto.db")); cycle=ResearchCycle(db)
    project=cycle.run("autonomy")["project"]
    result=CompanyOrchestrator(db).run_autonomous(project["id"],max_steps=2)
    assert result["steps"]<=2
    assert result["status"] in ("STEP_LIMIT_REACHED","WAITING_FOR_APPROVAL","COMPLETED")
