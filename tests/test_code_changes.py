from app.database import Database
from app.workflow import ResearchCycle
from app.code_changes import CodeChangeService


def test_code_change_requires_separation_of_duties_and_verification(tmp_path):
    db=Database(str(tmp_path/"code.db"))
    project=ResearchCycle(db).run("governed code changes")["project"]
    db.execute("""INSERT INTO maintenance_work
        (id,kind,entity_type,entity_id,title,reason,success_criteria,status,approval_id,created_at,updated_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        ("mw","ENGINEERING","project",project["id"],"Fix","reason","tests","PROPOSED",None,"now","now"))
    svc=CodeChangeService(db)
    p=svc.propose(project["id"],"mw","safe patch","UNIFIED_DIFF","diff --git","pytest tests/test_x.py","LOW","alice")
    try: svc.approve(p["id"],"alice"); assert False
    except ValueError as exc: assert "separation" in str(exc)
    approved=svc.approve(p["id"],"bob")
    assert approved["status"]=="APPROVED"
    try:
        svc.mark_verified(p["id"],"ci-123","rollback")
        assert False
    except ValueError as exc:
        assert "recorded successful runner result" in str(exc)
    fingerprint=svc.fingerprint(svc.get(p["id"]))
    db.execute(
        """INSERT INTO code_change_execution_runs
           (id,proposal_id,run_type,project_id,proposal_fingerprint,status,actor,runner_mode,created_at)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        ("ci-123",p["id"],"VERIFICATION",project["id"],fingerprint,"PASSED","runner","isolated","now"),
    )
    svc.record_verification(p["id"],"ci-123",True,0,False,"tests passed")
    verified=svc.mark_verified(p["id"],"ci-123","rollback")
    assert verified["status"]=="VERIFIED"
    try:
        svc.rollback(p["id"],"rollback-1","bob")
        assert False
    except ValueError as exc:
        assert "deployed" in str(exc)
    db.execute(
        """INSERT INTO code_change_execution_runs
           (id,proposal_id,run_type,project_id,proposal_fingerprint,status,actor,runner_mode,created_at)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        ("deploy-1",p["id"],"DEPLOYMENT",project["id"],fingerprint,"PASSED","deployer","isolated","now"),
    )
    assert svc.record_deployed(p["id"],"deploy-1","deployer")["status"]=="DEPLOYED"
    db.execute(
        """INSERT INTO code_change_execution_runs
           (id,proposal_id,run_type,project_id,proposal_fingerprint,status,actor,runner_mode,created_at)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        ("rollback-1",p["id"],"ROLLBACK",project["id"],fingerprint,"PASSED","deployer","isolated","now"),
    )
    assert svc.rollback(p["id"],"rollback-1","deployer")["status"]=="ROLLED_BACK"


