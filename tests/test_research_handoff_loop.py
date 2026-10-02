from app.database import Database
from app.workflow import ResearchCycle
from app.research_handoff import ResearchHandoffCoordinator

def test_handoff_requires_accepted_project_scoped_synthesis(tmp_path):
    db=Database(str(tmp_path/"handoff.db"))
    p=ResearchCycle(db).run("Handoff")["project"]
    with __import__("pytest").raises(ValueError):
        ResearchHandoffCoordinator(db).complete_accepted_synthesis(p["id"],"missing")

def test_handoff_rejects_synthesis_from_other_project(tmp_path):
    db=Database(str(tmp_path/"scope.db"))
    p1=ResearchCycle(db).run("One")["project"]
    p2=ResearchCycle(db).run("Two")["project"]
    # A missing/foreign synthesis must never be accepted as this project's continuation.
    db.execute("""CREATE TABLE IF NOT EXISTS research_workspaces
        (id TEXT PRIMARY KEY, project_id TEXT, question TEXT, scope TEXT, inclusion_rules TEXT,
         exclusion_rules TEXT, status TEXT, owner TEXT, created_at TEXT, updated_at TEXT)""")
    db.execute("""CREATE TABLE IF NOT EXISTS research_syntheses
        (id TEXT PRIMARY KEY, workspace_id TEXT, synthesis TEXT, limitations TEXT, uncertainty TEXT,
         provenance_hash TEXT, evidence_refs TEXT, status TEXT, created_by TEXT, created_at TEXT)""")
    db.execute("INSERT INTO research_workspaces VALUES (?,?,?,?,?,?,?,?,?,datetime('now'))",
        ("ws-foreign",p2["id"],"Q","S","[]","[]","REVIEWED","x",__import__("datetime").datetime.now().isoformat()))
    db.execute("INSERT INTO research_syntheses VALUES (?,?,?,?,?,?,?,?,?,datetime('now'))",
        ("syn-foreign","ws-foreign","S","","","hash","[]","ACCEPTED","x"))
    with __import__("pytest").raises(ValueError):
        ResearchHandoffCoordinator(db).complete_accepted_synthesis(p1["id"],"syn-foreign")
