from app.database import Database
from app.registry import find_agent
from app.workflow import ResearchCycle

def test_registry_discovers_researcher():
    assert find_agent("literature-search").id == "researcher"

def test_research_cycle_persists_auditable_outputs(tmp_path):
    cycle = ResearchCycle(Database(str(tmp_path / "test.db")))
    result = cycle.run("Research whether self-regulation can be trained and transferred to daily behavior.")
    assert result["project"]["status"] == "COMPLETED"
    assert len(result["tasks"]) == 5
    assert result["claims"][0]["classification"] == "SUPPORTED"
    assert len(result["sources"]) == 3
    assert result["questions"][-1]["status"] == "OPEN"
    assert "NO FOUNDER ACTION REQUIRED" in result["brief"]["content"]

def test_cycle_rejects_unbounded_iterations(tmp_path):
    cycle = ResearchCycle(Database(str(tmp_path / "test.db")))
    try: cycle.run("Research whether self-regulation can be trained and transferred to daily behavior.", 11)
    except ValueError: pass
    else: raise AssertionError("must enforce autonomous-loop limit")
