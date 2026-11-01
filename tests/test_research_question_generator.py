from app.database import Database
from app.workflow import ResearchCycle
from app.experiment_engine import ExperimentEngine
from app.experiment_safety import ExperimentSafetyReviewer
from app.replication_engine import ReplicationEngine
from app.knowledge_graph import KnowledgeDependencyGraph
from app.research_question_generator import ResearchQuestionGenerator

def test_replication_is_explicit_graph_node(tmp_path):
    db=Database(str(tmp_path/"graph.db"))
    project=ResearchCycle(db).run("Graph replication")["project"]
    e=ExperimentEngine(db)
    exp=e.create(project["id"],"Q","H","D","P","I","C","O",'{"outcome":"O"}')
    e.preregister(exp["id"])
    ExperimentSafetyReviewer(db).review(exp["id"],"ACCEPT","review","reviewer")
    e.start(exp["id"]); e.record_result(exp["id"],"outcome","interpretation"); e.complete(exp["id"])
    rp=ReplicationEngine(db).propose(project["id"],exp["id"],"independent confirmation")
    graph=KnowledgeDependencyGraph(db).sync_project(project["id"])
    edge=db.one("SELECT * FROM knowledge_edges WHERE project_id=? AND from_type='REPLICATION_PROPOSAL' AND from_id=? AND relation='REPLICATES'",(project["id"],rp["id"]))
    assert edge is not None
    assert edge["to_id"]==exp["id"]

def test_question_generator_creates_review_questions_without_mutating_claims(tmp_path):
    db=Database(str(tmp_path/"questions.db"))
    project=ResearchCycle(db).run("Question generation")["project"]
    e=ExperimentEngine(db)
    exp=e.create(project["id"],"Q","H","D","P","I","C","O",'{"outcome":"O"}')
    e.preregister(exp["id"])
    ExperimentSafetyReviewer(db).review(exp["id"],"ACCEPT","review","reviewer")
    e.start(exp["id"]); e.record_result(exp["id"],"outcome","interpretation"); e.complete(exp["id"])
    rp=ReplicationEngine(db).propose(project["id"],exp["id"],"independent confirmation")
    ReplicationEngine(db).ready(rp["id"])
    ReplicationEngine(db).record_result(rp["id"],"descriptive outcome","no automatic conclusion")
    result=ResearchQuestionGenerator(db).generate(project["id"])
    assert any(x["trigger_type"]=="AUTONOMOUS_GAP_DETECTOR" for x in result["queue_items"])
    assert all(x["status"]=="PROPOSED" for x in result["queue_items"])



def test_question_generator_is_idempotent_for_open_followups(tmp_path):
    db=Database(str(tmp_path/"idempotent-questions.db"))
    project=ResearchCycle(db).run("Idempotent question generation")["project"]
    e=ExperimentEngine(db)
    exp=e.create(project["id"],"Q","H","D","P","I","C","O",'{"outcome":"O"}')
    e.preregister(exp["id"])
    ExperimentSafetyReviewer(db).review(exp["id"],"ACCEPT","review","reviewer")
    e.start(exp["id"]); e.record_result(exp["id"],"outcome","interpretation"); e.complete(exp["id"])
    rp=ReplicationEngine(db).propose(project["id"],exp["id"],"independent confirmation")
    ReplicationEngine(db).ready(rp["id"])
    ReplicationEngine(db).record_result(rp["id"],"descriptive outcome","no automatic conclusion")

    generator=ResearchQuestionGenerator(db)
    first=generator.generate(project["id"])
    second=generator.generate(project["id"])

    assert len(first["queue_items"]) == len(second["queue_items"])
    assert all(item["status"] == "PROPOSED" for item in second["queue_items"])
    assert "no claim" in second["policy"]



def test_question_generator_surfaces_recorded_synthesis_limitations(tmp_path):
    from app.research_engine import ResearchEngine
    from app.evidence_pipeline import EvidencePipeline

    db=Database(str(tmp_path/"synthesis-limitations.db"))
    project=ResearchCycle(db).run("Synthesis limitation follow-up")["project"]
    engine=ResearchEngine(db)
    workspace=engine.create(project["id"],"Does implementation planning improve long-term adherence?")
    engine.activate(workspace["id"],"researcher")
    source=EvidencePipeline(db).register_source(
        "Synthetic test paper","https://example.org/hds-synthetic-paper",
        authors="Test Author",year=2025
    )
    engine.add_source(workspace["id"],source["id"],content="Synthetic abstract for a unit test.")
    engine.synthesize(
        workspace["id"],
        "Candidate synthesis text.",
        limitations="Small and non-representative samples.",
        uncertainty="Long-term transfer remains unclear.",
        created_by="researcher",
    )

    result=ResearchQuestionGenerator(db).generate(project["id"])

    followups=[item for item in result["queue_items"] if item["trigger_type"]=="AUTONOMOUS_GAP_DETECTOR"]
    assert any("methodological limitations" in item["question"] for item in followups)
    limitation=next(item for item in followups if "methodological limitations" in item["question"])
    assert "non-representative samples" in limitation["rationale"]
    assert limitation["status"]=="PROPOSED"
