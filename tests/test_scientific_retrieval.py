"""Integration tests for the scientific retrieval boundary.

These tests stub provider responses so CI does not depend on the live network.
They verify that retrieval records discoverable material without silently
promoting it to reviewed evidence.
"""
from app.autonomous_research_loop import AutonomousResearchLoop
from app.database import Database
from app.scientific_retrieval import ScientificRetrievalService
from app.workflow import ResearchCycle


def _active_workspace(tmp_path):
    db = Database(str(tmp_path / "scientific-retrieval.db"))
    project = ResearchCycle(db).run("self-discipline research")["project"]
    run = AutonomousResearchLoop(db).bootstrap_research(
        "What is self-discipline, what components comprise it, and how can it be developed?"
    )
    # The bootstrap loop creates its own project; use that project's workspace.
    loop = AutonomousResearchLoop(db)
    loop.start_research(run["run"]["id"])
    active_run = loop.get(run["run"]["id"])
    return db, active_run


def test_retrieval_persists_discovery_without_verifying_evidence(tmp_path, monkeypatch):
    db, run = _active_workspace(tmp_path)
    service = ScientificRetrievalService(db)
    record = {
        "record_id": "doi:10.1234/example",
        "title": "Self-regulation and goal pursuit",
        "url": "https://doi.org/10.1234/example",
        "authors": "Example, A.",
        "year": 2024,
        "source_type": "PAPER",
        "abstract": "An abstract describing self-regulation and goal pursuit.",
    }
    monkeypatch.setattr(service, "_pubmed", lambda query, limit: [record])
    monkeypatch.setattr(service, "_crossref", lambda query, limit: [dict(record)])

    result = service.retrieve(run["workspace_id"], providers=("pubmed", "crossref"), limit=10)

    assert result["retrieval_run"]["status"] == "COMPLETED"
    assert result["retrieval_run"]["result_count"] == 1
    assert result["scientific_status"] == "DISCOVERY_ONLY_UNVERIFIED"
    assert len(result["results"]) == 1
    source_id = result["results"][0]["source_id"]
    workspace_source = db.one(
        "SELECT * FROM research_workspace_sources WHERE workspace_id=? AND source_id=?",
        (run["workspace_id"], source_id),
    )
    assert workspace_source is not None
    assert workspace_source["reviewed"] == 0
    parsed = db.one(
        "SELECT state,content FROM evidence_sources WHERE source_id=? ORDER BY created_at DESC LIMIT 1",
        (source_id,),
    )
    assert parsed["state"] == "PARSED"
    assert parsed["content"] == record["abstract"]
    assert db.one("SELECT COUNT(*) AS n FROM evidence WHERE source_id=?", (source_id,))["n"] == 0


def test_retrieval_reports_provider_failures_without_inventing_results(tmp_path, monkeypatch):
    db, run = _active_workspace(tmp_path)
    service = ScientificRetrievalService(db)

    def fail(query, limit):
        raise TimeoutError("simulated provider timeout")

    monkeypatch.setattr(service, "_pubmed", fail)
    monkeypatch.setattr(service, "_crossref", fail)
    result = service.retrieve(run["workspace_id"], providers=("pubmed", "crossref"), limit=5)

    assert result["retrieval_run"]["status"] == "FAILED"
    assert result["retrieval_run"]["result_count"] == 0
    assert result["results"] == []
    assert len(result["errors"]) == 2
    assert result["scientific_status"] == "DISCOVERY_ONLY_UNVERIFIED"
