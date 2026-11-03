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



def test_study_comparison_preserves_literal_values_and_missingness(tmp_path):
    db = Database(str(tmp_path / "study-comparison.db"))
    project = ResearchCycle(db).run("Study comparison")["project"]
    pipeline = EvidencePipeline(db)
    claim_id = _claim(db, project["id"], "A training claim.")

    evidence_ids = [
        _verified_excerpt(db, pipeline, claim_id, "Study one", "https://example.org/one", "SUPPORTS", "reviewer-one"),
        _verified_excerpt(db, pipeline, claim_id, "Study two", "https://example.org/two", "SUPPORTS", "reviewer-two"),
    ]
    source_ids = [
        db.one("SELECT source_id FROM evidence WHERE id=?", (eid,))["source_id"]
        for eid in evidence_ids
    ]
    db.execute(
        "INSERT INTO studies(id,source_id,project_id,title,design,population,findings,created_at) VALUES (?,?,?,?,?,?,?,?)",
        (str(uuid4()), source_ids[0], project["id"], "Study one record", "Randomized trial", "Adults", "Outcome A improved", now()),
    )
    db.execute(
        "INSERT INTO studies(id,source_id,project_id,title,design,population,findings,created_at) VALUES (?,?,?,?,?,?,?,?)",
        (str(uuid4()), source_ids[1], project["id"], "Study two record", "Prospective cohort", "Adolescents", "Outcome B unchanged", now()),
    )

    result = ResearchEvidenceSynthesizer(db).synthesize_project(project["id"])
    row = next(x for x in result["claims"] if x["claim_id"] == claim_id)
    comparison = row["study_comparison"]

    assert comparison["design"]["distinct_literal_values"] == 2
    assert {x["value"] for x in comparison["design"]["recorded_values"]} == {
        "Randomized trial", "Prospective cohort"
    }
    assert comparison["population"]["distinct_literal_values"] == 2
    assert comparison["findings"]["status"] == "RECORDED_VALUES_PRESENT"
    assert comparison["design"]["verified_sources_without_study_record"] == []


def test_evidence_map_summarizes_recorded_outcomes_within_study_and_preserves_missingness(tmp_path):
    db = Database(str(tmp_path / "study-outcomes.db"))
    project = ResearchCycle(db).run("Study outcome summaries")["project"]
    pipeline = EvidencePipeline(db)
    claim_id = _claim(db, project["id"], "A claim about self-discipline.")
    evidence_id = _verified_excerpt(
        db, pipeline, claim_id, "Outcome study",
        "https://example.org/outcomes", "SUPPORTS", "independent-reviewer"
    )
    source_id = db.one("SELECT source_id FROM evidence WHERE id=?", (evidence_id,))["source_id"]
    study_id = str(uuid4())
    db.execute(
        "INSERT INTO studies(id,source_id,project_id,title,design,population,findings,created_at) VALUES (?,?,?,?,?,?,?,?)",
        (study_id, source_id, project["id"], "Recorded outcome study", "Pilot", "Adults", "Recorded outcome data", now()),
    )
    participant_ids = [str(uuid4()) for _ in range(3)]
    for index, participant_id in enumerate(participant_ids):
        db.execute(
            "INSERT INTO study_participants(id,study_id,external_ref,consent_status,created_at) VALUES (?,?,?,?,?)",
            (participant_id, study_id, f"participant-{index}", "CONSENTED", now()),
        )
    for participant_id, value, missing_reason in [
        (participant_ids[0], 8.0, None),
        (participant_ids[1], 10.0, None),
        (participant_ids[2], None, "WITHDREW"),
    ]:
        db.execute(
            """INSERT INTO study_outcomes(
                   id,study_id,participant_id,session_id,outcome_name,value,unit,
                   missing_reason,observation_type,recorded_at
               ) VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (str(uuid4()), study_id, participant_id, None, "Self-regulation score",
             value, "points", missing_reason, "POST", now()),
        )

    result = ResearchEvidenceSynthesizer(db).synthesize_project(project["id"])
    row = next(x for x in result["claims"] if x["claim_id"] == claim_id)
    study_outcomes = row["recorded_study_outcomes"][0]["studies"][0]["outcomes"][0]

    assert study_outcomes["outcome_name"] == "Self-regulation score"
    assert study_outcomes["unit"] == "points"
    assert study_outcomes["records_total"] == 3
    assert study_outcomes["participants_total"] == 3
    assert study_outcomes["n_observed"] == 2
    assert study_outcomes["n_missing"] == 1
    assert study_outcomes["missing_reasons"] == {"WITHDREW": 1}
    assert study_outcomes["minimum"] == 8.0
    assert study_outcomes["maximum"] == 10.0
    assert study_outcomes["mean"] == 9.0
    assert study_outcomes["median"] == 9.0


def test_evidence_map_summarizes_recorded_adherence_by_phase_without_calling_it_an_outcome(tmp_path):
    db = Database(str(tmp_path / "study-adherence.db"))
    project = ResearchCycle(db).run("Study adherence")["project"]
    pipeline = EvidencePipeline(db)
    claim_id = _claim(db, project["id"], "A claim about intervention adherence.")
    evidence_id = _verified_excerpt(
        db, pipeline, claim_id, "Adherence study",
        "https://example.org/adherence", "SUPPORTS", "independent-reviewer"
    )
    source_id = db.one("SELECT source_id FROM evidence WHERE id=?", (evidence_id,))["source_id"]
    study_id = str(uuid4())
    db.execute(
        "INSERT INTO studies(id,source_id,project_id,title,design,population,findings,created_at) VALUES (?,?,?,?,?,?,?,?)",
        (study_id, source_id, project["id"], "Recorded adherence study", "Pilot", "Adults", "Adherence records", now()),
    )
    participant_ids = [str(uuid4()) for _ in range(2)]
    for index, participant_id in enumerate(participant_ids):
        db.execute(
            "INSERT INTO study_participants(id,study_id,external_ref,consent_status,created_at) VALUES (?,?,?,?,?)",
            (participant_id, study_id, f"adherence-participant-{index}", "CONSENTED", now()),
        )
    session_id = str(uuid4())
    db.execute(
        "INSERT INTO study_sessions(id,study_id,participant_id,phase,session_number,occurred_at,status) VALUES (?,?,?,?,?,?,?)",
        (session_id, study_id, participant_ids[0], "INTERVENTION", 1, now(), "COMPLETED"),
    )
    for participant_id, planned, completed in [
        (participant_ids[0], 4, 3),
        (participant_ids[1], 4, 2),
    ]:
        db.execute(
            "INSERT INTO study_adherence(id,study_id,participant_id,session_id,planned,completed,adherence_note,recorded_at) VALUES (?,?,?,?,?,?,?,?)",
            (str(uuid4()), study_id, participant_id, session_id, planned, completed, None, now()),
        )

    result = ResearchEvidenceSynthesizer(db).synthesize_project(project["id"])
    row = next(x for x in result["claims"] if x["claim_id"] == claim_id)
    adherence = row["recorded_study_adherence"][0]["studies"][0]["phases"][0]

    assert adherence["phase"] == "INTERVENTION"
    assert adherence["records_total"] == 2
    assert adherence["participants_total"] == 2
    assert adherence["planned_total"] == 8
    assert adherence["completed_total"] == 5
    assert adherence["completion_rate"] == 0.625
    assert "process measure" in " ".join(result["limitations"]).lower() or "causal inference" in " ".join(result["limitations"]).lower()
