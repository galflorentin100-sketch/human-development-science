from fastapi.testclient import TestClient
from app.main import app

client=TestClient(app)

def test_health():
    r=client.get("/health")
    assert r.status_code==200
    assert r.json()["status"]=="ok"

def test_company_state():
    r=client.get("/api/company-state")
    assert r.status_code==200
    assert r.json()["id"]=="hds"

def test_full_state_contains_workforce():
    r=client.get("/api/company-state/full")
    assert r.status_code==200
    body=r.json()
    assert len(body["agents"])>=10
    assert "risks" in body and "approvals" in body

def test_intelligence():
    r=client.get("/api/intelligence")
    assert r.status_code==200
    body=r.json()
    assert "health" in body
    assert "brief" in body
