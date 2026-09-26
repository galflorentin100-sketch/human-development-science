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

def test_database_migration_materializes_all_scientific_phases(tmp_path):
    db=Database(str(tmp_path/"all-phases.db"))
    db.migrate()
    required={
        "roles","idempotency_keys","model_calls","research_findings",
        "budgets","cost_events","scientific_constructs","training_protocols",
        "research_workspaces","hds_experiments","agent_output_reviews",
        "company_memory","knowledge_impact_reviews",
    }
    rows=db.all("SELECT name FROM sqlite_master WHERE type='table'")
    tables={r["name"] for r in rows}
    assert required <= tables
    db.migrate()
    rows2=db.all("SELECT name FROM sqlite_master WHERE type='table'")
    assert tables <= {r["name"] for r in rows2}
