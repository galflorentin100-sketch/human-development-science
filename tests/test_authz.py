from app.database import Database
from app.auth import AuthService
from app.workflow import ResearchCycle
import uuid

def _project(db):
    from app.models import now
    company,agent,project=[str(uuid.uuid4()) for _ in range(3)]
    company="hds"
    db.execute("INSERT INTO companies(id,name,mission,vision,core_principle,created_at) VALUES (?,?,?,?,?,?) ON CONFLICT(id) DO NOTHING",(company,"c","m","v","p",now()))
    db.execute("INSERT INTO agents(id,name,role,mission,capabilities,permissions,version,status,created_at) VALUES (?,?,?,?,?,?,?,?,?)",(agent,"a","r","m","[]","[]","1","ACTIVE",now()))
    db.execute("INSERT INTO projects(id,company_id,objective,status,owner_agent_id,created_at) VALUES (?,?,?,?,?,?)",(project,company,"o","ACTIVE",agent,now()))
    return project

def test_project_authorization_is_scoped_and_permission_checked(tmp_path):
    db=Database(str(tmp_path/"authz.db")); ResearchCycle(db); auth=AuthService(db)
    p1=_project(db); p2=_project(db)
    auth.create_user("founder","founder@example.test","founder")
    auth.create_user("user-a","a@example.test","operator")
    auth.create_user("user-b","b@example.test","reviewer")
    auth.grant_project_access("founder","user-a",p1,"operator")
    auth.grant_project_access("founder","user-b",p2,"reviewer")

    assert auth.project_authorize("user-a",p1,"WRITE").role=="operator"
    try:
        auth.project_authorize("user-a",p2,"READ")
        assert False
    except PermissionError as exc:
        assert "project access denied" in str(exc)

    try:
        auth.project_authorize("user-b",p2,"EXECUTE")
        assert False
    except PermissionError as exc:
        assert "permission denied" in str(exc)

def test_project_access_cannot_be_granted_to_unknown_project(tmp_path):
    db=Database(str(tmp_path/"authz-missing.db")); ResearchCycle(db); auth=AuthService(db)
    auth.create_user("founder","founder@example.test","founder")
    auth.create_user("user-a","a@example.test","operator")
    try:
        auth.grant_project_access("founder","user-a",str(uuid.uuid4()),"operator")
        assert False
    except ValueError as exc:
        assert "project not found" in str(exc)



def test_resource_project_boundary_covers_constructs(tmp_path, monkeypatch):
    from app.main import require_resource_project
    from app.models import now

    db=Database(str(tmp_path/"resource-boundary.db")); ResearchCycle(db); auth=AuthService(db)
    p1=_project(db); p2=_project(db)
    auth.create_user("founder","founder@example.test","founder")
    auth.create_user("operator","operator@example.test","operator")
    auth.grant_project_access("founder","operator",p1,"operator")

    db.execute(
        "INSERT INTO scientific_constructs(id,project_id,name,definition,construct_type,status,version,created_at) VALUES (?,?,?,?,?,?,?,?)",
        ("construct-a",p1,"discipline","test","CAPABILITY","ACTIVE",1,now()),
    )

    import app.main as main
    monkeypatch.setattr(main,"db",db)
    principal=auth.authorize("operator")
    assert require_resource_project(principal,"construct","construct-a","READ")==p1
    try:
        db.execute(
            "INSERT INTO scientific_constructs(id,project_id,name,definition,construct_type,status,version,created_at) VALUES (?,?,?,?,?,?,?,?)",
            ("construct-b",p2,"discipline-b","test","CAPABILITY","ACTIVE",1,now()),
        )
        require_resource_project(principal,"construct","construct-b","READ")
        assert False, "cross-project construct access must be denied"
    except Exception as exc:
        assert "project access denied" in str(exc)


def test_project_authorization_denies_cross_project_resource_even_with_company_membership(tmp_path):
    db=Database(str(tmp_path/"resource-auth.db")); ResearchCycle(db); auth=AuthService(db)
    p1=_project(db); p2=_project(db)
    auth.create_user("operator","operator@example.test","operator")
    auth.create_user("founder","founder@example.test","founder")
    auth.grant_project_access("founder","operator",p1,"operator")
    try:
        auth.project_authorize("operator",p2,"READ")
        assert False, "company membership must not imply project membership"
    except PermissionError as exc:
        assert "project access denied" in str(exc)
