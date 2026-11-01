"""Create a PostgreSQL custom-format backup without exposing credentials."""
from __future__ import annotations
import argparse, hashlib, os, subprocess
from datetime import datetime, timezone
from pathlib import Path

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--output-dir",default="backups")
    a=p.parse_args()
    url=os.environ.get("DATABASE_URL")
    if not url: raise SystemExit("DATABASE_URL is required")
    out=Path(a.output_dir); out.mkdir(parents=True,exist_ok=True)
    stamp=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dest=out/f"hds-postgres-{stamp}.dump"
    image=os.environ.get("HDS_PG_CLIENT_IMAGE")
    if image:
        command=["docker","run","--rm","--network","host","-e","DATABASE_URL","-v",f"{out.resolve()}:/backup",image,
                 "pg_dump","--format=custom","--no-owner","--no-privileges","--file",f"/backup/{dest.name}",url]
    else:
        command=["pg_dump","--format=custom","--no-owner","--no-privileges","--file",str(dest),url]
    r=subprocess.run(command,capture_output=True,text=True)
    if r.returncode:
        dest.unlink(missing_ok=True); raise SystemExit("pg_dump failed: " + (r.stderr.strip() or r.stdout.strip() or f"exit {r.returncode}"))
    digest=hashlib.sha256(dest.read_bytes()).hexdigest()
    dest.with_suffix(".sha256").write_text(f"{digest}  {dest.name}\n",encoding="utf-8")
    print(f"Backup created: {dest}")
    print(f"SHA256: {digest}")
if __name__=="__main__": main()
