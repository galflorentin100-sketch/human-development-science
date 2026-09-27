from app.database import Database
from app.workflow import ResearchCycle
from app.code_changes import CodeChangeService


def test_code_change_requires_separation_of_duties_and_verification(tmp_path):
    db=Database(str(tmp_path/"code.db"))
    project=ResearchCycle(db).run("governed code changes")["project"]
    db.execute("""INSERT INTO maintenance_work
        (id,kind,entity_type,entity_id,title,reason,success_criteria,status,approval_id,created_at,updated_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        ("mw","ENGINEERING","project",project["id"],"Fix","reason","tests","PROPOSED",None,"now","now"))
    svc=CodeChangeService(db)
    p=svc.propose(project["id"],"mw","safe patch","UNIFIED_DIFF","diff --git","pytest tests/test_x.py","LOW","alice")
    try: svc.approve(p["id"],"alice"); assert False
    except ValueError as exc: assert "separation" in str(exc)
    approved=svc.approve(p["id"],"bob")
    assert approved["status"]=="APPROVED"
    verified=svc.mark_verified(p["id"],"ci-123","rollback")
    assert verified["status"]=="VERIFIED"
    rolled=svc.rollback(p["id"],"bob")
    assert rolled["status"]=="ROLLED_BACK"
