from app.database import Database
from app.workflow import ResearchCycle
from app.human_development import HumanDevelopmentService
from app.models import now

def test_safety_incident_requires_independent_review(tmp_path):
    db=Database(str(tmp_path/"safety.db"))
    project=ResearchCycle(db).run("safety incidents")["project"]["id"]
    svc=HumanDevelopmentService(db)
    incident=svc.report_safety_incident(project,"participant stopped due to pain","execution stopped","HIGH","reporter")
    assert incident["status"]=="OPEN"
    try:
        svc.review_safety_incident(incident["id"],"reporter","REVIEWED","review")
        assert False
    except ValueError as exc:
        assert "cannot review" in str(exc)
    reviewed=svc.review_safety_incident(incident["id"],"independent-reviewer","REVIEWED","review completed")
    assert reviewed["status"]=="REVIEWED"
    assert reviewed["reviewed_by"]=="independent-reviewer"


def test_training_session_requires_current_safety_clearance_and_blocks_unresolved_adverse_event(tmp_path):
    from app.training import TrainingProtocolService
    from app.participant_governance import ParticipantGovernance

    db=Database(str(tmp_path/"training-safety.db"))
    project=ResearchCycle(db).run("training safety gate")["project"]["id"]
    protocol=TrainingProtocolService(db).create(
        project_id=project,
        name="Safety-gated protocol",
        mechanism_hypothesis="test mechanism",
        challenge_domain="test",
        dosage="one session",
        progression_rule="progress after successful sessions",
        transfer_target="target",
        retention_target="retention",
        safety_constraints="stop on adverse event",
    )
    participant=ParticipantGovernance(db)
    participant.register("p1","consent-v1")

    try:
        TrainingProtocolService(db).session(
            protocol["id"],"p1",1,"normal load",1,
            safety_checks=None,
        )
        assert False
    except ValueError as exc:
        assert "safety checks" in str(exc)

    session=TrainingProtocolService(db).session(
        protocol["id"],"p1",1,"normal load",1,
        safety_checks={"readiness":"CLEAR"},
    )
    assert session["participant_ref"]=="p1"

    event=participant.record_adverse_event(
        "p1",protocol["id"],"HIGH","unexpected adverse event"
    )
    try:
        TrainingProtocolService(db).session(
            protocol["id"],"p1",2,"normal load",1,
            safety_checks={"readiness":"CLEAR"},
        )
        assert False
    except ValueError as exc:
        assert "unresolved adverse event" in str(exc)

    resolved=participant.resolve_adverse_event(event["id"],"reviewer","participant reviewed and cleared")
    assert resolved["resolved"]==1

    session2=TrainingProtocolService(db).session(
        protocol["id"],"p1",2,"normal load",1,
        safety_checks={"readiness":"CLEAR"},
    )
    assert session2["session_number"]==2
