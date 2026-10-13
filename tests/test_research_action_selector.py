from app.research_action_selector import ResearchActionSelector

def test_action_selector_routes_research_to_information_gathering():
    route=ResearchActionSelector().select({"kind":"RESEARCH","title":"Collect evidence","reason":"open research question"})
    assert route["action"]=="INFORMATION_GATHERING"
    assert route["execution_authorized"] is True

def test_action_selector_routes_falsification_to_governed_review():
    route=ResearchActionSelector().select({"kind":"RESEARCH","title":"Follow up on falsification challenge","reason":"FALSIFICATION_REVIEW"})
    assert route["action"]=="FALSIFICATION_REVIEW"
    assert route["execution_authorized"] is False

def test_action_selector_routes_replication_to_governed_review():
    route=ResearchActionSelector().select({"kind":"RESEARCH","title":"Clarify the replication outcome","reason":"REPLICATION_REVIEW"})
    assert route["action"]=="REPLICATION_REVIEW"
    assert route["execution_authorized"] is False
