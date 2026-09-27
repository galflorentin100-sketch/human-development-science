from app.database import Database
from app.intelligence import IntelligenceService

def test_intelligence_findings_reads_research_findings(tmp_path):
    db=Database(str(tmp_path/"intelligence.db"))
    row=db.one("SELECT name FROM sqlite_master WHERE type='table' AND name='research_findings'")
    assert row
    assert IntelligenceService(db).findings()==[]
