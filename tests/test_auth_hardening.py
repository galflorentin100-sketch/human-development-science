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
