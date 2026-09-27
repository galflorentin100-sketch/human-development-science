from app.database import Database
from app.workflow import ResearchCycle
from app.autonomous_research_loop import AutonomousResearchLoop

def test_research_loop_enforces_project_and_provenance_gates(tmp_path):
    db=Database(str(tmp_path/"hds.db")); p=ResearchCycle(db).run("gap")["project"]; other=ResearchCycle(db).run("other")["project"]
    loop=AutonomousResearchLoop(db); run=loop.create_gap(p["id"],"What improves recovery after setbacks?"); loop.start_research(run["id"])
    ws=loop.get(run["id"])["workspace_id"]
    syn=loop.db.one("SELECT * FROM research_syntheses WHERE workspace_id=?",(ws,))
    # Cross-project synthesis cannot be attached.
    other_ws=__import__("app.research_engine",fromlist=["ResearchEngine"]).ResearchEngine(db).create(other["id"],"other gap")
    try: loop.attach_synthesis(run["id"],other_ws["id"])
    except ValueError: pass
    else: assert False
    assert loop.get(run["id"])["status"]=="RESEARCH_ACTIVE"

def test_research_loop_requires_explicit_finding_to_claim_provenance(tmp_path):
    db=Database(str(tmp_path/"hds.db")); p=ResearchCycle(db).run("gap")["project"]; loop=AutonomousResearchLoop(db)
    run=loop.create_gap(p["id"],"research question"); loop.start_research(run["id"])
    ws=loop.get(run["id"])["workspace_id"]
    # The loop cannot accept an arbitrary finding even from the same project.
    from app.research import ResearchFindingService
    f=ResearchFindingService(db).create(p["id"],"candidate","INFERENCE","OBSERVATION",created_by="u")
    try: loop.attach_finding(run["id"],f["id"])
    except ValueError as e: assert "awaiting finding" in str(e)
    else: assert False
