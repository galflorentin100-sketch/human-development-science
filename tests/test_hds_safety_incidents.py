from app.database import Database
from app.workflow import ResearchCycle
from app.human_development import HumanDevelopmentService
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
