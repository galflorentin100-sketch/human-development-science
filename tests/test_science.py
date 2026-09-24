from app.database import Database
from app.workflow import ResearchCycle
from app.science import ScientificRegistry

def test_scientific_registry_tracks_construct_measure_and_version(tmp_path):
    db=Database(str(tmp_path/"science.db")); ResearchCycle(db)
    registry=ScientificRegistry(db)
    c=registry.construct("Goal-directed self-regulation","Ability to direct and maintain behavior toward a chosen goal despite obstacles.")
    assert c["version"]==1
    registry.measure(c["id"],"Goal execution rate","Completed planned actions / planned actions","Structured daily log","percent","To be established","To be established")
    updated=registry.version_construct(c["id"],"Ability to direct and maintain behavior toward a chosen goal despite obstacles while adapting strategy when conditions change.","Behavioral task plus real-world transfer","Expanded construct definition")
    assert updated["version"]==2
    assert db.one("SELECT COUNT(*) AS n FROM construct_versions WHERE construct_id=?",(c["id"],))["n"]==2

def test_intervention_cannot_claim_unknown_evidence_level(tmp_path):
    db=Database(str(tmp_path/"science2.db")); ResearchCycle(db)
    registry=ScientificRegistry(db)
    try:
        registry.intervention("x","rationale","mechanism","PROVEN","daily","adults")
        assert False
    except ValueError as exc:
        assert "evidence level" in str(exc)

def test_intervention_evidence_is_structured(tmp_path):
    db=Database(str(tmp_path/"science3.db")); ResearchCycle(db)
    registry=ScientificRegistry(db)
    i=registry.intervention("x","rationale","mechanism","PLAUSIBLE","daily","adults")
    ev=registry.intervention_evidence(i["id"],"PILOT","study-001","pilot evidence")
    assert ev["evidence_kind"]=="PILOT"
