from app.database import Database
from app.evidence_pipeline import EvidencePipeline
from app.workflow import ResearchCycle


def _evidence(db, tmp_path, verdicts):
    project = ResearchCycle(db).run("evidence resolution matrix")["project"]
    pipeline = EvidencePipeline(db)
    source = pipeline.register_source(
        "Resolution source",
        "https://example.org/resolution-matrix",
    )
    pipeline.ingest_text(source["id"], "resolution excerpt")
    claim = db.one("SELECT id FROM claims WHERE project_id=? LIMIT 1", (project["id"],))
    if not claim:
        import uuid
        claim_id = str(uuid.uuid4())
        db.execute(
            """INSERT INTO claims
            (id,project_id,statement,classification,evidence_level,confidence,status,created_at)
            VALUES (?,?,?,?,?,?,?,?)""",
            (claim_id, project["id"], "resolution claim", "HYPOTHESIS",
             "PRELIMINARY", 0.1, "PROPOSED", project["created_at"]),
        )
        claim = {"id": claim_id}
    evidence = pipeline.attach(claim["id"], source["id"], "resolution excerpt")
    for index, verdict in enumerate(verdicts):
        pipeline.review(
            evidence["id"],
            f"reviewer-{index}",
            verdict,
            f"resolution matrix: {verdict}",
        )
    return pipeline.resolve(evidence["id"])


def test_verified_and_uncertain_resolves_to_uncertain(tmp_path):
    db = Database(str(tmp_path / "verified-uncertain.db"))
    resolved = _evidence(db, tmp_path, ["VERIFIED", "UNCERTAIN"])
    assert resolved["state"] == "UNCERTAIN"


def test_verified_and_rejected_resolves_to_conflicted(tmp_path):
    db = Database(str(tmp_path / "verified-rejected.db"))
    resolved = _evidence(db, tmp_path, ["VERIFIED", "REJECTED"])
    assert resolved["state"] == "CONFLICTED"


def test_verified_only_resolves_to_verified(tmp_path):
    db = Database(str(tmp_path / "verified-only.db"))
    resolved = _evidence(db, tmp_path, ["VERIFIED"])
    assert resolved["state"] == "VERIFIED"


def test_rejected_only_resolves_to_rejected(tmp_path):
    db = Database(str(tmp_path / "rejected-only.db"))
    resolved = _evidence(db, tmp_path, ["REJECTED"])
    assert resolved["state"] == "REJECTED"


def test_unreviewed_resolves_to_unreviewed(tmp_path):
    db = Database(str(tmp_path / "unreviewed.db"))
    project = ResearchCycle(db).run("unreviewed resolution")["project"]
    pipeline = EvidencePipeline(db)
    source = pipeline.register_source(
        "Unreviewed source",
        "https://example.org/unreviewed-resolution",
    )
    pipeline.ingest_text(source["id"], "unreviewed excerpt")
    import uuid
    claim_id = str(uuid.uuid4())
    db.execute(
        """INSERT INTO claims
        (id,project_id,statement,classification,evidence_level,confidence,status,created_at)
        VALUES (?,?,?,?,?,?,?,?)""",
        (claim_id, project["id"], "unreviewed claim", "HYPOTHESIS",
         "PRELIMINARY", 0.1, "PROPOSED", project["created_at"]),
    )
    evidence = pipeline.attach(claim_id, source["id"], "unreviewed excerpt")
    assert pipeline.resolve(evidence["id"])["state"] == "UNREVIEWED"
