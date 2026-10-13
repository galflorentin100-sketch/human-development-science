from app.auth import AuthService
from app.database import Database
from app.workflow import ResearchCycle
from scripts.bootstrap_owner import provision_owner


def test_owner_provisioning_creates_only_configured_founder(tmp_path):
    db = Database(str(tmp_path / "owner-bootstrap.db"))
    ResearchCycle(db)
    result = provision_owner(
        db,
        "idp|owner-123",
        "owner@example.org",
        "idp|owner-123",
    )
    assert result["role"] == "founder"
    principal = AuthService(db, "idp|owner-123").authorize("idp|owner-123")
    assert principal.role == "founder"
    assert principal.can("DEPLOY")


def test_owner_provisioning_rejects_mismatched_external_subject(tmp_path):
    db = Database(str(tmp_path / "owner-bootstrap-mismatch.db"))
    ResearchCycle(db)
    try:
        provision_owner(
            db,
            "idp|attacker",
            "owner@example.org",
            "idp|owner-123",
        )
        assert False, "mismatched subject must not be provisioned"
    except ValueError as exc:
        assert "exactly match" in str(exc)


def test_owner_provisioning_does_not_silently_escalate_existing_operator(tmp_path):
    db = Database(str(tmp_path / "owner-bootstrap-role.db"))
    ResearchCycle(db)
    AuthService(db, "idp|owner-123").create_user(
        "idp|owner-123",
        "owner@example.org",
        role="operator",
    )
    try:
        provision_owner(
            db,
            "idp|owner-123",
            "owner@example.org",
            "idp|owner-123",
        )
        assert False, "existing operator must not be silently escalated"
    except RuntimeError as exc:
        assert "without active founder membership" in str(exc)

def test_bootstrapped_research_project_can_be_granted_to_configured_founder(tmp_path):
    from app.autonomous_research_loop import AutonomousResearchLoop

    db = Database(str(tmp_path / "owner-project-access.db"))
    ResearchCycle(db)
    owner_subject = "idp|owner-456"
    provision_owner(db, owner_subject, "owner@example.org", owner_subject)
    result = AutonomousResearchLoop(db).bootstrap_research(
        "What is self-discipline?"
    )
    service = AuthService(db, owner_subject)
    access = service.grant_project_access(
        owner_subject,
        owner_subject,
        result["project"]["id"],
        role="founder",
    )
    assert access.user_id
    assert access.can("WRITE")
    assert service.project_authorize(
        owner_subject, result["project"]["id"], "EXECUTE"
    ).can("EXECUTE")

