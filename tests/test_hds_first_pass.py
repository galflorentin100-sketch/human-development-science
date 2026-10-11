import json

from fastapi.testclient import TestClient

from app.autonomous_research_loop import AutonomousResearchLoop
from app.database import Database
from app.providers import ModelResponse
from app.scientific_retrieval import ScientificRetrievalService
from app.workflow import ResearchCycle
import app.main as main


class FakeResearchProvider:
    name = "test-provider"

    def estimate_cost(self, request):
        return 0.0

    def complete(self, request):
        return ModelResponse(
            content=json.dumps({
                "candidate_claims": [],
                "result": "The supplied abstracts are insufficient for a supported conclusion.",
                "limitations": "This test uses one synthetic abstract.",
                "uncertainty": "No scientific conclusion is established by this run.",
            }),
            provider=self.name,
            model="fake-research-model",
        )


def _run(tmp_path, monkeypatch, abstract):
    db = Database(str(tmp_path / "hds-first-pass.db"))
    ResearchCycle(db)
    # Seed project/agent state exactly as the normal application workflow does.
    ResearchCycle(db).run("HDS first-pass test setup")
    created = AutonomousResearchLoop(db).bootstrap_research(
        "Which interventions improve self-discipline over time, for whom, and under what conditions?"
    )
    run = created["run"]

    record = {
        "record_id": "pubmed:123456",
        "title": "Self-regulation intervention study",
        "url": "https://pubmed.ncbi.nlm.nih.gov/123456/",
        "authors": "Example et al.",
        "year": 2024,
        "source_type": "PAPER",
        "abstract": abstract,
    }
    monkeypatch.setattr(ScientificRetrievalService, "_pubmed", lambda self, query, limit: [record])
    monkeypatch.setattr(ScientificRetrievalService, "_crossref", lambda self, query, limit: [])
    monkeypatch.setattr(main, "db", db)
    return db, run


def test_first_pass_executes_configured_research_agent_and_keeps_output_unverified(tmp_path, monkeypatch):
    db, run = _run(
        tmp_path, monkeypatch,
        "A small randomized study compared a self-monitoring intervention with a control group. "
        "The abstract reports short-term questionnaire outcomes and notes limited follow-up."
    )
    import app.execution as execution
    monkeypatch.setattr(execution, "configured_provider", lambda: FakeResearchProvider())

    response = TestClient(main.app).post(
        f"/api/hds/research-loops/{run['id']}/run-first-pass",
        json={"query": "self-discipline interventions", "providers": ["pubmed"], "limit": 5},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "RESEARCH_PASS_RECORDED"
    assert body["scientific_status"] == "UNVERIFIED_REVIEW_REQUIRED"
    assert body["output_review"]["status"] == "NEEDS_EVIDENCE"
    assert body["agent_run_id"]
    assert db.one("SELECT status FROM agent_runs WHERE id=?", (body["agent_run_id"],))["status"] == "REVIEW"
    assert db.one("SELECT verified FROM agent_runs WHERE id=?", (body["agent_run_id"],))["verified"] == 0


def test_first_pass_blocks_when_retrieved_sources_have_no_readable_abstract(tmp_path, monkeypatch):
    _db, run = _run(tmp_path, monkeypatch, "")
    response = TestClient(main.app).post(
        f"/api/hds/research-loops/{run['id']}/run-first-pass",
        json={"query": "self-discipline interventions", "providers": ["pubmed"], "limit": 5},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "RESEARCH_AGENT_BLOCKED"
    assert body["scientific_status"] == "DISCOVERY_ONLY_UNVERIFIED"
    assert "readable abstract" in body["reason"]


def test_first_pass_reports_missing_real_model_provider_without_fake_research(tmp_path, monkeypatch):
    _db, run = _run(
        tmp_path, monkeypatch,
        "The study abstract describes a self-regulation intervention and short-term outcomes."
    )
    import app.execution as execution

    class MissingProvider:
        name = "local"

        def estimate_cost(self, request):
            return 0.0

        def complete(self, request):
            raise RuntimeError("No research-capable model is configured.")

    monkeypatch.setattr(execution, "configured_provider", lambda: MissingProvider())
    response = TestClient(main.app).post(
        f"/api/hds/research-loops/{run['id']}/run-first-pass",
        json={"query": "self-discipline interventions", "providers": ["pubmed"], "limit": 5},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "MODEL_EXECUTION_FAILED"
    assert body["scientific_status"] == "NO_SYNTHESIS"
    assert "No research-capable model" in body["error"]
    db_count = _db.one("SELECT COUNT(*) AS n FROM research_syntheses")["n"]
    assert db_count == 0
