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
