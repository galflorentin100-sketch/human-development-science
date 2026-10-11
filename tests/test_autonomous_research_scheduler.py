from app.database import Database
from app.workflow import ResearchCycle
from app.autonomous_research_scheduler import AutonomousResearchScheduler
from app.scientific_retrieval import ScientificRetrievalService


def _mock_retrieval(monkeypatch):
    record = {
        "record_id": "pubmed:mock-1",
        "title": "Mock peer-reviewed research record",
        "url": "https://pubmed.ncbi.nlm.nih.gov/12345678/",
        "authors": "Test Author",
        "year": 2024,
        "source_type": "PAPER",
        "abstract": "This mock abstract exists only to test the retrieval pipeline.",
        "doi": "10.5555/hds.mock.1",
    }
    monkeypatch.setattr(ScientificRetrievalService, "_pubmed", lambda self, query, limit: [record])
    monkeypatch.setattr(ScientificRetrievalService, "_crossref", lambda self, query, limit: [])

def test_scheduler_starts_low_risk_digital_research_without_approval(tmp_path, monkeypatch):
    _mock_retrieval(monkeypatch)
    db=Database(str(tmp_path/"scheduler.db"))
    project=ResearchCycle(db).run("Autonomous scheduler")["project"]
    db.execute("UPDATE projects SET status='RUNNING' WHERE id=?",(project["id"],))
    db.execute(
        "INSERT INTO research_questions(id,project_id,question,status,created_at) VALUES (?,?,?,?,datetime('now'))",
        ("q-auto",project["id"],"What evidence gaps exist in a measurable human-development construct?","OPEN"),
    )
    result=AutonomousResearchScheduler(db).schedule_once(project["id"])
    assert result["status"]=="TASK_CREATED"
    assert result["task"]["assigned_agent_id"]
    assert result["retrieval"]["retrieval_run"]["result_count"] == 1
    assert result["task"]["status"] == "PLANNED"
    run=db.one("SELECT * FROM autonomous_research_runs WHERE id=?",(result["run_id"],))
    assert run["mode"]=="DIGITAL_RESEARCH"
    assert run["status"]=="TASK_CREATED"
    queue=db.one("SELECT status FROM hds_research_queue WHERE id=?",(result["queue_item_id"],))
    assert queue["status"]=="IN_PROGRESS"

def test_scheduler_does_not_execute_on_completed_project(tmp_path):
    db=Database(str(tmp_path/"scheduler-block.db"))
    project=ResearchCycle(db).run("Blocked scheduler")["project"]
    result=AutonomousResearchScheduler(db).schedule_once(project["id"])
    assert result["status"]=="PROJECT_NOT_EXECUTABLE"


def test_scheduler_consumes_generated_replication_gap(tmp_path):
    from app.experiment_engine import ExperimentEngine
    from app.experiment_safety import ExperimentSafetyReviewer
    from app.replication_engine import ReplicationEngine
    db=Database(str(tmp_path/"scheduler-gap.db"))
    project=ResearchCycle(db).run("Scheduler gap")["project"]
    db.execute("UPDATE projects SET status='RUNNING' WHERE id=?",(project["id"],))
    e=ExperimentEngine(db)
    exp=e.create(project["id"],"Original question","Original hypothesis","design","population","intervention","comparison","outcome",'{"outcome":"outcome"}')
    e.preregister(exp["id"])
    ExperimentSafetyReviewer(db).review(exp["id"],"ACCEPT","digital test review","reviewer")
    e.start(exp["id"]); e.record_result(exp["id"],"descriptive result","descriptive interpretation"); e.complete(exp["id"])
    rp=ReplicationEngine(db).propose(project["id"],exp["id"],"independent confirmation")
    ReplicationEngine(db).ready(rp["id"]); ReplicationEngine(db).record_result(rp["id"],"descriptive replication result","requires review")
    result=AutonomousResearchScheduler(db).schedule_once(project["id"])
    assert result["status"]=="GOVERNED_REVIEW_REQUIRED"
    assert result["candidate"]["kind"]=="RESEARCH"
    assert result["candidate"]["action_type"]=="REPLICATION_REVIEW"
    assert result["candidate"]["route"]["execution_authorized"] is False
    assert "Clarify the replication outcome" in result["candidate"]["title"]


def test_scheduler_reuses_generated_gap_queue_item_for_digital_research(tmp_path, monkeypatch):
    _mock_retrieval(monkeypatch)
    db=Database(str(tmp_path/"scheduler-generated-gap.db"))
    project=ResearchCycle(db).run("Generated gap scheduler")["project"]
    db.execute("UPDATE projects SET status='RUNNING' WHERE id=?",(project["id"],))

    question="What evidence gaps exist in a measurable human-development construct?"
    db.execute(
        "INSERT INTO research_questions(id,project_id,question,status,trigger_type,priority,created_at) "
        "VALUES (?,?,?,?,?,?,datetime('now'))",
        ("q-generated",project["id"],question,"OPEN","AUTONOMOUS_GAP_DETECTOR",80),
    )
    from app.research_queue import ResearchQueue
    generated=ResearchQueue(db).propose(
        project["id"],question,"Gap detector proposal","AUTONOMOUS_GAP_DETECTOR"
    )
    result=AutonomousResearchScheduler(db).schedule_once(project["id"])

    assert result["status"]=="TASK_CREATED"
    assert result["queue_item_id"]==generated["id"]
    queue=db.one("SELECT * FROM hds_research_queue WHERE id=?",(generated["id"],))
    assert queue["status"]=="IN_PROGRESS"
    assert queue["trigger_type"]=="AUTONOMOUS_GAP_DETECTOR"

def test_run_and_execute_once_executes_only_prepared_task_and_stops_at_review(tmp_path, monkeypatch):
    _mock_retrieval(monkeypatch)
    from app.orchestrator import CompanyOrchestrator
    captured={}
    def fake_execute(self, project_id, task_id=None):
        captured["project_id"]=project_id
        captured["task_id"]=task_id
        return {"status":"WAITING_FOR_OUTPUT_REVIEW","output_review":{"status":"READY_FOR_REVIEW"}}
    monkeypatch.setattr(CompanyOrchestrator,"execute_next",fake_execute)
    db=Database(str(tmp_path/"scheduler-execute-once.db"))
    project=ResearchCycle(db).run("Autonomous research execution")["project"]
    db.execute("UPDATE projects SET status='RUNNING' WHERE id=?",(project["id"],))
    db.execute(
        "INSERT INTO research_questions(id,project_id,question,status,created_at) VALUES (?,?,?,?,datetime('now'))",
        ("q-execute-once",project["id"],"What evidence gaps exist in a measurable human-development construct?","OPEN"),
    )

    result=AutonomousResearchScheduler(db).run_and_execute_once(project["id"],actor="test-owner")

    assert captured["project_id"]==project["id"]
    assert captured["task_id"]==result["task"]["id"]
    assert result["status"]=="WAITING_FOR_OUTPUT_REVIEW"
    assert result["research_completed"] is False
    run=db.one("SELECT status FROM autonomous_research_runs WHERE id=?",(result["run_id"],))
    assert run["status"]=="WAITING_FOR_OUTPUT_REVIEW"
