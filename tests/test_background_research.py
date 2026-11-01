from app.background_research import BackgroundResearchScheduler, QUESTIONS
from app.dashboard import render_dashboard


def test_background_scheduler_has_bounded_mental_research_rotation():
    scheduler = BackgroundResearchScheduler(interval_seconds=60)
    assert scheduler.interval_seconds == 900
    assert len(QUESTIONS) >= 5
    assert any("self-discipline" in question for question in QUESTIONS)
    assert any("emotion regulation" in question for question in QUESTIONS)


def test_dashboard_exposes_saved_autonomous_research_feed():
    html = render_dashboard()
    assert "Autonomous research feed" in html
    assert "loadBackgroundFeed" in html
    assert "refreshProjectFeed" in html


def test_background_scheduler_persists_question_rotation(tmp_path):
    state = tmp_path / "scheduler-state.json"
    first = BackgroundResearchScheduler(state_path=state)
    first._save_cursor(3)

    restarted = BackgroundResearchScheduler(state_path=state)
    assert restarted._load_cursor() == 3


def test_background_scheduler_recovers_from_missing_or_invalid_state(tmp_path):
    state = tmp_path / "scheduler-state.json"
    scheduler = BackgroundResearchScheduler(state_path=state)
    assert scheduler._load_cursor() == 0

    state.write_text("not-json", encoding="utf-8")
    assert scheduler._load_cursor() == 0
