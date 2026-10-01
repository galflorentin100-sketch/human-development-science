from app.database import Database
from app.workflow import ResearchCycle
from app.autonomous_research_lab import AutonomousResearchLab


def test_autonomous_research_lab_discovers_and_starts_without_founder_approval(tmp_path):
    db=Database(str(tmp_path/"autonomous-lab.db"))
    project=ResearchCycle(db).run("Autonomous research lab")["project"]
    db.execute("UPDATE projects SET status='RUNNING' WHERE id=?",(project["id"],))
    result=AutonomousResearchLab(db).discover(project["id"])
    assert result["autonomous"] is True
    assert result["candidate_count"] >= 1

    started=AutonomousResearchLab(db).run_once(project["id"], result["candidates"][0]["question"])
    assert started["run_id"]
    assert started["workspace_id"]
    assert started["task_id"]
    assert started["status"] not in {"PROJECT_NOT_EXECUTABLE", "NO_RESEARCH_CANDIDATE"}


def test_autonomous_research_lab_keeps_scientific_admission_gated(tmp_path):
    db=Database(str(tmp_path/"autonomous-gates.db"))
    project=ResearchCycle(db).run("Autonomous gates")["project"]
    db.execute("UPDATE projects SET status='RUNNING' WHERE id=?",(project["id"],))
    lab=AutonomousResearchLab(db)
    item=lab.run_once(project["id"], "Can a new training mechanism improve persistence?")
    assert item["status"] in {
        "COMPLETED",
        "WAITING_FOR_OUTPUT_REVIEW",
        "EXECUTION_FAILED",
        "EXECUTION_PREFLIGHT_FAILED",
        "RETRY_SCHEDULED",
    }
    rows=db.all("SELECT status FROM claims WHERE project_id=?", (project["id"],))
    assert all(row["status"] != "SUPPORTED" for row in rows)
