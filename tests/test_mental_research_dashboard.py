from app.dashboard import render_dashboard


def test_dashboard_exposes_mental_research_workflow():
    html = render_dashboard()
    assert "HDS Mentality Research Lab" in html
    assert "/api/hds/research-loops/bootstrap" in html
    assert "/run-first-pass" in html
    assert "Unverified research output" in html
    assert "candidate_claims" in html
