"""Restore a PostgreSQL custom-format backup into a disposable target database."""
from __future__ import annotations
import argparse, hashlib, os, subprocess
from pathlib import Path

def main():
    p=argparse.ArgumentParser()
    p.add_argument("backup",type=Path)
    a=p.parse_args()
    url=os.environ.get("DATABASE_URL")
    if not url: raise SystemExit("DATABASE_URL is required")
    b=a.backup
    if not b.is_file(): raise SystemExit(f"backup not found: {b}")
    digest=hashlib.sha256(b.read_bytes()).hexdigest()
    side=b.with_suffix(".sha256")
    if side.is_file() and side.read_text(encoding="utf-8").split()[0]!=digest:
        raise SystemExit("backup checksum mismatch")
    r=subprocess.run(["pg_restore","--exit-on-error","--no-owner","--no-privileges","--dbname",url,str(b)],capture_output=True,text=True)
    if r.returncode: raise SystemExit("pg_restore failed: " + (r.stderr.strip() or r.stdout.strip() or f"exit {r.returncode}"))
    q=subprocess.run(["psql",url,"-Atqc","SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public'"],capture_output=True,text=True)
    if q.returncode: raise SystemExit("restored database schema query failed: " + (q.stderr.strip() or f"exit {q.returncode}"))
    if int(q.stdout.strip() or "0")==0: raise SystemExit("restored database schema verification failed: no public tables were restored")
    print(f"Backup restore verified: {b}")
    print(f"SHA256: {digest}")
if __name__=="__main__": main()
