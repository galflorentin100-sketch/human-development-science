from app.database import Database
from app.workflow import ResearchCycle
from app.human_development import HumanDevelopmentService


def test_hds_domains_include_core_human_development_areas(tmp_path):
    db = Database(str(tmp_path / "hds-domains.db"))
    domains = HumanDevelopmentService(db).domains()
    ids = {item["id"] for item in domains}
    assert {"MENTAL_TOUGHNESS", "DISCIPLINE", "PHYSICAL_PERFORMANCE", "COMBAT_SPORTS", "CHARACTER", "TEAMWORK"} <= ids


def test_hds_competition_is_project_scoped_and_measurable(tmp_path):
    db = Database(str(tmp_path / "hds-competition.db"))
    project = ResearchCycle(db).run("HDS competition")["project"]
    svc = HumanDevelopmentService(db)

    program = svc.create_program(
        project["id"], "Human Performance Pilot",
        "Test a measurable multi-domain challenge format",
        "PHYSICAL_PERFORMANCE", "founder",
    )
    challenge = svc.create_challenge(
        program["id"], "Controlled endurance challenge",
        "A supervised performance task with predefined scoring",
        "ENDURANCE", 5, "Qualified supervision; stop criteria; participant consent", "founder",
    )
    competition = svc.create_competition(project["id"], "HDS Challenge Day", "multi_event", "founder")
    event = svc.add_event(competition["id"], challenge["id"], 1, "time_seconds")
    participant = svc.register_participant(competition["id"], "participant-1")

    try:
        svc.record_score(event["id"], participant["id"], "time_seconds", 120)
        assert False, "score must require participant consent"
    except ValueError as exc:
        assert "consent" in str(exc).lower()

    consented = svc.record_consent(participant["id"])
    assert consented["consent_status"] == "CONSENTED"
    score = svc.record_score(event["id"], participant["id"], "time_seconds", 120)
    assert score["score"] == 120.0

    snapshot = svc.competition_snapshot(competition["id"])
    assert len(snapshot["events"]) == 1
    assert len(snapshot["participants"]) == 1
    assert len(snapshot["scores"]) == 1


def test_hds_cannot_mix_challenge_from_another_project(tmp_path):
    db = Database(str(tmp_path / "hds-isolation.db"))
    first = ResearchCycle(db).run("HDS project one")["project"]
    second = ResearchCycle(db).run("HDS project two")["project"]
    svc = HumanDevelopmentService(db)

    program = svc.create_program(first["id"], "Program One", "Objective", "CHARACTER", "founder")
    challenge = svc.create_challenge(
        program["id"], "Challenge One", "Description", "CHARACTER", 3,
        "Supervision and stop criteria", "founder",
    )
    competition = svc.create_competition(second["id"], "Competition Two", "multi_event", "founder")

    try:
        svc.add_event(competition["id"], challenge["id"], 1, "score")
        assert False, "cross-project challenge must be rejected"
    except ValueError as exc:
        assert "another project" in str(exc)


def test_hds_api_routes_are_wired():
    from app.main import app
    paths = {route.path for route in app.routes}
    assert "/api/hds/domains" in paths
    assert "/api/hds/programs" in paths
    assert "/api/hds/competitions" in paths
    assert "/api/hds/competitions/{competition_id}" in paths
