from app.dashboard import render_dashboard


def test_dashboard_exposes_mental_research_workflow():
    html = render_dashboard()
    assert "HDS Mentality Research Lab" in html
    assert "/api/hds/research-loops/bootstrap" in html
    assert "/run-first-pass" in html
    assert "Unverified research output" in html
    assert "candidate_claims" in html


def test_dashboard_refreshes_all_project_panels_together():
    html = render_dashboard()
    assert 'onclick="refreshAll()"' in html
    assert 'async function refreshAll()' in html
    assert 'addEventListener("change",refreshAll)' in html
    refresh_all = html.split("async function refreshAll()", 1)[1].split("async function refreshProjectFeed()", 1)[0]
    assert "refresh()" in refresh_all
    assert "loadBackgroundFeed()" in refresh_all
    assert "loadEvidenceMap()" in refresh_all
