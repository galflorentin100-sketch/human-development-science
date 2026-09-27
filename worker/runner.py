"""Minimal isolated verification worker entrypoint."""
import os,sys

def main():
    if os.getenv("HDS_WORKER_NETWORK","none") != "none": raise SystemExit("refusing execution: HDS_WORKER_NETWORK must be none")
    if os.geteuid() == 0: raise SystemExit("refusing execution as root")
    command=sys.argv[1:]
    if not command: raise SystemExit("verification command required")
    if command[0] not in {"pytest","python","python3"} or any(x in {"-c","--command","-m","--module"} for x in command): raise SystemExit("verification command is not allowlisted")
    import subprocess
    result=subprocess.run(command,cwd="/workspace",env={"PATH":"/usr/local/bin:/usr/bin:/bin","PYTHONDONTWRITEBYTECODE":"1","PYTHONNOUSERSITE":"1"},check=False)
    raise SystemExit(result.returncode)

if __name__=="__main__": main()
