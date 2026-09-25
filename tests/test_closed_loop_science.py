from app.database import Database
from app.workflow import ResearchCycle
import uuid

def _setup(db):
    from app.models import now
    c,a,p=[str(uuid.uuid4()) for _ in range(3)]
    db.execute("INSERT INTO companies(id,name,mission,vision,core_principle,created_at) VALUES (?,?,?,?,?,?)",(c,"c","m","v","p",now()))
    db.execute("INSERT INTO agents(id,name,role,mission,capabilities,permissions,version,status,created_at) VALUES (?,?,?,?,?,?,?,?,?)",(a,"a","r","m","[]","[]","1","ACTIVE",now()))
    db.execute("INSERT INTO projects(id,company_id,objective,status,owner_agent_id,created_at) VALUES (?,?,?,?,?,?)",(p,c,"o","ACTIVE",a,now()))
    return p

def test_experiment_preregistration_gate(tmp_path):
    from app.experiment_engine import ExperimentEngine
    db=Database(str(tmp_path/"e.db")); ResearchCycle(db); pid=_setup(db)
    e=ExperimentEngine(db).create(
        pid,"Does challenge improve transfer?","challenge improves transfer",
        "randomized","adults","challenge","usual practice","transfer score",
        '{"outcome_name":"transfer","estimand":"between-arm","population":"adults","estimator":"difference","ci_method":"none","missing_data_policy":"complete-cases","multiplicity_policy":"none","subgroup_policy":"none","stopping_rule":"fixed","allowed_methods":["DESCRIPTIVE"]}'
    )
    assert e["status"]=="DRAFT"
    ready=ExperimentEngine(db).preregister(e["id"])
    assert ready["status"]=="READY" and ready["preregistered"]==1

def test_closed_loop_surfaces_missing_evidence(tmp_path):
    from app.training import TrainingProtocolService
    from app.closed_loop_engine import ClosedLoopEngine
    db=Database(str(tmp_path/"loop.db")); ResearchCycle(db); pid=_setup(db)
    protocol=TrainingProtocolService(db).create(
        pid,"p","m","challenge","dose","progress","transfer","retention","safety"
    )
    snapshot=ClosedLoopEngine(db).protocol(protocol["id"])
    assert "no_scientific_basis" in snapshot["readiness"]["blockers"]

def test_integrity_flags_supported_claim_without_evidence(tmp_path):
    from app.scientific_integrity import ScientificIntegrityChecker
    from app.models import now
    db=Database(str(tmp_path/"integrity.db")); ResearchCycle(db); pid=_setup(db)
    claim=str(uuid.uuid4())
    db.execute("INSERT INTO claims(id,project_id,statement,classification,evidence_level,confidence,status,created_at) VALUES (?,?,?,?,?,?,?,?)",
               (claim,pid,"x","FACT","SUPPORTED",1.0,"SUPPORTED",now()))
    result=ScientificIntegrityChecker(db).project(pid)
    assert result["integrity"]=="REVIEW_REQUIRED"
    assert any(x["type"]=="SUPPORTED_CLAIM_WITHOUT_EVIDENCE" for x in result["issues"])

def test_research_queue_requires_explicit_approval(tmp_path):
    from app.research_queue import ResearchQueue
    db=Database(str(tmp_path/"queue.db")); ResearchCycle(db); pid=_setup(db)
    q=ResearchQueue(db)
    row=q.propose(pid,"What changes transfer?","transfer evidence is incomplete","EVIDENCE_GAP",priority="HIGH")
    assert row["status"]=="PROPOSED"
    assert q.approve(row["id"],"founder")["status"]=="APPROVED"


def test_hds_experiment_result_is_in_knowledge_graph(tmp_path):
    from app.experiment_engine import ExperimentEngine
    from app.knowledge_graph import KnowledgeDependencyGraph
    db=Database(str(tmp_path/"hds_experiment.db")); ResearchCycle(db); pid=_setup(db)
    e=ExperimentEngine(db).create(
        pid,"q","h","pre-post","adults","intervention","control","retention",
        '{"outcome_name":"retention","estimand":"within","population":"adults","estimator":"difference","ci_method":"none","missing_data_policy":"complete-cases","multiplicity_policy":"none","subgroup_policy":"none","stopping_rule":"fixed","allowed_methods":["DESCRIPTIVE"]}'
    )
    ExperimentEngine(db).preregister(e["id"])
    ExperimentEngine(db).start(e["id"])
    result=ExperimentEngine(db).record_result(e["id"],"0.7","descriptive result")
    graph=KnowledgeDependencyGraph(db).build(pid)
    assert any(edge["relation"]=="HAS_RESULT" and edge["to_id"]==result["id"] for edge in graph["edges"])
