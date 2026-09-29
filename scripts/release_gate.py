"""Deterministic release gate for HDS application invariants."""
from pathlib import Path
from tempfile import TemporaryDirectory
from collections import Counter
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.database import Database

REQUIRED_TABLES={
"projects","claims","evidence","project_memberships","approvals","maintenance_work","code_change_proposals",
"hds_programs","hds_challenges","hds_competitions","hds_competition_scores","hds_safety_controls",
"hds_constructs","hds_assessment_measures","hds_assessment_sessions","hds_assessment_observations",
"hds_experiments","hds_experiment_results","research_workspaces","research_syntheses","study_outcomes","research_loop_runs","hds_challenge_executions","hds_training_adjustments"
}
REQUIRED_ROUTES={"/ready","/api/intelligence","/api/hds/programs","/api/hds/competitions","/api/hds/assessments/constructs","/api/hds/assessments/measures","/api/hds/research-loops","/api/hds/company/{project_id}/analytics","/api/hds/training/{protocol_id}/participants/{participant_ref}/adaptive"}

def main():
    with TemporaryDirectory() as d:
        db=Database(str(Path(d)/"release.db")); db.migrate()
        tables={r["name"] for r in db.all("SELECT name FROM sqlite_master WHERE type='table'")}
        missing=REQUIRED_TABLES-tables
        if missing: raise SystemExit("missing required tables: "+", ".join(sorted(missing)))
    from app.main import app
    route_paths=[r.path for r in app.routes if getattr(r,"path",None)]
    routes=set(route_paths)
    missing_routes=REQUIRED_ROUTES-routes
    if missing_routes: raise SystemExit("missing required routes: "+", ".join(sorted(missing_routes)))
    duplicates=sorted(path for path,count in Counter(route_paths).items() if count > 1)
    if duplicates: raise SystemExit("duplicate application routes: "+", ".join(duplicates))
    print("HDS release gate: PASS")

if __name__=="__main__": main()
