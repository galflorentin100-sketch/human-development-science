from app.database import Database
from app.workflow import ResearchCycle
from app.research import ResearchRepository
from app.falsification_engine import FalsificationEngine

def test_falsification_challenge_lifecycle_is_explicit(tmp_path):
    db=Database(str(tmp_path/"falsification.db"))
    project=ResearchCycle(db).run("Falsification")["project"]
    hypothesis=ResearchRepository(db).hypothesis(project["id"],"A measurable training mechanism improves persistence")
    engine=FalsificationEngine(db)
    row=engine.propose(
        project["id"],hypothesis["id"],
        "Attempt to find observations inconsistent with the hypothesis",
        "No improvement under a preregistered test despite adequate exposure",
        ["predefined outcome","fixed stopping rule"],
    )
    assert row["status"]=="PROPOSED"
    started=engine.start(row["id"])
    assert started["status"]=="IN_PROGRESS"
    completed=engine.record_result(row["id"],"No disconfirming observation was obtained","Not falsified by this challenge")
    assert completed["status"]=="COMPLETED"
    assert completed["conclusion"]=="Not falsified by this challenge"

def test_falsification_is_project_scoped(tmp_path):
    db=Database(str(tmp_path/"falsification-scope.db"))
    p1=ResearchCycle(db).run("P1")["project"]
    p2=ResearchCycle(db).run("P2")["project"]
    h=ResearchRepository(db).hypothesis(p1["id"],"Hypothesis")
    engine=FalsificationEngine(db)
    try:
        engine.propose(p2["id"],h["id"],"challenge","disconfirming observation")
        assert False
    except ValueError as exc:
        assert "hypothesis" in str(exc)
