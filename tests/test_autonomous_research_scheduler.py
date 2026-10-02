from app.database import Database
from app.workflow import ResearchCycle
from app.autonomous_research_scheduler import AutonomousResearchScheduler

def test_scheduler_starts_low_risk_digital_research_without_approval(tmp_path):
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
    assert result["status"]=="TASK_CREATED"
    assert result["candidate"]["kind"]=="RESEARCH"
    assert "Clarify the replication outcome" in result["candidate"]["title"]
