"""Isolated verification worker. Polls a shared job volume; never needs network access."""
import json, os, subprocess, time
from pathlib import Path

ROOT=Path(os.getenv("HDS_WORKER_SHARED_DIR","/var/lib/hds-code-worker"))
RESULTS=Path(os.getenv("HDS_WORKER_RESULT_DIR","/var/lib/hds-code-worker-results"))
ALLOWED={"pytest","python","python3"}

def run_job(job):
    req=json.loads((job/"request.json").read_text(encoding="utf-8"))
    command=req.get("command"); timeout=min(max(int(req.get("timeout",300)),1),900)
    if not isinstance(command,list) or not command or command[0] not in ALLOWED:
        raise ValueError("verification command is not allowlisted")
    if any(x in {"-c","--command","-m","--module"} for x in command):
        raise ValueError("dynamic code execution is not allowed")
    for arg in command[1:]:
        if isinstance(arg,str) and arg.startswith("-"): continue
        if Path(arg).is_absolute() or ".." in Path(arg).parts:
            raise ValueError("verification command cannot address paths outside the workspace")
    env={"PATH":"/usr/local/bin:/usr/bin:/bin","PYTHONDONTWRITEBYTECODE":"1","PYTHONNOUSERSITE":"1"}
    try:
        p=subprocess.run(command,cwd=job/"workspace",env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=timeout,check=False)
        result={"passed":p.returncode==0,"return_code":p.returncode,"timed_out":False,"output":p.stdout[-200000:]}
    except subprocess.TimeoutExpired as exc:
        out=exc.stdout or ""
        if isinstance(out,bytes): out=out.decode("utf-8",errors="replace")
        result={"passed":False,"return_code":None,"timed_out":True,"output":out[-200000:]}
    RESULTS.mkdir(parents=True,exist_ok=True)
    out=RESULTS/(job.name+".json"); tmp=RESULTS/(job.name+".json.tmp")
    tmp.write_text(json.dumps(result),encoding="utf-8"); tmp.replace(out)

def main():
    if os.getenv("HDS_WORKER_NETWORK","none")!="none" or os.geteuid()==0:
        raise SystemExit("worker security precondition failed")
    ROOT.mkdir(parents=True,exist_ok=True); jobs=ROOT/"jobs"; jobs.mkdir(exist_ok=True)
    RESULTS.mkdir(parents=True,exist_ok=True)
    while True:
        for job in sorted(jobs.iterdir()):
            if not job.is_dir() or not (job/"request.json").exists() or (RESULTS/(job.name+".json")).exists(): continue
            try: run_job(job)
            except Exception as exc:
                (RESULTS/(job.name+".json")).write_text(json.dumps({"passed":False,"return_code":None,"timed_out":False,"output":str(exc)}),encoding="utf-8")
        time.sleep(0.25)

if __name__=="__main__": main()
