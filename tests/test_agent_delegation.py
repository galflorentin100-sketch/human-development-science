import uuid
from app.database import Database
from app.research_queue import ResearchQueue
from app.models import now

def test_delegation_maps_research_to_agent(tmp_path):
    from app.agent_delegation import AgentDelegation
    db=Database(str(tmp_path/"x.db"))
    from app.workflow import ResearchCycle
    ResearchCycle(db)
    pid=ResearchCycle(db).run("delegation")["project"]["id"]
    ResearchQueue(db).propose(pid,"Question","Need evidence","DISCOVERY")
    task=AgentDelegation(db).delegate_pending(pid,1)[0]
    assert task["assigned_agent_id"]=="researcher"
    assert task["status"]=="PLANNED"

def test_delegation_deduplicates(tmp_path):
    from app.agent_delegation import AgentDelegation
    db=Database(str(tmp_path/"x.db"))
    from app.workflow import ResearchCycle
    ResearchCycle(db)
    pid=ResearchCycle(db).run("delegation dedupe")["project"]["id"]
    ResearchQueue(db).propose(pid,"Question","Need evidence","DISCOVERY")
    d=AgentDelegation(db)
    assert len(d.delegate_pending(pid,5))==1
    assert len(d.delegate_pending(pid,5))==0


def test_decision_center_has_delegateable_method(tmp_path):
    from app.decision_center import DecisionCenter
    db=Database(str(tmp_path/"x.db"))
    pid=str(uuid.uuid4())
    assert DecisionCenter(db).delegateable(pid)==[]

def test_governance_sensitive_delegation_requires_and_consumes_founder_approval(tmp_path):
    from app.agent_delegation import AgentDelegation
    from app.approvals import ApprovalService
    from app.workflow import ResearchCycle
    db=Database(str(tmp_path/"approval.db"))
    ResearchCycle(db)
    pid=ResearchCycle(db).run("approval gate")["project"]["id"]
    decision={"type":"FINDING","id":"finding-1","title":"Candidate finding","reason":"Review evidence","priority":"HIGH","requires_founder_approval":True}
    delegation=AgentDelegation(db)

    first=delegation.delegate(pid,decision)
    assert first["status"]=="WAITING_FOR_APPROVAL"
    approval=first["approval"]
    assert approval["action"]=="FOUNDER_DECISION:FINDING:finding-1"

    ApprovalService(db).resolve(approval["id"],"APPROVED","founder")
    task=delegation.delegate(pid,decision)
    assert task["status"]=="PLANNED"
    consumed=db.one("SELECT action FROM approval_events WHERE approval_id=? AND action='CONSUMED'",(approval["id"],))
    assert consumed is not None

def test_governed_delegation_rolls_back_consumed_approval_when_task_creation_fails(tmp_path, monkeypatch):
    from app.agent_delegation import AgentDelegation
    from app.approvals import ApprovalService
    from app.workflow import ResearchCycle
    db=Database(str(tmp_path/"atomic.db"))
    ResearchCycle(db)
    pid=ResearchCycle(db).run("atomic approval")["project"]["id"]
    decision={"type":"FINDING","id":"finding-atomic","title":"Atomic finding","reason":"Review evidence","priority":"HIGH","requires_founder_approval":True}
    delegation=AgentDelegation(db)
    first=delegation.delegate(pid,decision)
    approval=first["approval"]
    ApprovalService(db).resolve(approval["id"],"APPROVED","founder")

    def fail_task(*args,**kwargs):
        raise RuntimeError("simulated task insert failure")
    monkeypatch.setattr(delegation.tasks,"create_task_in_transaction",fail_task)

    try:
        delegation.delegate(pid,decision)
        assert False, "expected simulated failure"
    except RuntimeError as exc:
        assert str(exc)=="simulated task insert failure"

    restored=db.one("SELECT status FROM approvals WHERE id=?",(approval["id"],))
    assert restored["status"]=="APPROVED"
    assert db.one("SELECT 1 FROM approval_events WHERE approval_id=? AND action='CONSUMED'",(approval["id"],)) is None
