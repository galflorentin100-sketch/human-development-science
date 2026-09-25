import uuid

from app.database import Database
from app.workflow import ResearchCycle
from app.models import now
from app.evidence_pipeline import EvidencePipeline
from app.research import ResearchFindingService
from app.finding_claim_bridge import FindingClaimBridge
from app.claim_state import ClaimStateService
from app.science import ScientificRegistry
from app.intervention_lifecycle import InterventionLifecycle
from app.training import TrainingProtocolService


def _project(db):
    cid, aid, pid = [str(uuid.uuid4()) for _ in range(3)]
    db.execute(
        "INSERT INTO companies(id,name,mission,vision,core_principle,created_at) VALUES (?,?,?,?,?,?)",
        (cid, "HDS", "science", "training", "truth", now()),
    )
    db.execute(
        "INSERT INTO agents(id,name,role,mission,capabilities,permissions,version,status,created_at) VALUES (?,?,?,?,?,?,?,?,?)",
        (aid, "test-agent", "researcher", "test", "[]", "[]", "1", "ACTIVE", now()),
    )
    db.execute(
        "INSERT INTO projects(id,company_id,objective,status,owner_agent_id,created_at) VALUES (?,?,?,?,?,?)",
        (pid, cid, "integration", "ACTIVE", aid, now()),
    )
    return pid


def _verified_evidence(db, claim_id, suffix):
    source_id = str(uuid.uuid4())
    db.execute(
        "INSERT INTO sources(id,title,url,source_type,verified_at,provenance_note) VALUES (?,?,?,?,?,?)",
        (source_id, "source", f"https://example.com/{source_id}", "PAPER", "", "test"),
    )
    pipe = EvidencePipeline(db)
    pipe.ingest_text(source_id, f"evidence-{suffix}")
    ev = pipe.attach(claim_id, source_id, f"excerpt-{suffix}")
    pipe.review(ev["id"], f"reviewer-{suffix}", "VERIFIED", "independently checked")
    return ev["id"]


def test_full_scientific_to_training_lifecycle(tmp_path):
    db = Database(str(tmp_path / "full-lifecycle.db"))
    ResearchCycle(db)
    project_id = _project(db)

    original_claim_id = str(uuid.uuid4())
    db.execute(
        "INSERT INTO claims(id,project_id,statement,classification,evidence_level,confidence,status,created_at) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (
            original_claim_id,
            project_id,
            "Structured practice may improve goal-directed self-regulation.",
            "HYPOTHESIS",
            "PRELIMINARY",
            0.0,
            "PROPOSED",
            now(),
        ),
    )
    evidence_id = _verified_evidence(db, original_claim_id, "claim")

    finding = ResearchFindingService(db).create(
        project_id,
        "Structured practice may improve goal-directed self-regulation.",
        classification="INFERENCE",
        source_type="MEASUREMENT",
        evidence_refs=(evidence_id,),
        interpretation="The observed measurement is consistent with the stated inference; this does not establish causality.",
    )
    accepted = ResearchFindingService(db).review(
        finding["id"], "independent-reviewer", "ACCEPTED", "Evidence was verified.",
    )
    assert accepted["status"] == "ACCEPTED"

    proposed = FindingClaimBridge(db).propose_claim(finding["id"], "bridge-agent")
    claim_id = proposed["claim_id"]
    ClaimStateService(db).transition(
        claim_id, "SUPPORTED", "reviewer", "Verified supporting evidence.", evidence_id
    )
    assert db.one("SELECT status FROM claims WHERE id=?", (claim_id,))["status"] == "SUPPORTED"

    registry = ScientificRegistry(db)
    intervention = registry.intervention(
        "structured-practice",
        "candidate intervention",
        "structured self-regulation practice",
        "PRELIMINARY",
        "4 weeks",
        "adults",
        status="EXPERIMENTAL",
    )
    registry.intervention_evidence(intervention["id"], "PILOT", evidence_id, "linked verified evidence")
    InterventionLifecycle(db).promote(intervention["id"], "PILOT", "reviewer", "pilot admission")
    db.execute("UPDATE interventions SET evidence_level='SUPPORTED' WHERE id=?", (intervention["id"],))
    InterventionLifecycle(db).promote(intervention["id"], "SUPPORTED", "reviewer", "verified evidence supports lifecycle admission")

    training = TrainingProtocolService(db).create(
        project_id,
        "structured-self-regulation-training",
        "Repeated structured practice may affect goal-directed behavior.",
        "goal pursuit under distraction",
        "4 weeks",
        "increase practice demand after predefined success criteria",
        "independent real-world goal execution",
        "8-week retention assessment",
        "stop criteria and participant safety monitoring",
        evidence_level="PRELIMINARY",
        source_claim_id=claim_id,
        intervention_id=intervention["id"],
    )
    TrainingProtocolService(db).attach_evidence(
        training["id"], "VERIFIED_SOURCE", evidence_id, "linked reviewed evidence"
    )
    TrainingProtocolService(db).promote(training["id"], "PILOT", "reviewer", "pilot admission")
    TrainingProtocolService(db).session(
        training["id"], "participant-1", 1, "baseline load", 1,
        task_success=0.5, transfer_score=0.4, retention_score=0.3,
    )
    supported = TrainingProtocolService(db).promote(
        training["id"], "SUPPORTED", "reviewer", "pilot produced transfer and retention observations"
    )

    assert supported["status"] == "SUPPORTED"
    readiness = TrainingProtocolService(db).readiness(training["id"])
    assert readiness["scientific_basis"]["source_claim_id"] == claim_id
    assert readiness["scientific_basis"]["intervention_id"] == intervention["id"]
