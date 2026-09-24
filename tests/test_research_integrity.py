from app.database import Database
from app.workflow import ResearchCycle
from app.research import ResearchRepository, StudyExecution
from app.evidence_pipeline import EvidencePipeline

def make_db(tmp_path):
    db=Database(str(tmp_path/"integrity.db"))
    ResearchCycle(db)
    return db

def test_participant_conflicting_consent_is_not_silently_reused(tmp_path):
    db=make_db(tmp_path)
    db.execute("INSERT INTO studies(id,title,design,population,findings,created_at,status) VALUES (?,?,?,?,?,?,?)",("s","S","RCT","adults","","2026-01-01","APPROVED"))
    study=StudyExecution(db)
    study.participant("s","p","CONSENTED")
    try: study.participant("s","p","WITHDRAWN"); assert False
    except ValueError as exc: assert "different consent" in str(exc)

def test_randomization_and_session_enforce_study_membership(tmp_path):
    db=make_db(tmp_path)
    for sid in ("s1","s2"):
        db.execute("INSERT INTO studies(id,title,design,population,findings,created_at,status) VALUES (?,?,?,?,?,?,?)",(sid,sid,"RCT","adults","","2026-01-01","APPROVED"))
    study=StudyExecution(db); p=study.participant("s1","p")
    try: study.randomize("s2",p["id"]); assert False
    except ValueError as exc: assert "does not belong" in str(exc)
    try: study.session("s2",p["id"],"BASELINE",1); assert False
    except ValueError as exc: assert "does not belong" in str(exc)

def test_randomization_rejects_duplicate_assignment(tmp_path):
    db=make_db(tmp_path)
    db.execute("INSERT INTO studies(id,title,design,population,findings,created_at,status) VALUES (?,?,?,?,?,?,?)",("s","S","RCT","adults","","2026-01-01","APPROVED"))
    study=StudyExecution(db); p=study.participant("s","p")
    study.randomize("s",p["id"],seed=1)
    try: study.randomize("s",p["id"],seed=2); assert False
    except ValueError as exc: assert "already assigned" in str(exc)

def test_experiment_result_is_single(tmp_path):
    db=make_db(tmp_path)
    db.execute("INSERT INTO experiments(id,hypothesis,status,design,created_at) VALUES (?,?,?,?,?)",("e","h","PLANNED","RCT","2026-01-01"))
    repo=ResearchRepository(db); repo.result("e","outcome","interpretation")
    assert db.one("SELECT status FROM experiments WHERE id='e'")["status"]=="COMPLETED"
    try: repo.result("e","again","again"); assert False
    except ValueError as exc: assert "already has a result" in str(exc)
    assert db.one("SELECT COUNT(*) AS n FROM experiment_results WHERE experiment_id='e'")["n"]==1

def test_evidence_reviewer_must_be_independent_and_unique(tmp_path):
    db=make_db(tmp_path)
    db.execute("INSERT INTO companies(id,name,mission,vision,core_principle,created_at) VALUES (?,?,?,?,?,?)",("c","C","m","v","p","2026-01-01"))
    db.execute("INSERT INTO agents(id,name,role,mission,capabilities,permissions,version,status,created_at) VALUES (?,?,?,?,?,?,?,?,?)",("a","A","r","m","[]","[]","1","ACTIVE","2026-01-01"))
    db.execute("INSERT INTO projects(id,company_id,objective,status,owner_agent_id,created_at) VALUES (?,?,?,?,?,?)",("p","c","o","RUNNING","a","2026-01-01"))
    db.execute("INSERT INTO claims(id,project_id,statement,classification,evidence_level,confidence,status,created_at) VALUES (?,?,?,?,?,?,?,?)",("c1","p","claim","FACT","PRIMARY",0.8,"OPEN","2026-01-01"))
    db.execute("INSERT INTO sources(id,title,url,source_type,verified_at,provenance_note) VALUES (?,?,?,?,?,?)",("src","source","https://example.com","PAPER","",""))
    db.execute("INSERT INTO evidence_sources(id,source_id,state,content_hash,fetched_at,parsed_at,created_at) VALUES (?,?,?,?,?,?,?)",("es","src","PARSED","hash","now","now","now"))
    pipe=EvidencePipeline(db); ev=pipe.attach("c1","src","excerpt",actor="alice")
    try: pipe.review(ev["id"],"alice","VERIFIED","self review"); assert False
    except ValueError as exc: assert "independent" in str(exc)
    pipe.review(ev["id"],"bob","VERIFIED","independent review")
    try: pipe.review(ev["id"],"bob","VERIFIED","duplicate review"); assert False
    except ValueError as exc: assert "already reviewed" in str(exc)


def test_evidence_excerpt_has_provenance_hash(tmp_path):
    import hashlib
    db=make_db(tmp_path)
    db.execute("INSERT INTO companies(id,name,mission,vision,core_principle,created_at) VALUES (?,?,?,?,?,?)",("c2","C","m","v","p","2026-01-01"))
    db.execute("INSERT INTO agents(id,name,role,mission,capabilities,permissions,version,status,created_at) VALUES (?,?,?,?,?,?,?,?,?)",("a2","A","r","m","[]","[]","1","ACTIVE","2026-01-01"))
    db.execute("INSERT INTO projects(id,company_id,objective,status,owner_agent_id,created_at) VALUES (?,?,?,?,?,?)",("p2","c2","o","RUNNING","a2","2026-01-01"))
    db.execute("INSERT INTO claims(id,project_id,statement,classification,evidence_level,confidence,status,created_at) VALUES (?,?,?,?,?,?,?,?)",("c2","p2","claim","FACT","PRIMARY",0.8,"OPEN","2026-01-01"))
    db.execute("INSERT INTO sources(id,title,url,source_type,verified_at,provenance_note) VALUES (?,?,?,?,?,?)",("src2","source","https://example.org","PAPER","",""))
    db.execute("INSERT INTO evidence_sources(id,source_id,state,content_hash,fetched_at,parsed_at,created_at) VALUES (?,?,?,?,?,?,?)",("es2","src2","PARSED","hash","now","now","now"))
    ev=EvidencePipeline(db).attach("c2","src2","excerpt",actor="alice")
    assert ev["excerpt_hash"]==hashlib.sha256(b"excerpt").hexdigest()
