from app.database import Database
from app.workflow import ResearchCycle
from app.evidence_pipeline import EvidencePipeline
from app.research_evidence_synthesis import ResearchEvidenceSynthesizer
from app.models import now
from uuid import uuid4


def _claim(db, project_id, statement):
    claim_id = str(uuid4())
    db.execute(
        "INSERT INTO claims(id,project_id,statement,classification,evidence_level,confidence,status,created_at) VALUES (?,?,?,?,?,?,?,?)",
        (claim_id, project_id, statement, "HYPOTHESIS", "UNVERIFIED", 0.0, "OPEN", now()),
    )
    return claim_id


def _verified_excerpt(db, pipeline, claim_id, title, url, stance, reviewer):
    source = pipeline.register_source(title, url, authors="Test team", year=2024)
    text = f"Abstract excerpt for {title}."
    pipeline.ingest_text(source["id"], text)
    evidence = pipeline.attach(claim_id, source["id"], text, stance=stance)
    pipeline.review(evidence["id"], reviewer, "VERIFIED", "Excerpt checked against stored source text.")
    return evidence["id"]


def test_synthesis_maps_verified_agreement_and_disagreement_without_mutation(tmp_path):
    db = Database(str(tmp_path / "evidence-map.db"))
    project = ResearchCycle(db).run("Evidence map")["project"]
    pipeline = EvidencePipeline(db)
    claim_id = _claim(db, project["id"], "Implementation intentions improve adherence.")

    _verified_excerpt(db, pipeline, claim_id, "Study A", "https://example.org/a", "SUPPORTS", "reviewer-a")
    _verified_excerpt(db, pipeline, claim_id, "Study B", "https://example.org/b", "SUPPORTS", "reviewer-b")
    _verified_excerpt(db, pipeline, claim_id, "Study C", "https://example.org/c", "CONTRADICTS", "reviewer-c")
    before = db.one("SELECT status,evidence_level,confidence FROM claims WHERE id=?", (claim_id,))

    result = ResearchEvidenceSynthesizer(db).synthesize_project(project["id"])
    row = next(x for x in result["claims"] if x["claim_id"] == claim_id)

    assert row["pattern"] == "MIXED_VERIFIED_STANCES"
    assert row["counts"]["distinct_supporting_sources"] == 2
    assert row["counts"]["distinct_contradicting_sources"] == 1
    assert len(row["verified_evidence"]) == 3
    after = db.one("SELECT status,evidence_level,confidence FROM claims WHERE id=?", (claim_id,))
    assert dict(after) == dict(before)
    assert "not a systematic review" in " ".join(result["limitations"]).lower()


def test_synthesis_excludes_unreviewed_evidence(tmp_path):
    db = Database(str(tmp_path / "unreviewed-evidence.db"))
    project = ResearchCycle(db).run("Unreviewed evidence map")["project"]
    pipeline = EvidencePipeline(db)
    claim_id = _claim(db, project["id"], "A candidate claim.")
    source = pipeline.register_source("Unreviewed", "https://example.org/unreviewed")
    excerpt = "This excerpt has not been reviewed."
    pipeline.ingest_text(source["id"], excerpt)
    pipeline.attach(claim_id, source["id"], excerpt, stance="SUPPORTS")

    result = ResearchEvidenceSynthesizer(db).synthesize_project(project["id"])
    row = next(x for x in result["claims"] if x["claim_id"] == claim_id)

    assert row["pattern"] == "NO_VERIFIED_EVIDENCE"
    assert row["counts"]["excluded_nonverified_items"] == 1
    assert row["verified_evidence"] == []



def test_evidence_map_includes_only_explicitly_recorded_study_descriptors(tmp_path):
    db = Database(str(tmp_path / "study-descriptors.db"))
    project = ResearchCycle(db).run("Study descriptors")["project"]
    pipeline = EvidencePipeline(db)
    claim_id = _claim(db, project["id"], "A claim about training.")
    evidence_id = _verified_excerpt(
        db, pipeline, claim_id, "Study with descriptors",
        "https://example.org/descriptors", "SUPPORTS", "independent-reviewer"
    )
    source_id = db.one("SELECT source_id FROM evidence WHERE id=?", (evidence_id,))["source_id"]
    study_id = str(uuid4())
    db.execute(
        "INSERT INTO studies(id,source_id,project_id,title,design,population,findings,created_at) VALUES (?,?,?,?,?,?,?,?)",
        (study_id, source_id, project["id"], "Recorded cohort study", "Prospective cohort", "Adults aged 18-35", "Adherence improved in this recorded dataset.", now()),
    )

    result = ResearchEvidenceSynthesizer(db).synthesize_project(project["id"])
    row = next(x for x in result["claims"] if x["claim_id"] == claim_id)

    descriptors = row["recorded_study_descriptors"]
    assert descriptors[0]["source_id"] == source_id
    assert descriptors[0]["studies"][0]["design"] == "Prospective cohort"
    assert descriptors[0]["studies"][0]["population"] == "Adults aged 18-35"
