from app.database import Database
from app.workflow import ResearchCycle
from app.research_queue import ResearchQueue

def test_autonomous_begin_requires_scheduler_mode(tmp_path):
    db=Database(str(tmp_path/"queue.db"))
    project=ResearchCycle(db).run("Queue governance")["project"]
    q=ResearchQueue(db)
    item=q.propose(project["id"],"Digital question","reason",trigger_type="AUTONOMOUS_SCHEDULER")
    try:
        q.autonomous_begin(item["id"],"autonomous-research",mode="HUMAN_SUBJECTS")
        assert False
    except ValueError as exc:
        assert "DIGITAL_RESEARCH" in str(exc)

def test_autonomous_begin_is_audited(tmp_path):
    db=Database(str(tmp_path/"queue-audit.db"))
    project=ResearchCycle(db).run("Queue audit")["project"]
    q=ResearchQueue(db)
    item=q.propose(project["id"],"Digital question","reason",trigger_type="AUTONOMOUS_SCHEDULER")
    started=q.autonomous_begin(item["id"],"autonomous-research")
    assert started["queue_item"]["status"]=="IN_PROGRESS"
    audit=db.one("SELECT * FROM audit_logs WHERE entity_id=? AND event_type='research_queue.autonomous_started'",(item["id"],))
    assert audit is not None
