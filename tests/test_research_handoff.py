from app.database import Database
from app.workflow import ResearchCycle
from app.research_handoff import ResearchHandoffCoordinator

def test_handoff_requires_accepted_output(tmp_path):
    db=Database(str(tmp_path/"handoff.db"))
    project=ResearchCycle(db).run("Handoff")["project"]
    try:
        ResearchHandoffCoordinator(db).handoff("missing-review","actor")
        assert False
    except ValueError as exc:
        assert "output review not found" in str(exc)

def test_handoff_rejects_unaccepted_output(tmp_path):
    db=Database(str(tmp_path/"handoff2.db"))
    project=ResearchCycle(db).run("Handoff")
    task_id="task-handoff"
    db.execute("""INSERT INTO tasks
        (id,project_id,title,status,assigned_agent_id,priority,success_criteria,created_at,updated_at,owner,required_permissions,retry_limit)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (task_id,project["project"]["id"],"test","PLANNED",None,1.0,"{}","now","now","test","[]",0))
    db.execute("""INSERT INTO agent_runs
        (id,agent_id,task_id,status,input_payload,output_payload,started_at,completed_at)
        VALUES (?,?,?,?,?,?,datetime('now'),datetime('now'))""",
        ("run","agent","task-handoff","COMPLETED","{}","{}"))
    db.execute("""INSERT INTO agent_output_reviews
        (id,agent_run_id,project_id,task_id,evidence_refs,provenance_hash,status,created_at)
        VALUES (?,?,?,?,?,?,?,datetime('now'))""",
        ("review","run",project["project"]["id"],task_id,"[]","hash","READY_FOR_REVIEW"))
    try:
        ResearchHandoffCoordinator(db).handoff("review","actor")
        assert False
    except ValueError as exc:
        assert "accepted" in str(exc)
