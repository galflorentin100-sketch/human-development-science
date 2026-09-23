from app.database import Database
from app.workflow import ResearchCycle
from app.tasks import TaskEngine
from app.permissions import Permission,PermissionService

def test_phase2_tables_and_goal(tmp_path):
    db=Database(str(tmp_path/"phase2.db"))
    ResearchCycle(db)
    goal=TaskEngine(db).create_goal("Build HDS","test")
    assert goal["status"]=="ACTIVE"
    assert db.one("SELECT 1 FROM goals WHERE id=?",(goal["id"],))

def test_execution_permission_seeded(tmp_path):
    db=Database(str(tmp_path/"permissions.db"))
    ResearchCycle(db)
    PermissionService(db).check("researcher",Permission.EXECUTE,"smoke")
