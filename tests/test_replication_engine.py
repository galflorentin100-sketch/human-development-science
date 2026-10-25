from app.database import Database
from app.workflow import ResearchCycle
from app.experiment_engine import ExperimentEngine
from app.experiment_safety import ExperimentSafetyReviewer
from app.replication_engine import ReplicationEngine

def test_replication_requires_completed_source_and_preserves_project_scope(tmp_path):
    db=Database(str(tmp_path/"replication.db"))
    project=ResearchCycle(db).run("Replication")["project"]
    engine=ExperimentEngine(db)
    exp=engine.create(project["id"],"Does X improve Y","X improves Y","controlled","adults","X","control","Y",'{"outcome":"Y"}')
    try:
        ReplicationEngine(db).propose(project["id"],exp["id"],"confirm result")
        assert False
    except ValueError as exc:
        assert "completed" in str(exc)
    exp=engine.preregister(exp["id"])
    ExperimentSafetyReviewer(db).review(exp["id"],"ACCEPT","digital planning safety review","reviewer")
    engine.start(exp["id"])
    engine.record_result(exp["id"],"descriptive outcome","descriptive interpretation")
    engine.complete(exp["id"])
    repl=ReplicationEngine(db)
    p=repl.propose(project["id"],exp["id"],"independent confirmation",["same primary outcome","same stopping rule"])
    assert p["status"]=="PROPOSED"
    assert repl.ready(p["id"])["status"]=="READY"
    done=repl.record_result(p["id"],"No compatible effect estimate available","Replication outcome recorded descriptively")
    assert done["status"]=="COMPLETED"

def test_replication_cannot_cross_projects(tmp_path):
    db=Database(str(tmp_path/"replication-scope.db"))
    p1=ResearchCycle(db).run("P1")["project"]
    p2=ResearchCycle(db).run("P2")["project"]
    engine=ExperimentEngine(db)
    exp=engine.create(p1["id"],"Q","H","D","P","I","C","O",'{"outcome":"O"}')
    engine.preregister(exp["id"])
    ExperimentSafetyReviewer(db).review(exp["id"],"ACCEPT","review","reviewer")
    engine.start(exp["id"]); engine.record_result(exp["id"],"outcome","interpretation"); engine.complete(exp["id"])
    try:
        ReplicationEngine(db).propose(p2["id"],exp["id"],"cross project")
        assert False
    except ValueError as exc:
        assert "source experiment" in str(exc)
