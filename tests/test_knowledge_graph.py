from app.database import Database
from app.workflow import ResearchCycle
from app.knowledge_graph import KnowledgeDependencyGraph
import uuid

def _setup(db):
    from app.models import now
    c,a,p=[str(uuid.uuid4()) for _ in range(3)]
    db.execute("INSERT INTO companies(id,name,mission,vision,core_principle,created_at) VALUES (?,?,?,?,?,?)",(c,"c","m","v","p",now()))
    db.execute("INSERT INTO agents(id,name,role,mission,capabilities,permissions,version,status,created_at) VALUES (?,?,?,?,?,?,?,?,?)",(a,"a","r","m","[]","[]","1","ACTIVE",now()))
    db.execute("INSERT INTO projects(id,company_id,objective,status,owner_agent_id,created_at) VALUES (?,?,?,?,?,?)",(p,c,"o","ACTIVE",a,now()))
    return p

def test_explicit_edges_are_idempotent_and_traceable(tmp_path):
    db=Database(str(tmp_path/"graph.db")); ResearchCycle(db); pid=_setup(db)
    g=KnowledgeDependencyGraph(db)
    from app.models import now
    source,claim,evidence=[str(uuid.uuid4()) for _ in range(3)]
    db.execute("INSERT INTO sources(id,title,url,authors,publication_year,source_type,verified_at,provenance_note) VALUES (?,?,?,?,?,?,?,?)",(source,"s","https://example.org/s","","2026","PAPER","",""))
    db.execute("INSERT INTO claims(id,project_id,statement,classification,evidence_level,confidence,status,created_at) VALUES (?,?,?,?,?,?,?,?)",(claim,pid,"c","FACT","PRELIMINARY",0.5,"PROPOSED",now()))
    db.execute("INSERT INTO evidence(id,claim_id,source_id,stance,excerpt,verified,created_by,excerpt_hash,created_at) VALUES (?,?,?,?,?,?,?,?,?)",(evidence,claim,source,"SUPPORTS","x",1,"system","h",now()))
    g.add_edge(pid,"EVIDENCE",evidence,"SUPPORTS","CLAIM",claim,["source:1"],"reviewer")
    g.add_edge(pid,"EVIDENCE",evidence,"SUPPORTS","CLAIM",claim,["source:1"],"reviewer")
    trace=g.trace(pid,"EVIDENCE",evidence)
    assert trace["node_count"]==2
    assert any(n["type"]=="CLAIM" and n["id"]==claim for n in trace["nodes"])

