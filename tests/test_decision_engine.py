import pytest
from app.database import Database
from app.decision_engine import DecisionEngine
from app.workflow import ResearchCycle


def test_decision_assessment_is_project_scoped_and_atomic(tmp_path):
    db=Database(str(tmp_path/"decision.db"))
    project=ResearchCycle(db).run("decision project")["project"]
    engine=DecisionEngine(db)

    result=engine.assess(
        project["id"],
        "PUBLISH",
        ["publish","wait"],
        ["verified evidence"],
        ["outcome uncertainty"],
        0.9,
        "measure publication outcome",
        owner="founder",
        risk_level="HIGH",
    )

    assert result["decision"]["project_id"]==project["id"]
    assert result["approval"] is not None
    stored=db.one("SELECT project_id FROM decisions WHERE id=?",(result["decision"]["id"],))
    assert stored["project_id"]==project["id"]


def test_decision_assessment_rejects_unknown_project_without_partial_row(tmp_path):
    db=Database(str(tmp_path/"decision_missing.db"))
    engine=DecisionEngine(db)
    with pytest.raises(ValueError, match="project not found"):
        engine.assess(
            "missing-project",
            "WAIT",
            ["wait"],
            ["evidence"],
            [],
            0.9,
            "observe",
            owner="founder",
        )
    assert db.one("SELECT 1 FROM decisions WHERE project_id=?",("missing-project",)) is None


def test_decision_outcome_requires_matching_project_when_scope_is_supplied(tmp_path):
    db=Database(str(tmp_path/"decision_scope.db"))
    p1=ResearchCycle(db).run("project one")["project"]
    p2=ResearchCycle(db).run("project two")["project"]
    decision=DecisionEngine(db).assess(
        p1["id"],"WAIT",["wait"],["evidence"],[],0.9,"observe",owner="founder"
    )["decision"]

    with pytest.raises(ValueError, match="another project"):
        DecisionEngine(db).record_outcome(decision["id"],"wrong project",project_id=p2["id"])

    assert db.one("SELECT actual_outcome FROM decisions WHERE id=?",(decision["id"],))["actual_outcome"] is None
    assert DecisionEngine(db).record_outcome(decision["id"],"observed",project_id=p1["id"])["actual_outcome"]=="observed"


def test_direct_execution_cannot_bypass_pending_decision_approval(tmp_path):
    from app.orchestrator import CompanyOrchestrator
    from app.tasks import TaskEngine

    db=Database(str(tmp_path/"decision_execution.db"))
    project=ResearchCycle(db).run("execution governance")["project"]
    TaskEngine(db).create_task(
        "governed task",
        "must wait for decision approval",
        project_id=project["id"],
        owner="researcher",
    )
    DecisionEngine(db).assess(
        project["id"],
        "PUBLISH",
        ["publish","wait"],
        ["verified evidence"],
        ["publication uncertainty"],
        0.9,
        "measure publication outcome",
        owner="founder",
        risk_level="HIGH",
    )

    result=CompanyOrchestrator(db).execute_next(project["id"])

    assert result["status"]=="WAITING_FOR_APPROVAL"
    assert db.one(
        "SELECT status FROM tasks WHERE project_id=? AND title=?",
        (project["id"],"governed task"),
    )["status"]=="PLANNED"
