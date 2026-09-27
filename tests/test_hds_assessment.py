from app.database import Database
from app.workflow import ResearchCycle
from app.assessment import AssessmentService


def test_assessment_longitudinal_baseline_post_retention_and_project_isolation(tmp_path):
    db=Database(str(tmp_path/"company.db"))
    first=ResearchCycle(db).run("assessment one")["project"]
    second=ResearchCycle(db).run("assessment two")["project"]
    svc=AssessmentService(db)
    construct=svc.create_construct(first["id"],"RESILIENCE","Recovery behavior","Observable recovery after a defined setback","u1")
    measure=svc.create_measure(first["id"],construct["id"],"Recovery time","minutes",0,120,False,"u1")
    baseline=svc.start(first["id"],"p1","BASELINE")
    svc.observe(baseline["id"],measure["id"],60)
    svc.complete(baseline["id"])
    post=svc.start(first["id"],"p1","POST")
    svc.observe(post["id"],measure["id"],40)
    svc.complete(post["id"])
    retention=svc.start(first["id"],"p1","RETENTION")
    svc.observe(retention["id"],measure["id"],45)
    svc.complete(retention["id"])
    progress=svc.progress(first["id"],"p1",measure["id"])
    assert [x["timepoint"] for x in progress["observations"]]==["BASELINE","POST","RETENTION"]
    try:
        svc.create_measure(second["id"],construct["id"],"Bad","x",None,None,True,"u2")
        assert False
    except ValueError as exc:
        assert "project" in str(exc)


def test_assessment_rejects_out_of_range_and_closed_session(tmp_path):
    db=Database(str(tmp_path/"company.db"))
    project=ResearchCycle(db).run("assessment")["project"]
    svc=AssessmentService(db)
    construct=svc.create_construct(project["id"],"DISCIPLINE","Consistency","Observed completion consistency","u1")
    measure=svc.create_measure(project["id"],construct["id"],"Score","points",0,10,True,"u1")
    session=svc.start(project["id"],"p1","BASELINE")
    try: svc.observe(session["id"],measure["id"],11)
    except ValueError as exc: assert "maximum" in str(exc)
    else: assert False
    svc.observe(session["id"],measure["id"],8)
    svc.complete(session["id"])
    try: svc.observe(session["id"],measure["id"],7)
    except ValueError as exc: assert "closed" in str(exc)
    else: assert False


def test_assessment_routes_are_wired():
    from app.main import app
    paths={route.path for route in app.routes}
    assert "/api/hds/assessments/constructs" in paths
    assert "/api/hds/assessments/measures" in paths
    assert "/api/hds/assessments/sessions" in paths
