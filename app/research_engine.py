"""Governed research workspace: question -> sources -> synthesis -> review.

This layer does not claim scientific truth. It stores research work products and
keeps source/provenance state explicit until a human-reviewed finding is created.
"""
from __future__ import annotations
import hashlib, json
from uuid import uuid4
from app.models import now
from app.evidence_pipeline import EvidencePipeline

class ResearchEngine:
    STATUSES={"DRAFT","ACTIVE","SYNTHESIS_READY","REVIEWED","CLOSED"}

    def __init__(self,db):
        self.db=db
        self._ensure()

    def _ensure(self):
        self.db.execute("""CREATE TABLE IF NOT EXISTS research_workspaces (
            id TEXT PRIMARY KEY, project_id TEXT NOT NULL, question TEXT NOT NULL,
            scope TEXT NOT NULL, inclusion_rules TEXT NOT NULL, exclusion_rules TEXT NOT NULL,
            status TEXT NOT NULL, owner TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        )""")
        self.db.execute("""CREATE TABLE IF NOT EXISTS research_workspace_sources (
            id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL REFERENCES research_workspaces(id),
            source_id TEXT NOT NULL REFERENCES sources(id), relevance TEXT NOT NULL,
            notes TEXT NOT NULL, content_hash TEXT, reviewed INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL, UNIQUE(workspace_id,source_id)
        )""")
        self.db.execute("""CREATE TABLE IF NOT EXISTS research_syntheses (
            id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL REFERENCES research_workspaces(id),
            synthesis TEXT NOT NULL, limitations TEXT NOT NULL, uncertainty TEXT NOT NULL,
            provenance_hash TEXT NOT NULL, evidence_refs TEXT NOT NULL DEFAULT '[]',
            status TEXT NOT NULL, created_by TEXT NOT NULL, created_at TEXT NOT NULL
        )""")
        cols=set(self.db.table_columns("research_syntheses"))
        if "evidence_refs" not in cols:
            self.db.execute("ALTER TABLE research_syntheses ADD COLUMN evidence_refs TEXT NOT NULL DEFAULT '[]'")

    def create(self,project_id,question,scope="",inclusion_rules=(),exclusion_rules=(),owner="system"):
        if not str(question or "").strip(): raise ValueError("research question is required")
        i=str(uuid4()); ts=now()
        self.db.execute(
            "INSERT INTO research_workspaces(id,project_id,question,scope,inclusion_rules,exclusion_rules,status,owner,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (i,project_id,question,scope,json.dumps(list(inclusion_rules),sort_keys=True),json.dumps(list(exclusion_rules),sort_keys=True),"DRAFT",owner,ts,ts))
        return self.get(i)

    def activate(self,workspace_id,actor):
        row=self._get(workspace_id)
        if row["status"]!="DRAFT": raise ValueError("workspace must be DRAFT")
        self.db.execute("UPDATE research_workspaces SET status='ACTIVE',updated_at=? WHERE id=? AND status='DRAFT'",(now(),workspace_id))
        self.db.audit("research_workspace.activated","research_workspace",workspace_id,actor,{},now(),str(uuid4()))
        return self.get(workspace_id)

    def add_source(self,workspace_id,source_id,relevance="UNASSESSED",notes="",content=None):
        row=self._get(workspace_id)
        if row["status"] not in {"DRAFT","ACTIVE"}: raise ValueError("sources can only be added before synthesis")
        if not self.db.one("SELECT id FROM sources WHERE id=?",(source_id,)): raise ValueError("source not found")
        digest=None
        if content is not None:
            digest=hashlib.sha256(str(content).encode("utf-8")).hexdigest()
            EvidencePipeline(self.db).ingest_text(source_id,str(content))
        i=str(uuid4())
        self.db.execute(
            "INSERT OR IGNORE INTO research_workspace_sources(id,workspace_id,source_id,relevance,notes,content_hash,reviewed,created_at) VALUES (?,?,?,?,?,?,0,?)",
            (i,workspace_id,source_id,relevance,notes,digest,now()))
        return self.db.one("SELECT * FROM research_workspace_sources WHERE workspace_id=? AND source_id=?",(workspace_id,source_id))

    def synthesize(self,workspace_id,synthesis,limitations="",uncertainty="",created_by="system",evidence_refs=()):
        row=self._get(workspace_id)
        if row["status"]!="ACTIVE": raise ValueError("workspace must be ACTIVE")
        sources=self.db.all("SELECT * FROM research_workspace_sources WHERE workspace_id=?",(workspace_id,))
        if not sources: raise ValueError("synthesis requires at least one source")
        if not str(synthesis or "").strip(): raise ValueError("synthesis is required")
        provenance={"workspace_id":workspace_id,"source_ids":sorted(x["source_id"] for x in sources),
                    "source_hashes":sorted(x["content_hash"] for x in sources if x.get("content_hash")),
            "evidence_refs":sorted(str(x) for x in evidence_refs)}
        ph=hashlib.sha256(json.dumps(provenance,sort_keys=True).encode()).hexdigest()
        i=str(uuid4()); ts=now()
        with self.db.transaction() as con:
            con.execute(
                "INSERT INTO research_syntheses(id,workspace_id,synthesis,limitations,uncertainty,provenance_hash,evidence_refs,status,created_by,created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (i,workspace_id,synthesis,limitations,uncertainty,ph,json.dumps(list(evidence_refs),sort_keys=True),"CANDIDATE",created_by,ts))
            updated=con.execute("UPDATE research_workspaces SET status='SYNTHESIS_READY',updated_at=? WHERE id=? AND status='ACTIVE'",(ts,workspace_id))
            if updated.rowcount != 1: raise ValueError("workspace changed before synthesis could be committed")
        return self.db.one("SELECT * FROM research_syntheses WHERE id=?",(i,))

    def review(self,synthesis_id,reviewer,decision,rationale):
        syn=self.db.one("SELECT * FROM research_syntheses WHERE id=?",(synthesis_id,))
        if not syn: raise ValueError("synthesis not found")
        if decision not in {"ACCEPTED","REJECTED"}: raise ValueError("decision must be ACCEPTED or REJECTED")
        if not str(rationale or "").strip(): raise ValueError("review rationale is required")
        if syn["created_by"]==reviewer and reviewer!="system": raise ValueError("reviewer must be independent")
        workspace=self._get(syn["workspace_id"])
        if workspace["status"]!="SYNTHESIS_READY": raise ValueError("workspace is not ready for synthesis review")
        new_status="REVIEWED" if decision=="ACCEPTED" else "ACTIVE"
        ts=now()
        with self.db.transaction() as con:
            updated=con.execute("UPDATE research_syntheses SET status=? WHERE id=? AND status='CANDIDATE'",(decision,synthesis_id))
            if updated.rowcount != 1: raise ValueError("synthesis review was already resolved")
            workspace_updated=con.execute("UPDATE research_workspaces SET status=?,updated_at=? WHERE id=? AND status='SYNTHESIS_READY'",(new_status,ts,workspace["id"]))
            if workspace_updated.rowcount != 1: raise ValueError("workspace review state changed concurrently")
            con.execute("INSERT INTO audit_logs(id,event_type,entity_type,entity_id,actor,payload,created_at) VALUES (?,?,?,?,?,?,?)",
                        (str(uuid4()),"research_synthesis.reviewed","research_synthesis",synthesis_id,reviewer,
                         json.dumps({"decision":decision,"rationale":rationale},sort_keys=True),ts))
        return self.db.one("SELECT * FROM research_syntheses WHERE id=?",(synthesis_id,))

    def readiness(self,synthesis_id):
        syn=self.db.one("SELECT * FROM research_syntheses WHERE id=?",(synthesis_id,))
        if not syn: raise ValueError("synthesis not found")
        from app.research_evidence_auditor import ResearchEvidenceAuditor
        evidence=ResearchEvidenceAuditor(self.db).audit_synthesis(synthesis_id)
        from app.skeptic import SkepticService
        skeptic=self.db.one("SELECT * FROM research_skeptic_reviews WHERE synthesis_id=? ORDER BY created_at DESC LIMIT 1",(synthesis_id,))
        skeptic_status=skeptic["status"] if skeptic else "MISSING"
        blockers=[]
        if evidence["status"]!="PASS": blockers.append("evidence_audit")
        if skeptic_status not in {"ACCEPTED"}: blockers.append("skeptic_review")
        if syn["status"]!="ACCEPTED": blockers.append("synthesis_review")
        return {"synthesis_id":synthesis_id,"ready":not blockers,"blockers":blockers,
                "evidence_audit":evidence,"skeptic_status":skeptic_status}

    def promote_to_candidate_finding(self,synthesis_id,actor):
        syn=self.db.one("SELECT * FROM research_syntheses WHERE id=?",(synthesis_id,))
        if not syn: raise ValueError("synthesis not found")
        readiness=self.readiness(synthesis_id)
        if not readiness["ready"]: raise ValueError("research synthesis is not ready: "+",".join(readiness["blockers"]))
        workspace=self._get(syn["workspace_id"])
        from app.research import ResearchFindingService
        existing=self.db.one(
            "SELECT * FROM research_findings WHERE project_id=? AND source_type='LITERATURE' AND source_id=? LIMIT 1",
            (workspace["project_id"],synthesis_id))
        if existing: return existing
        interpretation=json.dumps({
            "synthesis":syn["synthesis"],
            "limitations":syn["limitations"],
            "uncertainty":syn["uncertainty"],
            "provenance_hash":syn["provenance_hash"],
            "evidence_refs":json.loads(syn["evidence_refs"] or "[]"),
            "note":"Candidate only; scientific acceptance still requires evidence review."
        },sort_keys=True)
        return ResearchFindingService(self.db).create(
            workspace["project_id"],syn["synthesis"],classification="INFERENCE",
            source_type="LITERATURE",source_id=synthesis_id,evidence_refs=json.loads(syn["evidence_refs"] or "[]"),
            interpretation=interpretation,created_by=actor)

    def get(self,workspace_id):
        row=self._get(workspace_id)
        row["sources"]=self.db.all("SELECT * FROM research_workspace_sources WHERE workspace_id=? ORDER BY created_at",(workspace_id,))
        row["syntheses"]=self.db.all("SELECT * FROM research_syntheses WHERE workspace_id=? ORDER BY created_at DESC",(workspace_id,))
        return row

    def list(self,project_id,status=None):
        if status and status not in self.STATUSES: raise ValueError("invalid workspace status")
        q="SELECT * FROM research_workspaces WHERE project_id=?"
        p=[project_id]
        if status: q+=" AND status=?"; p.append(status)
        return self.db.all(q+" ORDER BY created_at DESC",tuple(p))

    def _get(self,i):
        row=self.db.one("SELECT * FROM research_workspaces WHERE id=?",(i,))
        if not row: raise ValueError("research workspace not found")
        return row