def test_code_change_runner_only_executes_approved_allowlisted_patch(tmp_path):
    from app.code_change_runner import CodeChangeRunner
    import json
    workspace=tmp_path/"workspace"
    workspace.mkdir()
    (workspace/"test_generated.py").write_text("def test_ok():\n    assert 2 + 2 == 4\n")
    db=Database(str(tmp_path/"runner.db"))
    project=ResearchCycle(db).run("runner")["project"]
    db.execute("""INSERT INTO maintenance_work
        (id,kind,entity_type,entity_id,title,reason,success_criteria,status,approval_id,created_at,updated_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        ("mw-run","ENGINEERING","project",project["id"],"Fix","reason","tests","PROPOSED",None,"now","now"))
    svc=CodeChangeService(db)
    payload=json.dumps({"test_generated.py":"def test_ok():\n    assert 3 * 3 == 9\n"})
    p=svc.propose(project["id"],"mw-run","runner patch","FILE_REPLACEMENT",payload,"python test_generated.py","LOW","alice")
    svc.approve(p["id"],"bob")
    result=CodeChangeRunner(db).verify_and_record(p["id"],str(workspace),30)
    assert result["passed"] is True
    assert db.one("SELECT status FROM code_change_proposals WHERE id=?",(p["id"],))["status"]=="VERIFIED"


def test_code_change_runner_rejects_unapproved_and_dynamic_commands(tmp_path):
    from app.code_change_runner import CodeChangeRunner
    db=Database(str(tmp_path/"runner-reject.db"))
    project=ResearchCycle(db).run("runner reject")["project"]
    db.execute("""INSERT INTO maintenance_work
        (id,kind,entity_type,entity_id,title,reason,success_criteria,status,approval_id,created_at,updated_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        ("mw-reject","ENGINEERING","project",project["id"],"Fix","reason","tests","PROPOSED",None,"now","now"))
    svc=CodeChangeService(db)
    p=svc.propose(project["id"],"mw-reject","runner patch","FILE_REPLACEMENT",'{"x.py":"x=1"}',"pytest -c evil","LOW","alice")
    runner=CodeChangeRunner(db)
    try: runner.verify(p["id"],str(tmp_path),30); assert False
    except ValueError as exc: assert "approved" in str(exc)
    svc.approve(p["id"],"bob")
    try: runner.verify(p["id"],str(tmp_path),30); assert False
    except ValueError as exc: assert "dynamic code execution" in str(exc)

def test_code_change_runner_rejects_workspace_escape_paths(tmp_path):
    from app.code_change_runner import CodeChangeRunner
    import json
    db=Database(str(tmp_path/"runner-path.db"))
    project=ResearchCycle(db).run("runner path")["project"]
    db.execute("""INSERT INTO maintenance_work
        (id,kind,entity_type,entity_id,title,reason,success_criteria,status,approval_id,created_at,updated_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        ("mw-path","ENGINEERING","project",project["id"],"Fix","reason","tests","PROPOSED",None,"now","now"))
    svc=CodeChangeService(db)
    p=svc.propose(project["id"],"mw-path","runner patch","FILE_REPLACEMENT",'{"x.py":"x=1"}',"python ../escape.py","LOW","alice")
    svc.approve(p["id"],"bob")
    try:
        CodeChangeRunner(db).verify(p["id"],str(tmp_path),30)
        assert False
    except ValueError as exc:
        assert "outside the workspace" in str(exc)

def test_code_change_runner_rejects_symlink_patch_target(tmp_path):
    from app.code_change_runner import CodeChangeRunner
    import json
    workspace=tmp_path/"workspace"; workspace.mkdir()
    outside=tmp_path/"outside.py"; outside.write_text("safe")
    (workspace/"link.py").symlink_to(outside)
    db=Database(str(tmp_path/"runner-link.db"))
    project=ResearchCycle(db).run("runner link")["project"]
    db.execute("""INSERT INTO maintenance_work
        (id,kind,entity_type,entity_id,title,reason,success_criteria,status,approval_id,created_at,updated_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        ("mw-link","ENGINEERING","project",project["id"],"Fix","reason","tests","PROPOSED",None,"now","now"))
    svc=CodeChangeService(db)
    p=svc.propose(project["id"],"mw-link","runner patch","FILE_REPLACEMENT",
                  json.dumps({"link.py":"tampered"}),"python link.py","LOW","alice")
    svc.approve(p["id"],"bob")
    try:
        CodeChangeRunner(db).verify(p["id"],str(workspace),30)
        assert False
    except ValueError as exc:
        assert "symlink" in str(exc)

def test_code_change_cannot_cross_project_maintenance_work(tmp_path):
    db=Database(str(tmp_path/"cross-project.db"))
    first=ResearchCycle(db).run("first project")["project"]
    second=ResearchCycle(db).run("second project")["project"]
    db.execute("""INSERT INTO maintenance_work
        (id,kind,entity_type,entity_id,title,reason,success_criteria,status,approval_id,created_at,updated_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        ("mw-cross","ENGINEERING","project",first["id"],"Fix","reason","tests","PROPOSED",None,"now","now"))
    svc=CodeChangeService(db)
    try:
        svc.propose(second["id"],"mw-cross","cross project","FILE_REPLACEMENT",'{"x.py":"x=1"}',"pytest test_x.py","LOW","alice")
        assert False
    except ValueError as exc:
        assert "another project" in str(exc)


def test_code_change_runner_isolated_mode_uses_worker_job_transport(tmp_path, monkeypatch):
    import json, threading, time
    from app.code_change_runner import CodeChangeRunner
    workspace=tmp_path/"workspace"; workspace.mkdir()
    (workspace/"test_generated.py").write_text("assert 5 * 5 == 25\n")
    shared=tmp_path/"worker"; monkeypatch.setenv("HDS_CODE_RUNNER_MODE","isolated")
    monkeypatch.setenv("HDS_WORKER_SHARED_DIR",str(shared))
    monkeypatch.setenv("HDS_WORKER_RESULT_DIR",str(tmp_path/"results"))
    from worker import runner as worker_module
    monkeypatch.setattr(worker_module.os, "geteuid", lambda: 10001)
    worker_main=worker_module.main
    thread=threading.Thread(target=worker_main,daemon=True); thread.start()
    db=Database(str(tmp_path/"isolated.db"))
    project=ResearchCycle(db).run("isolated runner")["project"]
    db.execute("""INSERT INTO maintenance_work
        (id,kind,entity_type,entity_id,title,reason,success_criteria,status,approval_id,created_at,updated_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        ("mw-isolated","ENGINEERING","project",project["id"],"Fix","reason","tests","PROPOSED",None,"now","now"))
    svc=CodeChangeService(db)
    payload=json.dumps({"test_generated.py":"assert 7 * 7 == 49\n"})
    p=svc.propose(project["id"],"mw-isolated","isolated patch","FILE_REPLACEMENT",payload,"python test_generated.py","LOW","alice")
    svc.approve(p["id"],"bob")
    result=CodeChangeRunner(db).verify_and_record(p["id"],str(workspace),20)
    assert result["passed"] is True
    assert db.one("SELECT status FROM code_change_proposals WHERE id=?",(p["id"],))["status"]=="VERIFIED"
