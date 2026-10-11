from app.database import Database
from app.workflow import ResearchCycle
from app.autonomous_research_lab import AutonomousResearchLab


def _mock_retrieval(monkeypatch, records=True):
    from app.scientific_retrieval import ScientificRetrievalService
    monkeypatch.setattr(
        ScientificRetrievalService, "_pubmed",
        lambda self, query, limit: ([{
            "record_id": "pubmed:12345",
            "doi": "10.1000/hds-test",
            "title": "Self-regulation and goal pursuit",
            "url": "https://pubmed.ncbi.nlm.nih.gov/12345/",
            "authors": "Example A",
            "year": 2024,
            "abstract": "This is a synthetic test abstract, not a real scientific source.",
            "source_type": "PUBMED",
            "provider": "pubmed",
        }] if records else []),
    )
    monkeypatch.setattr(ScientificRetrievalService, "_crossref", lambda self, query, limit: [])


def test_autonomous_research_lab_discovers_and_starts_without_founder_approval(tmp_path, monkeypatch):
    _mock_retrieval(monkeypatch)
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


def test_autonomous_research_lab_keeps_scientific_admission_gated(tmp_path, monkeypatch):
    _mock_retrieval(monkeypatch)
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
        "NO_EXECUTABLE_TASK",
    }
    rows=db.all("SELECT status FROM claims WHERE project_id=?", (project["id"],))
    assert all(row["status"] != "SUPPORTED" for row in rows)



def test_autonomous_research_lab_blocks_execution_when_retrieval_returns_no_sources(tmp_path, monkeypatch):
    _mock_retrieval(monkeypatch, records=False)
    db=Database(str(tmp_path/"autonomous-no-sources.db"))
    project=ResearchCycle(db).run("Autonomous research no sources")["project"]
    db.execute("UPDATE projects SET status='RUNNING' WHERE id=?",(project["id"],))

    result=AutonomousResearchLab(db).run_once(project["id"],"What is self-discipline?")

    assert result["status"]=="BLOCKED_NO_SOURCES"
    assert result["retrieval"]["retrieval_run"]["result_count"]==0
    assert result["result"]["status"]=="BLOCKED_NO_SOURCES"
    task=db.one("SELECT status FROM tasks WHERE id=?",(result["task_id"],))
    assert task["status"]=="BLOCKED"
    run=db.one("SELECT status,completed_at FROM autonomous_lab_runs WHERE id=?",(result["run_id"],))
    assert run["status"]=="BLOCKED_NO_SOURCES"
    assert run["completed_at"]


def test_autonomous_research_lab_executes_only_the_created_research_task(tmp_path, monkeypatch):
    _mock_retrieval(monkeypatch)
    db=Database(str(tmp_path/"autonomous-task-scope.db"))
    project=ResearchCycle(db).run("Autonomous task scope")["project"]
    db.execute("UPDATE projects SET status='RUNNING' WHERE id=?",(project["id"],))
    from app.orchestrator import CompanyOrchestrator
    calls=[]
    original=CompanyOrchestrator.execute_next
    def capture(self, project_id, task_id=None):
        calls.append((project_id,task_id))
        return original(self,project_id,task_id=task_id)
    monkeypatch.setattr(CompanyOrchestrator,"execute_next",capture)

    result=AutonomousResearchLab(db).run_once(project["id"],"What is self-discipline?")

    assert calls==[(project["id"],result["task_id"])]
