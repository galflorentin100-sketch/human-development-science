import json
import uuid

from app.database import Database
from app.evaluation import EvaluationService
from app.models import now


def test_verified_output_can_remain_uncertain_without_failing_verification(tmp_path):
    db=Database(str(tmp_path/"evaluation.db"))

    company_id=str(uuid.uuid4())
    agent_id=str(uuid.uuid4())
    project_id=str(uuid.uuid4())
    task_id=str(uuid.uuid4())
    run_id=str(uuid.uuid4())
    ts=now()

    db.execute(
        "INSERT INTO companies(id,name,mission,vision,core_principle,created_at) VALUES (?,?,?,?,?,?)",
        (company_id,"HDS","Research","Scientific development","Truth first",ts))
    db.execute(
        "INSERT INTO agents(id,name,role,mission,capabilities,permissions,version,status,created_at) VALUES (?,?,?,?,?,?,?,?,?)",
        (agent_id,"Researcher","researcher","Research",'["Research"]','["READ"]',"1","ACTIVE",ts))
    db.execute(
        "INSERT INTO projects(id,company_id,objective,status,owner_agent_id,created_at) VALUES (?,?,?,?,?,?)",
        (project_id,company_id,"Evaluate output","RUNNING",agent_id,ts))
    db.execute(
        "INSERT INTO tasks(id,project_id,title,status,assigned_agent_id,priority,success_criteria,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
        (task_id,project_id,"Review output","COMPLETED",agent_id,1.0,"Produce a verifiable output.",ts,ts))
    output={
        "uncertainties":["The observed result is preliminary."],
        "evidence_refs":["evidence-1"],
    }
    db.execute(
        """INSERT INTO agent_runs(
            id,agent_id,task_id,status,input_payload,output_payload,started_at,
            completed_at,confidence,evidence_refs,uncertainties,cost_metadata,error,verified
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            run_id,agent_id,task_id,"REVIEW","{}",
            json.dumps(output),ts,ts,0.5,json.dumps(output["evidence_refs"]),
            json.dumps(output["uncertainties"]),"{}",None,1,
        ))

    evaluation=EvaluationService(db).evaluate_run(run_id)

    assert evaluation["passed"]==1
    assert evaluation["score"]==1.0
    details=json.loads(evaluation["details"])
    assert details["verified"] is True
    assert details["uncertainties"]==output["uncertainties"]
