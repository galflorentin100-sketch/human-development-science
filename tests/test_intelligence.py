from app.database import Database
from app.intelligence import IntelligenceService
from app.workflow import ResearchCycle


def test_company_intelligence_snapshot_is_structured_and_read_only(tmp_path):
    db = Database(str(tmp_path / "intelligence.db"))
    project = ResearchCycle(db).run("intelligence project")["project"]

    result = IntelligenceService(db).health()
    assert result["agents"] >= 1
    assert result["model_calls"] >= 0
    assert project["id"]

    service = IntelligenceService(db)
    assert isinstance(service.findings(), list)
    assert isinstance(service.timeline(), list)
    assert isinstance(service.workforce(), list)


def test_company_intelligence_health_counts_track_work(tmp_path):
    db = Database(str(tmp_path / "intelligence_counts.db"))
    ResearchCycle(db).run("one")
    before = IntelligenceService(db).health()

    db.execute(
        "INSERT INTO risks(id,company_id,title,severity,status,created_at) VALUES (?,?,?,?,?,?)",
        ("risk-1", "hds", "test risk", "MEDIUM", "OPEN", "2026-01-01T00:00:00Z"),
    )
    after = IntelligenceService(db).health()

    assert after["open_risks"] == before["open_risks"] + 1


def test_intelligence_labels_nonaccepted_scientific_state(tmp_path):
    db = Database(str(tmp_path / "intelligence_state.db"))
    project = ResearchCycle(db).run("intelligence state")["project"]
    db.execute(
        "UPDATE claims SET status='PROPOSED' WHERE project_id=?",
        (project["id"],),
    )
    state = IntelligenceService(db).scientific_state(project["id"])
    assert state["accepted_claims"] == []
    assert all(x["scientific_state"] == "NOT_ACTIVE_KNOWLEDGE" for x in state["claims_requiring_review"])
    assert "Only scientifically admitted SUPPORTED claims" in state["policy"]


def test_intelligence_labels_candidate_and_accepted_findings(tmp_path):
    db = Database(str(tmp_path / "intelligence_findings.db"))
    project = ResearchCycle(db).run("intelligence findings")["project"]
    from app.research import ResearchFindingService
    ResearchFindingService(db).create(
        project["id"], "Candidate scientific observation", classification="HYPOTHESIS"
    )
    rows = IntelligenceService(db).findings()
    assert rows
    assert rows[0]["scientific_state"] == "CANDIDATE_REQUIRES_INDEPENDENT_REVIEW"
