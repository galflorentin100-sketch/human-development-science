from app.database import Database
from app.workflow import ResearchCycle
from app.research_handoff import ResearchHandoffCoordinator

def test_handoff_requires_accepted_output(tmp_path):
    db=Database(str(tmp_path/"handoff.db"))
    project=ResearchCycle(db).run("Handoff")["project"]
    # An unregistered review cannot enter the closed loop.
    try:
        ResearchHandoffCoordinator(db).handoff("missing-review","actor")
        assert False
    except ValueError as exc:
        assert "output review not found" in str(exc)

def test_handoff_rejects_unaccepted_output(tmp_path):
    db=Database(str(tmp_path/"handoff2.db"))
    ResearchCycle(db).run("Handoff")
    db.execute("""INSERT INTO agent_output_reviews
        (id,agent_run_id,project_id,task_id,evidence_refs,provenance_hash,status,created_at)
        VALUES (?,?,?,?,?,?,?,datetime('now'))""",
        ("review","run","project","task","[]","hash","READY_FOR_REVIEW"))
    try:
        ResearchHandoffCoordinator(db).handoff("review","actor")
        assert False
    except ValueError as exc:
        assert "accepted" in str(exc)
