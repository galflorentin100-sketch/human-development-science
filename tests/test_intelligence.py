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


def test_scientific_knowledge_state_distinguishes_claim_status_and_freshness(tmp_path):
    db = Database(str(tmp_path / "knowledge_state.db"))
    project = ResearchCycle(db).run("knowledge state")["project"]
    db.execute(
        "INSERT INTO claims(id,project_id,statement,classification,evidence_level,confidence,status,created_at) VALUES (?,?,?,?,?,?,?,?)",
        ("candidate-claim", project["id"], "Candidate statement", "HYPOTHESIS", "PRELIMINARY", 0.2, "CANDIDATE", "2026-01-01T00:00:00Z"),
    )
    result = IntelligenceService(db).scientific_knowledge(project["id"])
    assert result["claims_by_status"]["CANDIDATE"] == 1
    assert "CANDIDATE:ACTIVE" not in result["knowledge_freshness_by_type_and_status"]
    assert result["interpretation"]["candidate_and_proposed_claims_are_not_active_knowledge"] is True
