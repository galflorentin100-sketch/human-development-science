import uuid
from app.database import Database
from app.research_queue import ResearchQueue
from app.models import now

def test_delegation_maps_research_to_agent(tmp_path):
    from app.agent_delegation import AgentDelegation
    db=Database(str(tmp_path/"x.db"))
    pid=str(uuid.uuid4())
    ResearchQueue(db).propose(pid,"Question","Need evidence","DISCOVERY")
    task=AgentDelegation(db).delegate_pending(pid,1)[0]
    assert task["assigned_agent_id"]=="researcher"
    assert task["status"]=="PLANNED"

def test_delegation_deduplicates(tmp_path):
    from app.agent_delegation import AgentDelegation
    db=Database(str(tmp_path/"x.db"))
    pid=str(uuid.uuid4())
    ResearchQueue(db).propose(pid,"Question","Need evidence","DISCOVERY")
    d=AgentDelegation(db)
    assert len(d.delegate_pending(pid,5))==1
    assert len(d.delegate_pending(pid,5))==0
