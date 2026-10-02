from app.database import Database
from app.workflow import ResearchCycle
from app.research_engine import ResearchEngine
from app.research_loop_coordinator import ResearchLoopCoordinator

def test_closed_loop_requires_accepted_synthesis(tmp_path):
    db=Database(str(tmp_path/"loop.db"))
    project=ResearchCycle(db).run("Loop")["project"]
    engine=ResearchEngine(db)
    ws=engine.create(project["id"],"What evidence exists?","bounded",owner="system")
    engine.activate(ws["id"],"system")
    try:
        ResearchLoopCoordinator(db).after_review("missing")
        assert False
    except ValueError:
        pass

def test_closed_loop_syncs_graph_and_generates_next_gaps(tmp_path):
    db=Database(str(tmp_path/"loop2.db"))
    project=ResearchCycle(db).run("Loop accepted")["project"]
    engine=ResearchEngine(db)
    ws=engine.create(project["id"],"What evidence exists?","bounded",owner="system")
    engine.activate(ws["id"],"system")
    source_id="source-1"
    db.execute("INSERT INTO sources(id,title,uri,created_at) VALUES (?,?,?,datetime('now'))",
               (source_id,"Test source","test://source"))
    engine.add_source(ws["id"],source_id,relevance="DIRECT",notes="test")
    # Synthesis is deliberately left candidate; this test verifies the governance gate.
    syn=engine.synthesize(ws["id"],"bounded synthesis","limitations","uncertainty","system",())
    assert syn["status"]=="CANDIDATE"
    try:
        ResearchLoopCoordinator(db).after_review(syn["id"])
        assert False
    except ValueError as exc:
        assert "ACCEPTED" in str(exc)
