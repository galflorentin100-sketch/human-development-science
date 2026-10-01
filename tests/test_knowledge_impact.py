import uuid
from app.database import Database
from app.models import now
from app.workflow import ResearchCycle

def test_impact_engine_proposes_review(tmp_path):
    from app.knowledge_impact_engine import KnowledgeImpactEngine
    db=Database(str(tmp_path/"i.db")); ResearchCycle(db)
    pid=ResearchCycle(db).run("impact")["project"]["id"]
    cid=str(uuid.uuid4()); tid=str(uuid.uuid4())
    db.execute("INSERT INTO claims(id,project_id,statement,classification,evidence_level,confidence,status,created_at) VALUES (?,?,?,?,?,?,?,?)",(cid,pid,"claim","HYPOTHESIS","PRELIMINARY",0.1,"PROPOSED",now()))
    db.execute("INSERT INTO training_protocols(id,project_id,name,mechanism_hypothesis,challenge_domain,dosage,progression_rule,transfer_target,retention_target,safety_constraints,evidence_level,status,version,created_at,source_claim_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(tid,pid,"protocol","m","challenge","dose","progress","transfer","retention","safe","UNTESTED","DRAFT",1,now(),cid))
    out=KnowledgeImpactEngine(db).propagate(pid,"claims",cid)
    assert out["affected_count"]==1
    rows=KnowledgeImpactEngine(db).list(pid)
    assert rows[0]["affected_id"]==tid


def test_accepted_impact_review_only_queues_reassessment_not_action(tmp_path):
    from app.knowledge_impact_engine import KnowledgeImpactEngine
    db=Database(str(tmp_path/"review.db")); ResearchCycle(db)
    pid=ResearchCycle(db).run("impact governance")["project"]["id"]
    cid=str(uuid.uuid4())
    db.execute("INSERT INTO claims(id,project_id,statement,classification,evidence_level,confidence,status,created_at) VALUES (?,?,?,?,?,?,?,?)",(cid,pid,"supported claim","HYPOTHESIS","PRELIMINARY",0.8,"SUPPORTED",now()))
    baseline_tasks=db.all("SELECT id FROM tasks WHERE project_id=?",(pid,))
    review_id=str(uuid.uuid4())
    db.execute("""INSERT INTO knowledge_impact_reviews
        (id,project_id,source_type,source_id,impact_type,affected_type,affected_id,reason,status,created_at)
        VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (review_id,pid,"claims",cid,"GRAPH_DEPENDENCY","TRAINING_PROTOCOL","protocol-1",
         "Potential downstream impact","PROPOSED",now()))
    reviewed=KnowledgeImpactEngine(db).review(
        review_id,"founder","ACCEPT",
        "Reassess the dependency before any scientific state change.",
    )
    assert reviewed["status"]=="ACCEPTED"
    assert db.all("SELECT id FROM tasks WHERE project_id=?",(pid,)) == baseline_tasks
    assert len(db.all("SELECT id FROM hds_research_queue WHERE project_id=? AND status='PROPOSED'",(pid,))) == 1


def test_claim_impact_resolves_finding_refs_by_evidence_id_and_flags_knowledge_version(tmp_path):
    from app.knowledge_impact import KnowledgeImpactAnalyzer
    db=Database(str(tmp_path/"impact-claim.db")); ResearchCycle(db)
    pid=ResearchCycle(db).run("impact claim")["project"]["id"]
    cid=str(uuid.uuid4()); fid=str(uuid.uuid4()); eid=str(uuid.uuid4())
    db.execute("INSERT INTO claims(id,project_id,statement,classification,evidence_level,confidence,status,created_at) VALUES (?,?,?,?,?,?,?,?)",
               (cid,pid,"claim","HYPOTHESIS","PRELIMINARY",0.8,"SUPPORTED",now()))
    db.execute("INSERT INTO sources(id,title,url,source_type,verified_at,provenance_note) VALUES (?,?,?,?,?,?)",
               ("src","source","https://example.test","PAPER","",""))
    db.execute("INSERT INTO evidence(id,claim_id,source_id,stance,verified,created_by,excerpt_hash,created_at) VALUES (?,?,?,?,?,?,?,?)",
               (eid,cid,"src","SUPPORTS",1,"researcher","hash",now()))
    db.execute("INSERT INTO research_findings(id,project_id,source_type,statement,classification,status,evidence_refs,created_by,created_at) VALUES (?,?,?,?,?,?,?,?,?)",
               (fid,pid,"OBSERVATION","finding","HYPOTHESIS","CANDIDATE",'["'+eid+'"]',"researcher",now()))
    db.execute("INSERT INTO scientific_knowledge_versions(id,claim_id,version,statement,classification,status,confidence,evidence_state,evidence_snapshot_hash,change_reason,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
               ("kv",cid,1,"claim","HYPOTHESIS","SUPPORTED",0.8,"SUPPORTED","hash","initial",now()))
    out=KnowledgeImpactAnalyzer(db).claim_impact(cid)
    assert [f["id"] for f in out["downstream"]["research_findings"]]==[fid]
    assert len(out["knowledge_versions"])==1
    assert out["review_required"] is True
    assert "knowledge_version_exists" in out["review_reasons"]
