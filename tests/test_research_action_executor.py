from app.database import Database
from app.workflow import ResearchCycle
from app.research_agent import ResearchAgentService
from app.research_action_executor import ResearchActionExecutor

def _workspace(db):
    p=ResearchCycle(db).run("Executor")["project"]
    wsid="ws-executor"
    db.execute("""INSERT INTO research_workspaces
        (id,project_id,question,scope,inclusion_rules,exclusion_rules,status,owner,created_at,updated_at)
        VALUES (?,?,?,?,?,?,?,?,datetime('now'),datetime('now'))""",
        (wsid,p["id"],"What evidence exists?","digital","[]","[]","ACTIVE","test"))
    return wsid

def test_information_gathering_creates_research_task(tmp_path):
    db=Database(str(tmp_path/"executor.db"))
    wsid=_workspace(db)
    result=ResearchActionExecutor(db).execute(wsid,"INFORMATION_GATHERING")
    assert result["status"]=="TASK_CREATED"
    assert result["action"]=="INFORMATION_GATHERING"
    assert result["task"]["assigned_agent_id"]

def test_sensitive_routes_remain_governed(tmp_path):
    db=Database(str(tmp_path/"governed.db"))
    wsid=_workspace(db)
    for action in ("FALSIFICATION_REVIEW","REPLICATION_REVIEW","EXPERIMENT_DESIGN"):
        result=ResearchActionExecutor(db).execute(wsid,action)
        assert result["status"]=="GOVERNED_REVIEW_REQUIRED"
        assert result["task"]["status"]=="PLANNED"
