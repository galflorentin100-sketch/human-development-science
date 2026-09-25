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


def test_decision_items_expose_next_action(tmp_path):
    import uuid
    from app.database import Database
    db=Database(str(tmp_path/"x.db"))
    project_id=str(uuid.uuid4())
    item={"type":"RESEARCH","id":"r1","priority":"NORMAL","title":"Question","reason":"Need evidence"}
    center=DecisionCenter(db)
    center.list=lambda pid:[dict(item)]
    result=center.list(project_id)
    assert result[0]["next_action"]=="delegate_research"
    assert result[0]["agent_role"]=="researcher"
