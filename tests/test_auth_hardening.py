from app.database import Database
from app.workflow import ResearchCycle
from app.auth import AuthService

def test_new_users_are_not_founders_by_default(tmp_path):
    db=Database(str(tmp_path/"auth.db")); ResearchCycle(db)
    auth=AuthService(db)
    user=auth.create_user("subject-1","a@example.com")
    role=db.one("SELECT r.name FROM company_memberships m JOIN roles r ON r.id=m.role_id WHERE m.user_id=?",(user["id"],))
    assert role["name"]=="operator"

def test_existing_external_subject_cannot_change_email(tmp_path):
    db=Database(str(tmp_path/"auth2.db")); ResearchCycle(db)
    auth=AuthService(db)
    auth.create_user("subject-1","a@example.com")
    try:
        auth.create_user("subject-1","attacker@example.com")
        assert False
    except ValueError as exc:
        assert "different email" in str(exc)

def test_founder_role_must_be_explicit(tmp_path):
    db=Database(str(tmp_path/"auth3.db")); ResearchCycle(db)
    auth=AuthService(db)
    user=auth.create_user("founder-subject","f@example.com","founder")
    principal=auth.authorize("founder-subject")
    assert principal.role=="founder"
    assert principal.can("APPROVE")


def test_authorize_principal_uses_database_user_id(tmp_path):
    db=Database(str(tmp_path/"principal-id.db")); ResearchCycle(db)
    auth=AuthService(db)
    user=auth.create_user("subject-1","a@example.com","operator")
    principal=auth.authorize("subject-1")
    assert principal.user_id == user["id"]
    assert principal.user_id != user["external_subject"]


def test_configured_owner_is_the_only_authorized_principal(tmp_path):
    db=Database(str(tmp_path/"owner.db")); ResearchCycle(db)
    auth=AuthService(db,"owner-subject")
    auth.create_user("owner-subject","owner@example.com","founder")
    auth.create_user("other-subject","other@example.com","operator")
    assert auth.authorize("owner-subject").role=="founder"
    try:
        auth.authorize("other-subject")
        assert False
    except PermissionError as exc:
        assert "system owner" in str(exc)
