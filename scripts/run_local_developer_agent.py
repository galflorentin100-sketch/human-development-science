"""Guarded local HDS coding agent using Ollama; no model-supplied shell commands."""
from __future__ import annotations
import argparse,json,logging,os,re,subprocess,sys,time,urllib.error,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
BASE="hds-local-developer-agent"; WORK="hds-agent-work"; MODEL="qwen2.5:7b"
PREFIXES=("app/","tests/","scripts/","docs/"); MAX_DIFF=30000; MAX_FILES=8
LOG=logging.getLogger("hds.developer_agent")
def state_dir():
    p=Path(os.getenv("LOCALAPPDATA",str(Path.home())))/"HDS"; p.mkdir(parents=True,exist_ok=True); return p
def run(cmd,timeout=900):
    return subprocess.run(cmd,cwd=ROOT,text=True,capture_output=True,timeout=timeout,check=False)
def git(*args):
    r=run(["git",*args],120)
    if r.returncode: raise RuntimeError((r.stderr or r.stdout).strip() or "git failed")
    return r.stdout.strip()
def prepare():
    if not (ROOT/".git").exists(): raise RuntimeError("Run inside a Git clone.")
    current=git("branch","--show-current")
    if git("status","--porcelain"): raise RuntimeError("Working tree must be clean; agent will not overwrite changes.")
    if current==WORK: return
    if current!=BASE: raise RuntimeError(f"Start on {BASE} or {WORK}; current branch is {current}.")
    if git("branch","--list",WORK): git("switch",WORK)
    else: git("switch","-c",WORK)
def ask(model,url):
    backlog=(ROOT/"docs"/"DEVELOPER_AGENT_BACKLOG.md").read_text(encoding="utf-8")
    prompt=f"""Choose ONE small unfinished task from this backlog:
{backlog}
Return ONLY JSON with task_id, summary, diff. diff is a unified diff with --- a/path and +++ b/path.
At most {MAX_FILES} existing files and {MAX_DIFF} characters. Only app/, tests/, scripts/, docs/.
No deletes, renames, new dependencies, secrets, workflows, production data, main, or shell commands.
If no safe patch, return empty diff and explain in summary. Do not claim tests passed."""
    body=json.dumps({"model":model,"prompt":prompt,"stream":False,"format":"json"}).encode()
    req=urllib.request.Request(url.rstrip("/")+"/api/generate",data=body,headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(req,timeout=900) as response: envelope=json.loads(response.read().decode())
    result=json.loads(envelope.get("response",""))
    if not isinstance(result,dict): raise ValueError("Model response must be a JSON object")
    return result
def validate(diff):
    if not isinstance(diff,str) or not diff.strip(): return []
    if len(diff)>MAX_DIFF or "\x00" in diff or "GIT binary patch" in diff: raise ValueError("Patch too large or binary")
    paths=[]
    for line in diff.splitlines():
        if not line.startswith("+++ "): continue
        raw=line[4:].split("\t",1)[0]
        if raw=="/dev/null" or not raw.startswith("b/"): raise ValueError("New files/deletions disabled")
        path=raw[2:].replace("\\","/")
        if path.startswith("/") or ".." in Path(path).parts: raise ValueError("Path traversal rejected")
        if not path.startswith(PREFIXES): raise ValueError(f"Path outside allowlist: {path}")
        if path in paths: raise ValueError("Duplicate patch path")
        paths.append(path)
    if not paths or len(paths)>MAX_FILES: raise ValueError("No patch targets or too many files")
    if re.search(r"(?m)^deleted file mode |^rename from |^rename to ",diff): raise ValueError("Delete/rename disabled")
    return paths
def apply_test(diff):
    patch=state_dir()/"pending.patch"; patch.write_text(diff,encoding="utf-8")
    try:
        c=run(["git","apply","--check",str(patch)])
        if c.returncode: return False,"Patch check failed: "+(c.stderr or c.stdout)
        a=run(["git","apply",str(patch)])
        if a.returncode: return False,"Patch apply failed: "+(a.stderr or a.stdout)
        w=run(["git","diff","--check"])
        if w.returncode: git("reset","--hard","HEAD"); return False,"Whitespace check failed: "+w.stderr
        t=run([sys.executable,"-m","pytest","-q"],1800); output=(t.stdout+"\n"+t.stderr).strip()
        if t.returncode: git("reset","--hard","HEAD"); return False,"Tests failed; rolled back.\n"+output[-10000:]
        return True,output[-10000:]
    finally: patch.unlink(missing_ok=True)
def report(data):
    p=state_dir(); (p/"developer_agent_report.json").write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8")
    with (p/"developer_agent_history.jsonl").open("a",encoding="utf-8") as f: f.write(json.dumps(data,ensure_ascii=False)+"\n")
def cycle(model,url):
    prepare(); item=ask(model,url); task=str(item.get("task_id","unspecified"))[:100]; summary=str(item.get("summary",""))[:2000]; diff=item.get("diff","")
    if not diff: report({"task_id":task,"summary":summary,"status":"NO_PATCH"}); LOG.info("No patch: %s",summary); return
    paths=validate(diff); ok,out=apply_test(diff)
    data={"task_id":task,"summary":summary,"files":paths,"status":"TESTS_PASSED" if ok else "REJECTED_OR_TEST_FAILED","test_output":out,"branch":WORK,"push_performed":False}
    if ok:
        git("add","--",*paths); git("commit","-m",f"HDS agent: {task}"); data["commit"]=git("rev-parse","HEAD")
    report(data); LOG.info("%s: %s",data["status"],task)
def main():
    p=argparse.ArgumentParser(); p.add_argument("--once",action="store_true"); p.add_argument("--interval-minutes",type=int,default=45); p.add_argument("--max-cycles",type=int,default=0); p.add_argument("--model",default=os.getenv("HDS_DEV_OLLAMA_MODEL",MODEL)); p.add_argument("--ollama-url",default=os.getenv("HDS_DEV_OLLAMA_URL","http://127.0.0.1:11434")); a=p.parse_args()
    logging.basicConfig(level=logging.INFO,format="%(asctime)s %(levelname)s %(message)s",handlers=[logging.StreamHandler(),logging.FileHandler(state_dir()/"developer_agent.log",encoding="utf-8")])
    if a.interval_minutes<15: p.error("interval must be at least 15 minutes")
    if a.model.lower().startswith(("claude","gpt-","openai")): p.error("Only local Ollama models are supported")
    count=0
    while True:
        try: cycle(a.model,a.ollama_url); count+=1
        except (urllib.error.URLError,TimeoutError,RuntimeError,ValueError,OSError,subprocess.TimeoutExpired) as e:
            LOG.exception("Cycle blocked safely: %s",e); report({"status":"BLOCKED","error":str(e),"push_performed":False})
        if a.once or (a.max_cycles and count>=a.max_cycles): break
        LOG.info("Sleeping %s minutes",a.interval_minutes); time.sleep(a.interval_minutes*60)
    return 0
if __name__=="__main__": raise SystemExit(main())
