"""Governed verification runner for approved code changes."""
from __future__ import annotations
import json, os, shlex, shutil, subprocess, tempfile, time
from pathlib import Path
from uuid import uuid4

ALLOWED_TEST_PROGRAMS={"pytest","python","python3"}
MAX_TIMEOUT_SECONDS=900
MAX_OUTPUT_BYTES=200_000

class CodeChangeRunner:
    def __init__(self,db):
        self.db=db
        from app.config import Settings
        self.settings=Settings.load()
        if self.settings.environment=="production" and self.settings.code_runner_mode!="isolated":
            raise RuntimeError("production code runner requires an isolated execution worker")

    def _proposal(self,proposal_id):
        row=self.db.one("SELECT * FROM code_change_proposals WHERE id=?",(proposal_id,))
        if not row: raise ValueError("code change proposal not found")
        if row["status"]!="APPROVED": raise ValueError("only approved code changes may enter the runner")
        return row

    def _command(self,command):
        parts=shlex.split(command)
        if not parts or parts[0] not in ALLOWED_TEST_PROGRAMS: raise ValueError("verification command is not allowlisted")
        if any(x in {"-c","--command","-m","--module"} for x in parts): raise ValueError("dynamic code execution is not allowed")
        # The worker may execute only files addressed inside the disposable workspace.
        for arg in parts[1:]:
            if arg.startswith("-"): continue
            if Path(arg).is_absolute() or ".." in Path(arg).parts:
                raise ValueError("verification command cannot address paths outside the workspace")
        return parts

    def _apply_patch(self,proposal,target):
        if proposal["patch_format"]=="FILE_REPLACEMENT":
            import json
            files=json.loads(proposal["patch_payload"])
            if not isinstance(files,dict) or not files: raise ValueError("file replacement payload must be a non-empty object")
            root=target.resolve()
            for rel,payload in files.items():
                path=(root/rel).resolve()
                if root not in path.parents: raise ValueError("patch escapes workspace")
                if (root / rel).is_symlink(): raise ValueError("patch cannot overwrite a symlink")
                if not isinstance(payload,str): raise ValueError("replacement content must be text")
                path.parent.mkdir(parents=True,exist_ok=True); path.write_text(payload,encoding="utf-8")
            return
        if proposal["patch_format"]=="UNIFIED_DIFF":
            result=subprocess.run(["git","apply","--whitespace=error-all","-"],input=proposal["patch_payload"],
                text=True,cwd=target,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=60,check=False,
                env={"PATH":os.environ.get("PATH","")})
            if result.returncode: raise ValueError("unified diff could not be applied: "+result.stdout[-4000:])
            return
        raise ValueError("unsupported patch format")

    def _verify_isolated(self, proposal, proposal_id, workspace, command, timeout, run_id):
        shared = Path(os.getenv('HDS_WORKER_SHARED_DIR', '/var/lib/hds-code-worker')).resolve()
        results_dir = Path(os.getenv('HDS_WORKER_RESULT_DIR', '/var/lib/hds-code-worker-results')).resolve()
        jobs = shared / 'jobs'; jobs.mkdir(parents=True, exist_ok=True)
        results_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='hds-verify-') as temp:
            target = Path(temp) / 'workspace'
            shutil.copytree(Path(workspace).resolve(), target, ignore=shutil.ignore_patterns('.git','__pycache__','.pytest_cache'))
            self._apply_patch(proposal, target)
            job_dir = jobs / run_id; job_dir.mkdir()
            shutil.copytree(target, job_dir / 'workspace', ignore=shutil.ignore_patterns('.git','__pycache__','.pytest_cache'))
            (job_dir / 'request.json').write_text(json.dumps({'command': command, 'timeout': timeout}), encoding='utf-8')
            deadline=time.monotonic()+timeout+30; result_file=results_dir/(run_id+'.json')
            try:
                while time.monotonic() < deadline:
                    if result_file.exists():
                        try:
                            result=json.loads(result_file.read_text(encoding='utf-8'))
                        except (OSError, ValueError):
                            time.sleep(0.25); continue
                        return {'verification_run_id':run_id,'proposal_id':proposal_id,'passed':bool(result.get('passed')),'return_code':result.get('return_code'),'timed_out':bool(result.get('timed_out')),'output':str(result.get('output',''))[-MAX_OUTPUT_BYTES:]}
                    time.sleep(0.25)
                return {'verification_run_id':run_id,'proposal_id':proposal_id,'passed':False,'return_code':None,'timed_out':True,'output':'isolated worker did not return a result before timeout'}
            finally: shutil.rmtree(job_dir, ignore_errors=True)
    def verify(self,proposal_id,workspace,timeout_seconds=300):
        proposal=self._proposal(proposal_id)
        root=Path(workspace).resolve()
        if not root.is_dir(): raise ValueError("workspace does not exist")
        timeout=min(max(int(timeout_seconds),1),MAX_TIMEOUT_SECONDS)
        command=self._command(proposal["test_command"]); run_id=str(uuid4())
        if self.settings.code_runner_mode=="isolated":
            return self._verify_isolated(proposal,proposal_id,root,command,timeout,run_id)
        with tempfile.TemporaryDirectory(prefix="hds-verify-") as temp:
            target=Path(temp)/"workspace"
            shutil.copytree(root,target,ignore=shutil.ignore_patterns(".git","__pycache__",".pytest_cache"))
            self._apply_patch(proposal,target)
            env={"PATH":os.environ.get("PATH",""),"PYTHONDONTWRITEBYTECODE":"1","PYTHONNOUSERSITE":"1"}
            try:
                result=subprocess.run(command,cwd=target,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
                    text=True,timeout=timeout,check=False,env=env)
                return {"verification_run_id":run_id,"proposal_id":proposal_id,"passed":result.returncode==0,
                        "return_code":result.returncode,"timed_out":False,"output":result.stdout[-MAX_OUTPUT_BYTES:]}
            except subprocess.TimeoutExpired as exc:
                output=exc.stdout or ""
                if isinstance(output,bytes): output=output.decode("utf-8",errors="replace")
                return {"verification_run_id":run_id,"proposal_id":proposal_id,"passed":False,
                        "return_code":None,"timed_out":True,"output":output[-MAX_OUTPUT_BYTES:]}

    def verify_and_record(self,proposal_id,workspace,timeout_seconds=300):
        result=self.verify(proposal_id,workspace,timeout_seconds)
        if not result["passed"]: return result
        from app.code_changes import CodeChangeService
        CodeChangeService(self.db).mark_verified(proposal_id,result["verification_run_id"],
            rollback_payload="verified runner result; deployment layer owns production rollback")
        return result
