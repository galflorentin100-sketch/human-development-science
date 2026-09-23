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

def test_research_repository_persists_hypothesis_and_experiment(tmp_path):
    from app.research import ResearchRepository
    db=Database(str(tmp_path/"research.db")); ResearchCycle(db)
    project=ResearchCycle(db).run("research")["project"]
    rr=ResearchRepository(db)
    h=rr.hypothesis(project["id"],"Training improves transfer")
    e=rr.experiment(project["id"],h["statement"],"controlled pilot")
    out=rr.result(e["id"],"null","No evidence of transfer in pilot")
    assert out["experiment_id"]==e["id"]
    assert db.one("SELECT status FROM experiments WHERE id=?",(e["id"],))["status"]=="COMPLETED"

def test_approval_event_is_audited(tmp_path):
    from app.approvals import ApprovalService,ApprovalStatus
    db=Database(str(tmp_path/"approval.db")); ResearchCycle(db)
    a=ApprovalService(db).request("DEPLOY","ceo")
    ApprovalService(db).resolve(a["id"],ApprovalStatus.REJECTED,"founder")
    assert db.one("SELECT COUNT(*) AS n FROM approval_events WHERE approval_id=?",(a["id"],))["n"]==1
