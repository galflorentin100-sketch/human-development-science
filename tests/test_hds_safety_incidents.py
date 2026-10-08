from app.database import Database
from app.workflow import ResearchCycle
from app.human_development import HumanDevelopmentService
from app.participant_governance import ParticipantGovernance
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
    db.execute("UPDATE training_protocols SET status='PILOT' WHERE id=?",(protocol["id"],))
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


def test_training_session_rechecks_consent_and_adverse_event_inside_write_transaction(tmp_path):
    from app.training import TrainingProtocolService
    from app.participant_governance import ParticipantGovernance

    db=Database(str(tmp_path/"training-transaction-gate.db"))
    project=ResearchCycle(db).run("transaction safety gate")["project"]["id"]
    protocol=TrainingProtocolService(db).create(
        project, "transaction-gated protocol", "mechanism", "domain",
        "one session", "progress", "transfer", "retention", "stop on adverse event",
    )
    db.execute("UPDATE training_protocols SET status='PILOT' WHERE id=?",(protocol["id"],))
    governance=ParticipantGovernance(db)
    governance.register("p1","consent-v1")
    session=TrainingProtocolService(db).session(
        protocol["id"], "p1", 1, "normal load", 1,
        safety_checks={"readiness":"CLEAR"},
    )
    assert session["session_number"] == 1

    governance.withdraw("p1","participant withdrew consent")
    try:
        TrainingProtocolService(db).session(
            protocol["id"], "p1", 2, "normal load", 1,
            safety_checks={"readiness":"CLEAR"},
        )
        assert False, "withdrawn consent must block a new session"
    except ValueError as exc:
        assert "actively consented" in str(exc)

    governance.register("p1","consent-v2")
    event=governance.record_adverse_event("p1",protocol["id"],"HIGH","unexpected event")
    try:
        TrainingProtocolService(db).session(
            protocol["id"], "p1", 3, "normal load", 1,
            safety_checks={"readiness":"CLEAR"},
        )
        assert False, "unresolved adverse event must block a new session"
    except ValueError as exc:
        assert "unresolved adverse event" in str(exc)
    assert db.one("SELECT session_number FROM training_sessions WHERE protocol_id=? AND participant_ref=? AND session_number=3",
                  (protocol["id"],"p1")) is None


def test_participant_consent_withdrawal_and_deviation_are_audited(tmp_path):
    db=Database(str(tmp_path/"participant-audit.db"))
    governance=ParticipantGovernance(db)
    governance.register("audit-p1","consent-v1","researcher")
    governance.record_deviation("audit-p1","protocol-1","load reduced","minor",session_id="session-1")
    governance.withdraw("audit-p1","participant requested withdrawal")
    events=db.all(
        "SELECT event_type,actor FROM audit_logs WHERE entity_type='participant' AND entity_id=? ORDER BY created_at",
        ("audit-p1",),
    )
    assert [e["event_type"] for e in events] == [
        "participant.consent_recorded",
        "participant.protocol_deviation_recorded",
        "participant.consent_withdrawn",
    ]
    assert events[0]["actor"] == "researcher"
