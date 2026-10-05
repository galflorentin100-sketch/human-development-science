import pytest

from app.database import Database
from app.workflow import ResearchCycle
from app.evidence_pipeline import EvidencePipeline
from app.research import ResearchFindingService
from app.finding_claim_bridge import FindingClaimBridge
from app.claim_state import ClaimStateService
from app.science import ScientificRegistry
from app.intervention_lifecycle import InterventionLifecycle
from app.training import TrainingProtocolService
from app.participant_governance import ParticipantGovernance
from app.outcome_feedback import OutcomeFeedbackService
from app.training_outcomes import TrainingOutcomeAnalyzer


def test_full_scientific_lifecycle_requires_governed_transitions(tmp_path):
    db = Database(str(tmp_path / "full-lifecycle.db"))
    project = ResearchCycle(db).run("full scientific lifecycle")["project"]
    pid = project["id"]

    pipeline = EvidencePipeline(db)
    source = pipeline.register_source(
        "Lifecycle source",
        "https://example.org/lifecycle-source",
    )
    pipeline.ingest_text(source["id"], "verified lifecycle excerpt")

    # Evidence must first belong to a claim, but that seed claim is not the
    # eventual scientific claim promoted from the reviewed finding.
    import uuid
    seed_claim = str(uuid.uuid4())
    db.execute(
        """INSERT INTO claims
        (id,project_id,statement,classification,evidence_level,confidence,status,created_at)
        VALUES (?,?,?,?,?,?,?,?)""",
        (seed_claim, pid, "seed evidence claim", "HYPOTHESIS",
         "PRELIMINARY", 0.1, "PROPOSED", project["created_at"]),
    )
    evidence = pipeline.attach(
        seed_claim, source["id"], "verified lifecycle excerpt"
    )
    pipeline.review(evidence["id"], "independent-reviewer", "VERIFIED", "checked")

    finding = ResearchFindingService(db).create(
        pid,
        "The reviewed lifecycle evidence supports a candidate training basis.",
        classification="INFERENCE",
        source_type="LITERATURE",
        source_id=None,
        evidence_refs=[evidence["id"]],
        interpretation="Descriptive evidence-grounded interpretation only.",
        created_by="researcher",
    )
    accepted = ResearchFindingService(db).review(
        finding["id"], "independent-reviewer-2", "ACCEPTED", "evidence verified"
    )
    assert accepted["status"] == "ACCEPTED"

    claim = FindingClaimBridge(db).propose_claim(
        finding["id"], "chief-scientist"
    )
    assert claim["status"] == "PROPOSED"
    claim_id = claim["claim_id"]

    claim_evidence = pipeline.attach(
        claim_id, source["id"], "verified lifecycle excerpt"
    )
    pipeline.review(
        claim_evidence["id"], "independent-reviewer-3", "VERIFIED", "checked"
    )
    supported = ClaimStateService(db).transition(
        claim_id,
        "SUPPORTED",
        "chief-scientist",
        "verified supporting evidence",
        evidence_id=claim_evidence["id"],
    )
    assert supported["status"] == "SUPPORTED"

    registry = ScientificRegistry(db)
    intervention = registry.intervention(
        "Lifecycle intervention",
        "test intervention",
        "test mechanism",
        "PRELIMINARY",
        "daily",
        "adults",
        project_id=pid,
    )
    registry.intervention_evidence(
        intervention["id"], "OBSERVATIONAL", claim_evidence["id"], "verified basis"
    )
    pilot = InterventionLifecycle(db).promote(
        intervention["id"], "PILOT", "chief-scientist", "begin governed pilot"
    )
    assert pilot["status"] == "PILOT"

    protocol = TrainingProtocolService(db).create(
        pid,
        "Lifecycle protocol",
        "mechanism hypothesis",
        "challenge",
        "one session",
        "progress conservatively",
        "real-world transfer",
        "retention follow-up",
        "stop on adverse event",
        source_claim_id=claim_id,
        intervention_id=intervention["id"],
    )
    pilot_protocol = TrainingProtocolService(db).promote(
        protocol["id"], "PILOT", "chief-scientist", "start pilot"
    )
    assert pilot_protocol["status"] == "PILOT"

    participant = "participant-pseudonymous-001"
    ParticipantGovernance(db).register(participant, "consent-v1")
    session = TrainingProtocolService(db).session(
        protocol["id"],
        participant,
        1,
        "baseline dose",
        1,
        task_success=0.7,
        transfer_score=0.6,
        retention_score=0.5,
        safety_checks={"fatigue": "CLEAR", "pain": "CLEAR"},
    )
    assert session["participant_ref"] == participant

    summary = TrainingOutcomeAnalyzer(db).summarize(protocol["id"])
    assert summary["n_sessions"] == 1
    assert summary["mean_transfer_score"] == 0.6
    assert summary["mean_retention_score"] == 0.5

    feedback = OutcomeFeedbackService(db).propose_from_training(
        protocol["id"], participant_ref=participant, created_by="researcher"
    )
    assert feedback["status"] == "CANDIDATE"
    assert feedback["scientific_status"] == "CANDIDATE_ONLY"
    assert feedback["research_proposal"]["status"] == "PROPOSED"
    assert "Investigate observed training outcomes" in feedback["research_proposal"]["question"]
    next_question=db.one(
        "SELECT * FROM research_questions WHERE project_id=? AND question=?",
        (pid, feedback["research_proposal"]["question"]),
    )
    assert next_question["status"] == "OPEN"
    assert next_question["trigger_type"] == "OUTCOME_FEEDBACK"

    candidate = db.one(
        "SELECT * FROM research_findings WHERE id=?",
        (feedback["finding_id"],),
    )
    assert candidate["status"] == "CANDIDATE"
    assert candidate["classification"] == "INFERENCE"

    # Training outcome feedback is never silently promoted to accepted science:
    # it has no evidence references and therefore cannot pass the acceptance gate.
    with pytest.raises(ValueError, match="evidence reference"):
        ResearchFindingService(db).review(
            candidate["id"], "independent-reviewer-4", "ACCEPTED", "accept"
        )