def test_impact_trace_does_not_claim_efficacy(tmp_path):
    db=Database(str(tmp_path/"impact.db")); ResearchCycle(db); pid=_setup(db)
    from app.models import now
    claim,intervention,protocol=[str(uuid.uuid4()) for _ in range(3)]
    db.execute("INSERT INTO claims(id,project_id,statement,classification,evidence_level,confidence,status,created_at) VALUES (?,?,?,?,?,?,?,?)",(claim,pid,"c","FACT","PRELIMINARY",0.5,"PROPOSED",now()))
    db.execute("INSERT INTO interventions(id,project_id,name,target_construct_id,rationale,mechanism,evidence_level,dosage,population,status,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",(intervention,pid,"i",None,"r","m","PRELIMINARY","d","p","EXPERIMENTAL",now()))
    db.execute("INSERT INTO training_protocols(id,project_id,name,target_construct_id,source_claim_id,intervention_id,mechanism_hypothesis,challenge_domain,dosage,progression_rule,transfer_target,retention_target,safety_constraints,evidence_level,status,version,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(protocol,pid,"p",None,claim,intervention,"m","d","dose","progress","transfer","retention","safe","PRELIMINARY","DRAFT",1,now()))
    g=KnowledgeDependencyGraph(db)
    g.add_edge(pid,"CLAIM",claim,"INFORMS","INTERVENTION",intervention)
    g.add_edge(pid,"INTERVENTION",intervention,"IMPLEMENTED_BY","TRAINING_PROTOCOL",protocol)
    result=g.impacted(pid,"CLAIM",claim)
    assert result["node_count"]==2
    assert "causal" in result["policy"] or "efficacy" in result["policy"]


def test_sync_materializes_only_resolvable_explicit_relationships(tmp_path):
    db=Database(str(tmp_path/"sync.db")); ResearchCycle(db); pid=_setup(db)
    source,claim,protocol=[str(uuid.uuid4()) for _ in range(3)]
    from app.models import now
    db.execute("INSERT INTO sources(id,title,url,authors,publication_year,source_type,verified_at,provenance_note) VALUES (?,?,?,?,?,?,?,?)",(source,"s","https://example.org/s","","2026","PAPER","",""))
    db.execute("INSERT INTO claims(id,project_id,statement,classification,evidence_level,confidence,status,created_at) VALUES (?,?,?,?,?,?,?,?)",(claim,pid,"c","FACT","PRELIMINARY",0.5,"PROPOSED",now()))
    db.execute("INSERT INTO evidence(id,claim_id,source_id,stance,excerpt,verified,created_by,excerpt_hash,created_at) VALUES (?,?,?,?,?,?,?,?,?)",(str(uuid.uuid4()),claim,source,"SUPPORTS","x",0,"system","h",now()))
    from app.training import TrainingProtocolService
    p=TrainingProtocolService(db).create(pid,"p","m","d","dose","progress","transfer","retention","safe",source_claim_id=claim)
    result=KnowledgeDependencyGraph(db).sync_project(pid)
    graph=KnowledgeDependencyGraph(db).build(pid)
    assert len(graph["edges"]) >= 3
    graph=KnowledgeDependencyGraph(db).build(pid)
    assert any(e["relation"]=="GROUNDS" and e["from_id"]==claim for e in graph["edges"])


def test_sync_connects_experiment_and_result(tmp_path):
    db=Database(str(tmp_path/"experiment.db")); ResearchCycle(db); pid=_setup(db)
    from app.research import ResearchRepository
    h=ResearchRepository(db).hypothesis(pid,"Does training improve retention?")
    e=ResearchRepository(db).experiment(pid,h["id"],"pre-post")
    ResearchRepository(db).result(e["id"],"retention improved","descriptive result")
    result=KnowledgeDependencyGraph(db).sync_project(pid)
    graph=KnowledgeDependencyGraph(db).build(pid)
    assert any(x["relation"]=="TESTED_BY" and x["to_id"]==e["id"] for x in graph["edges"])
    assert any(x["relation"]=="HAS_RESULT" and x["from_id"]==e["id"] for x in graph["edges"])
    assert result["created_edges"] >= 2


def test_add_edge_rejects_cross_project_node(tmp_path):
    db=Database(str(tmp_path/"isolation.db")); ResearchCycle(db); p1=_setup(db); p2=_setup(db)
    from app.models import now
    claim=str(uuid.uuid4())
    db.execute("INSERT INTO claims(id,project_id,statement,classification,evidence_level,confidence,status,created_at) VALUES (?,?,?,?,?,?,?,?)",(claim,p2,"foreign","FACT","PRELIMINARY",0.5,"PROPOSED",now()))
    g=KnowledgeDependencyGraph(db)
    import pytest
    with pytest.raises(ValueError, match="belongs to another project"):
        g.add_edge(p1,"CLAIM",claim,"INFORMS","HYPOTHESIS","h")


def test_add_edge_rejects_unknown_node_type(tmp_path):
    db=Database(str(tmp_path/"unknown-node.db")); ResearchCycle(db); pid=_setup(db)
    import pytest
    with pytest.raises(ValueError, match="unsupported graph node type"):
        KnowledgeDependencyGraph(db).add_edge(pid,"UNKNOWN","x","RELATION","PROJECT",pid)

def test_source_edge_requires_source_in_project(tmp_path):
    db=Database(str(tmp_path/"source-isolation.db")); ResearchCycle(db); p1=_setup(db); p2=_setup(db)
    from app.models import now
    source,claim=[str(uuid.uuid4()) for _ in range(2)]
    db.execute("INSERT INTO sources(id,title,url,authors,publication_year,source_type,verified_at,provenance_note) VALUES (?,?,?,?,?,?,?,?)",(source,"s","https://example.org/source-isolation","","2026","PAPER","",""))
    db.execute("INSERT INTO claims(id,project_id,statement,classification,evidence_level,confidence,status,created_at) VALUES (?,?,?,?,?,?,?,?)",(claim,p2,"c","FACT","PRELIMINARY",0.5,"PROPOSED",now()))
    evidence=str(uuid.uuid4())
    db.execute("INSERT INTO evidence(id,claim_id,source_id,stance,excerpt,verified,created_by,excerpt_hash,created_at) VALUES (?,?,?,?,?,?,?,?,?)",(evidence,claim,source,"SUPPORTS","x",0,"system","source-isolation",now()))
    import pytest
    with pytest.raises(ValueError, match="belongs to another project"):
        KnowledgeDependencyGraph(db).add_edge(p1,"SOURCE",source,"HAS_EVIDENCE","EVIDENCE",evidence)


def test_sync_materializes_full_explicit_scientific_provenance_chain(tmp_path):
    from app.models import now
    db=Database(str(tmp_path/"provenance-chain.db")); ResearchCycle(db); pid=_setup(db)
    source,claim,evidence,intervention,protocol,finding,revision=[str(uuid.uuid4()) for _ in range(7)]
    db.execute("INSERT INTO sources(id,title,url,authors,publication_year,source_type,verified_at,provenance_note) VALUES (?,?,?,?,?,?,?,?)",
               (source,"s","https://example.org/provenance-chain","","2026","PAPER","",""))
    db.execute("INSERT INTO claims(id,project_id,statement,classification,evidence_level,confidence,status,created_at) VALUES (?,?,?,?,?,?,?,?)",
               (claim,pid,"claim","INFERENCE","VERIFIED",0.8,"SUPPORTED",now()))
    db.execute("INSERT INTO evidence(id,claim_id,source_id,stance,excerpt,verified,created_by,excerpt_hash,created_at) VALUES (?,?,?,?,?,?,?,?,?)",
               (evidence,claim,source,"SUPPORTS","excerpt",1,"system","hash",now()))
    db.execute("INSERT INTO interventions(id,project_id,name,target_construct_id,rationale,mechanism,evidence_level,dosage,population,status,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
               (intervention,pid,"intervention",None,"rationale","mechanism","PRELIMINARY","dose","population","EXPERIMENTAL",now()))
    db.execute("INSERT INTO training_protocols(id,project_id,name,target_construct_id,source_claim_id,intervention_id,mechanism_hypothesis,challenge_domain,dosage,progression_rule,transfer_target,retention_target,safety_constraints,evidence_level,status,version,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
               (protocol,pid,"protocol",None,claim,intervention,"mechanism","domain","dose","progression","transfer","retention","safety","PRELIMINARY","DRAFT",1,now()))
    db.execute("INSERT INTO training_protocol_evidence(id,protocol_id,evidence_kind,evidence_ref,notes,created_at) VALUES (?,?,?,?,?,?)",
               (str(uuid.uuid4()),protocol,"PILOT",evidence,"basis",now()))
    db.execute("INSERT INTO intervention_evidence(id,intervention_id,evidence_kind,evidence_ref,notes,created_at) VALUES (?,?,?,?,?,?)",
               (str(uuid.uuid4()),intervention,"PILOT",evidence,"basis",now()))
    db.execute("INSERT INTO research_findings(id,project_id,source_type,source_id,statement,classification,status,evidence_refs,interpretation,created_by,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
               (finding,pid,"EVIDENCE",evidence,"finding","INFERENCE","ACCEPTED",__import__("json").dumps([evidence]),"","reviewer",now()))
    db.execute("INSERT INTO claim_revisions(id,claim_id,prior_classification,prior_confidence,new_classification,new_confidence,reason,evidence_id,review_required,previous_statement,new_statement,previous_status,new_status,rationale,evidence_refs,revised_by,status,source_finding_id,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
               (revision,claim,"INFERENCE",0.5,"INFERENCE",0.8,"finding basis",evidence,1,"old","claim","PROPOSED","SUPPORTED","finding basis",__import__("json").dumps([evidence]),"reviewer","PROPOSED",finding,now()))
    version=__import__("app.claim_state",fromlist=["ClaimStateService"]).ClaimStateService(db).knowledge_version(claim,"reviewer","snapshot")
    graph=KnowledgeDependencyGraph(db)
    graph.sync_project(pid)
    edges=graph.build(pid)["edges"]
    assert any(e["from_type"]=="FINDING" and e["to_type"]=="CLAIM" and e["from_id"]==finding and e["to_id"]==claim for e in edges)
    assert any(e["from_type"]=="CLAIM" and e["to_type"]=="KNOWLEDGE_VERSION" and e["from_id"]==claim and e["to_id"]==version["id"] for e in edges)
    assert any(e["from_type"]=="EVIDENCE" and e["to_type"]=="INTERVENTION" and e["to_id"]==intervention for e in edges)
    assert any(e["from_type"]=="EVIDENCE" and e["to_type"]=="TRAINING_PROTOCOL" and e["to_id"]==protocol for e in edges)
