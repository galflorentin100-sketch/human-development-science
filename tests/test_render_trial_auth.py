from fastapi.testclient import TestClient

import app.main as main


def test_trial_api_rejects_requests_without_bearer_token(monkeypatch):
    monkeypatch.setenv("HDS_TRIAL_TOKEN", "test-secret-token")
    response = TestClient(main.app).get("/api/agents/registry")
    assert response.status_code == 401
    assert response.json()["detail"] == "trial token required"


def test_trial_api_accepts_valid_bearer_token(monkeypatch):
    monkeypatch.setenv("HDS_TRIAL_TOKEN", "test-secret-token")
    response = TestClient(main.app).get(
        "/api/agents/registry",
        headers={"Authorization": "Bearer test-secret-token"},
    )
    assert response.status_code == 200


def test_trial_gate_is_inactive_when_token_is_not_configured(monkeypatch):
    monkeypatch.delenv("HDS_TRIAL_TOKEN", raising=False)
    response = TestClient(main.app).get("/api/agents/registry")
    assert response.status_code == 200
