from app.database import Database
from app.workflow import ResearchCycle
def test_cycle_smoke(tmp_path):
    cycle=ResearchCycle(Database(str(tmp_path/"test.db")))
    result=cycle.run("Research whether self-regulation can be trained and transferred to daily behavior.")
    assert result["project"]["status"]=="COMPLETED"
    assert len(result["tasks"])==5
    assert result["claims"][0]["classification"]=="PRELIMINARY"
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


def test_science_improvement_persists_evidence_reference(tmp_path):
    from app.continuous_improvement import ContinuousImprovementService
    db=Database(str(tmp_path/"improvement.db"))
    service=ContinuousImprovementService(db)
    cycle=ResearchCycle(db)
    result=cycle.run("Create verified evidence for improvement test")
    evidence_id=db.one("SELECT id FROM evidence WHERE claim_id=? AND verified=1",(result["claims"][0]["id"],))["id"]
    proposal=service.propose("Evidence-backed process change","SCIENCE","Test whether the process improves evidence quality.","Evidence audit pass rate","researcher",evidence_id)
    assert proposal["evidence_ref"]==evidence_id
    started=service.start_experiment(proposal["id"],"Compare before and after","Baseline recorded before intervention","researcher")
    assert started["status"]=="EXPERIMENT"
