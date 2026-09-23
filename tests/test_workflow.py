from app.database import Database
from app.workflow import ResearchCycle
def test_cycle_smoke(tmp_path):
    cycle=ResearchCycle(Database(str(tmp_path/"test.db")))
    result=cycle.run("Research whether self-regulation can be trained and transferred to daily behavior.")
    assert result["project"]["status"]=="COMPLETED"
    assert len(result["tasks"])==5
    assert result["claims"][0]["classification"]=="SUPPORTED"
    assert len(result["sources"])==3
    assert result["questions"][-1]["status"]=="OPEN"
    assert "NO FOUNDER ACTION REQUIRED" in result["brief"]["content"]
def test_cycle_rejects_unbounded_iterations(tmp_path):
    cycle=ResearchCycle(Database(str(tmp_path/"test.db")))
    try: cycle.run("bounded",11)
    except ValueError: return
    assert False


def test_cycle_persists_evidence_and_findings(tmp_path):
    cycle=ResearchCycle(Database(str(tmp_path/"evidence.db")))
    result=cycle.run("Test evidence audit")
    db=cycle.db
    assert db.one("SELECT COUNT(*) AS n FROM evidence WHERE claim_id=?",(result["claims"][0]["id"],))["n"]==3
    assert db.one("SELECT COUNT(*) AS n FROM findings WHERE project_id=?",(result["project"]["id"],))["n"]==1
