from app.database import Database
from app.intelligence import IntelligenceService
from app.workflow import ResearchCycle


def test_company_intelligence_snapshot_is_structured_and_read_only(tmp_path):
    db = Database(str(tmp_path / "intelligence.db"))
    project = ResearchCycle(db).run("intelligence project")["project"]

    result = IntelligenceService(db).health()
    assert result["agents"] >= 1
    assert result["audit_events"] >= 1
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
        "INSERT INTO risks(id,company_id,title,status,created_at) VALUES (?,?,?,?,?)",
        ("risk-1", "hds", "test risk", "OPEN", "2026-01-01T00:00:00Z"),
    )
    after = IntelligenceService(db).health()

    assert after["open_risks"] == before["open_risks"] + 1
