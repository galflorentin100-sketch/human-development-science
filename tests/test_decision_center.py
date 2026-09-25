import uuid
from app.database import Database
from app.research_queue import ResearchQueue

def test_decision_center_collects_research_review(tmp_path):
    from app.decision_center import DecisionCenter
    db=Database(str(tmp_path/"d.db"))
    pid=str(uuid.uuid4())
    ResearchQueue(db).propose(pid,"Does intervention transfer?","Transfer is unknown","DISCOVERY")
    items=DecisionCenter(db).list(pid)
    assert items and items[0]["type"]=="RESEARCH"

def test_decision_center_pending_approvals(tmp_path):
    from app.decision_center import DecisionCenter
    from app.approvals import ApprovalService
    db=Database(str(tmp_path/"a.db"))
    ApprovalService(db).request("scientific.publish","system","review")
    assert len(DecisionCenter(db).approvals())==1
