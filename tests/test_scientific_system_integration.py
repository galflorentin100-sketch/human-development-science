from app.database import Database
from app.workflow import ResearchCycle
from app.evidence_pipeline import EvidencePipeline
from app.knowledge_freshness import KnowledgeFreshness
from app.knowledge_impact import KnowledgeImpactAnalyzer
from app.scientific_admission import ScientificAdmissionGate
import uuid

def _setup(db):
    from app.models import now
    c,a,p=[str(uuid.uuid4()) for _ in range(3)]
    db.execute("INSERT INTO companies(id,name,mission,vision,core_principle,created_at) VALUES (?,?,?,?,?,?)",(c,"c","m","v","p",now()))
    db.execute("INSERT INTO agents(id,name,role,mission,capabilities,permissions,version,status,created_at) VALUES (?,?,?,?,?,?,?,?,?)",(a,"a","r","m","[]","[]","1","ACTIVE",now()))
    db.execute("INSERT INTO projects(id,company_id,objective,status,owner_agent_id,created_at) VALUES (?,?,?,?,?,?)",(p,c,"o","ACTIVE",a,now()))
    return p

def test_uncertain_verdict_cannot_resolve_verified(tmp_path):
    db=Database(str(tmp_path/"u.db")); ResearchCycle(db); pid=_setup(db)
    from app.models import now
    claim=str(uuid.uuid4()); source=str(uuid.uuid4())
    db.execute("INSERT INTO claims(id,project_id,statement,classification,evidence_level,confidence,status,created_at) VALUES (?,?,?,?,?,?,?,?)",(claim,pid,"x","HYPOTHESIS","PRELIMINARY",0.0,"PROPOSED",now()))
    db.execute("INSERT INTO sources(id,title,url,source_type,verified_at,provenance_note) VALUES (?,?,?,?,?,?)",(source,"s","https://x/"+source,"PAPER","","test"))
    ep=EvidencePipeline(db); ep.ingest_text(source,"text"); ev=ep.attach(claim,source,"excerpt")
    ep.review(ev["id"],"r1","VERIFIED","checked")
    ep.review(ev["id"],"r2","UNCERTAIN","uncertain")
    assert ep.resolve(ev["id"])["state"]=="UNCERTAIN"

def test_supported_claim_admission_requires_verified_nonconflicted_evidence(tmp_path):
    db=Database(str(tmp_path/"a.db")); ResearchCycle(db); pid=_setup(db)
    from app.models import now
    claim=str(uuid.uuid4())
    db.execute("INSERT INTO claims(id,project_id,statement,classification,evidence_level,confidence,status,created_at) VALUES (?,?,?,?,?,?,?,?)",(claim,pid,"x","FACT","SUPPORTED",1.0,"SUPPORTED",now()))
    gate=ScientificAdmissionGate(db)
    result=gate.claim(claim)
    assert result["supported"] is False
    assert result["verified_evidence"]==0

def test_knowledge_impact_identifies_downstream_training(tmp_path):
    db=Database(str(tmp_path/"i.db")); ResearchCycle(db); pid=_setup(db)
    from app.models import now
    claim=str(uuid.uuid4()); protocol=str(uuid.uuid4())
    db.execute("INSERT INTO claims(id,project_id,statement,classification,evidence_level,confidence,status,created_at) VALUES (?,?,?,?,?,?,?,?)",(claim,pid,"x","FACT","SUPPORTED",1.0,"SUPPORTED",now()))
    db.execute("""INSERT INTO training_protocols(id,project_id,name,target_construct_id,source_claim_id,intervention_id,mechanism_hypothesis,challenge_domain,dosage,progression_rule,transfer_target,retention_target,safety_constraints,evidence_level,status,version,created_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",(protocol,pid,"p",None,claim,None,"m","challenge","dose","progress","transfer","retention","safety","PRELIMINARY","PILOT",1,now()))
    impact=KnowledgeImpactAnalyzer(db).claim_impact(claim)
    assert any(x["id"]==protocol for x in impact["downstream"]["training_protocols"])
    assert impact["review_required"] is True

def test_freshness_register_and_scan(tmp_path):
    db=Database(str(tmp_path/"f.db")); ResearchCycle(db); pid=_setup(db)
    from app.models import now
    claim=str(uuid.uuid4())
    db.execute("INSERT INTO claims(id,project_id,statement,classification,evidence_level,confidence,status,created_at) VALUES (?,?,?,?,?,?,?,?)",(claim,pid,"x","HYPOTHESIS","PRELIMINARY",0.0,"PROPOSED",now()))
    row=KnowledgeFreshness(db).register("CLAIM",claim,90,"tester")
    assert row["status"]=="ACTIVE"
    db.execute("UPDATE knowledge_freshness SET next_review_at=? WHERE id=?",( "2000-01-01T00:00:00+00:00",row["id"]))
    scan=KnowledgeFreshness(db).scan()
    assert scan["stale_count"]==1
