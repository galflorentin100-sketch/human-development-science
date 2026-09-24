from app.scientific_ai import ScientificAIGuard

def test_fact_requires_evidence():
    guard=ScientificAIGuard()
    try:
        guard.classify("Humans can improve self-regulation.",requested="FACT")
        assert False
    except ValueError as exc:
        assert "evidence" in str(exc)

def test_hypothesis_can_be_unverified():
    statement=ScientificAIGuard().classify("This intervention may improve transfer.",requested="HYPOTHESIS")
    assert statement.classification=="HYPOTHESIS"

def test_constraints_forbid_invention():
    constraints=ScientificAIGuard().prompt_constraints()
    assert any("Never invent" in x for x in constraints)

def test_evidence_level_is_conservative():
    guard=ScientificAIGuard()
    assert guard.evidence_level(0,0,0)=="UNTESTED"
    assert guard.evidence_level(1,1,0)=="SUPPORTED"
    assert guard.evidence_level(1,1,1)=="WELL_SUPPORTED"
