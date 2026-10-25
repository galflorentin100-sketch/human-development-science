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
        cols=set(self.db.table_columns("research_workspaces"))
        if "research_queue_id" not in cols:
            self.db.execute("ALTER TABLE research_workspaces ADD COLUMN research_queue_id TEXT")
        cols=set(self.db.table_columns("research_syntheses"))
        if "evidence_refs" not in cols:
            self.db.execute("ALTER TABLE research_syntheses ADD COLUMN evidence_refs TEXT NOT NULL DEFAULT '[]'")

    def create(self,project_id,question,scope="",inclusion_rules=(),exclusion_rules=(),owner="system"):
        if not str(project_id or "").strip(): raise ValueError("project_id is required")
        if not self.db.one("SELECT 1 FROM projects WHERE id=?", (project_id,)): raise ValueError("project not found")
        if not str(question or "").strip(): raise ValueError("research question is required")
        i=str(uuid4()); ts=now()
        self.db.execute(
            "INSERT INTO research_workspaces(id,project_id,question,scope,inclusion_rules,exclusion_rules,status,owner,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (i,project_id,question,scope,json.dumps(list(inclusion_rules),sort_keys=True),json.dumps(list(exclusion_rules),sort_keys=True),"DRAFT",owner,ts,ts))
        return self.get(i)

    def activate(self,workspace_id,actor):
        ts=now()
        with self.db.transaction() as con:
            row=con.execute("SELECT status FROM research_workspaces WHERE id=?",(workspace_id,)).fetchone()
            if not row: raise ValueError("research workspace not found")
            if dict(row)["status"]!="DRAFT": raise ValueError("workspace must be DRAFT")
            updated=con.execute(
                "UPDATE research_workspaces SET status='ACTIVE',updated_at=? WHERE id=? AND status='DRAFT'",
                (ts,workspace_id))
            if updated.rowcount != 1:
                raise ValueError("workspace changed concurrently; retry")
            con.execute(
                "INSERT INTO audit_logs(id,event_type,entity_type,entity_id,actor,payload,created_at) VALUES (?,?,?,?,?,?,?)",
                (str(uuid4()),"research_workspace.activated","research_workspace",workspace_id,actor,"{}",ts))
        return self.get(workspace_id)

    def add_source(self,workspace_id,source_id,relevance="UNASSESSED",notes="",content=None):
        digest=None
        if content is not None:
            digest=hashlib.sha256(str(content).encode("utf-8")).hexdigest()
        with self.db.transaction() as con:
            row=con.execute("SELECT * FROM research_workspaces WHERE id=?",(workspace_id,)).fetchone()
            if not row: raise ValueError("research workspace not found")
            row=dict(row)
            if row["status"] not in {"DRAFT","ACTIVE"}:
                raise ValueError("sources can only be added before synthesis")
            if not con.execute("SELECT id FROM sources WHERE id=?",(source_id,)).fetchone():
                raise ValueError("source not found")
            if content is not None:
                EvidencePipeline(self.db)._ingest_text_in_transaction(con,source_id,str(content))
            i=str(uuid4())
            con.execute(
                "INSERT INTO research_workspace_sources(id,workspace_id,source_id,relevance,notes,content_hash,reviewed,created_at) VALUES (?,?,?,?,?,?,0,?) ON CONFLICT(workspace_id,source_id) DO NOTHING",
                (i,workspace_id,source_id,relevance,notes,digest,now()))
            return dict(con.execute(
                "SELECT * FROM research_workspace_sources WHERE workspace_id=? AND source_id=?",
                (workspace_id,source_id)).fetchone())

    def synthesize(self,workspace_id,synthesis,limitations="",uncertainty="",created_by="system",evidence_refs=()):
        row=self._get(workspace_id)
        if row["status"]!="ACTIVE": raise ValueError("workspace must be ACTIVE")
        sources=self.db.all("SELECT * FROM research_workspace_sources WHERE workspace_id=?",(workspace_id,))
        if not sources: raise ValueError("synthesis requires at least one source")
        if not str(synthesis or "").strip(): raise ValueError("synthesis is required")
        refs=[str(x) for x in (evidence_refs or ())]
        for ref in refs:
            evidence=self.db.one(
                "SELECT e.id FROM evidence e JOIN claims c ON c.id=e.claim_id WHERE e.id=? AND c.project_id=?",
                (ref, row["project_id"]))
            if not evidence:
                raise ValueError("research synthesis evidence belongs to another project or does not exist")
        provenance={"workspace_id":workspace_id,"source_ids":sorted(x["source_id"] for x in sources),
                    "source_hashes":sorted(x["content_hash"] for x in sources if x.get("content_hash")),
            "evidence_refs":sorted(refs)}
        ph=hashlib.sha256(json.dumps(provenance,sort_keys=True).encode()).hexdigest()
        i=str(uuid4()); ts=now()
        with self.db.transaction() as con:
            con.execute(
                "INSERT INTO research_syntheses(id,workspace_id,synthesis,limitations,uncertainty,provenance_hash,evidence_refs,status,created_by,created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (i,workspace_id,synthesis,limitations,uncertainty,ph,json.dumps(refs,sort_keys=True),"CANDIDATE",created_by,ts))
            updated=con.execute("UPDATE research_workspaces SET status='SYNTHESIS_READY',updated_at=? WHERE id=? AND status='ACTIVE'",(ts,workspace_id))
            if updated.rowcount != 1: raise ValueError("workspace changed before synthesis could be committed")
        return self.db.one("SELECT * FROM research_syntheses WHERE id=?",(i,))

    def review(self,synthesis_id,reviewer,decision,rationale):
        if decision not in {"ACCEPTED","REJECTED"}: raise ValueError("decision must be ACCEPTED or REJECTED")
        if not str(rationale or "").strip(): raise ValueError("review rationale is required")
        ts=now()
        with self.db.transaction() as con:
            syn=con.execute("SELECT * FROM research_syntheses WHERE id=?",(synthesis_id,)).fetchone()
            if not syn: raise ValueError("synthesis not found")
            syn=dict(syn)
            if syn["created_by"]==reviewer and reviewer!="system": raise ValueError("reviewer must be independent")
            workspace=con.execute("SELECT * FROM research_workspaces WHERE id=?",(syn["workspace_id"],)).fetchone()
            if not workspace: raise ValueError("research workspace not found")
            workspace=dict(workspace)
            if workspace["status"]!="SYNTHESIS_READY": raise ValueError("workspace is not ready for synthesis review")
            if decision=="ACCEPTED":
                refs=json.loads(syn["evidence_refs"] or "[]")
                if not refs:
                    raise ValueError("ACCEPTED synthesis requires evidence references")
                workspace_source_ids={
                    str(r["source_id"])
                    for r in con.execute(
                        "SELECT source_id FROM research_workspace_sources WHERE workspace_id=?",
                        (syn["workspace_id"],)
                    ).fetchall()
                }
                for ref in refs:
                    evidence=con.execute(
                        """SELECT e.id,e.source_id,e.verified
                           FROM evidence e
                           JOIN claims c ON c.id=e.claim_id
                           WHERE e.id=? AND c.project_id=?""",
                        (str(ref),workspace["project_id"])
                    ).fetchone()
                    if not evidence:
                        raise ValueError("ACCEPTED synthesis requires project-scoped evidence")
                    evidence=dict(evidence)
                    if str(evidence["source_id"]) not in workspace_source_ids:
                        raise ValueError("ACCEPTED synthesis contains out-of-scope evidence")
                    verdicts={
                        str(r["verdict"]).upper()
                        for r in con.execute(
                            "SELECT verdict FROM evidence_reviews WHERE evidence_id=?",
                            (str(ref),)
                        ).fetchall()
                    }
                    if evidence["verified"] != 1 or verdicts != {"VERIFIED"}:
                        raise ValueError("ACCEPTED synthesis requires all referenced evidence to be VERIFIED")
                skeptic=con.execute(
                    """SELECT status
                       FROM research_skeptic_reviews
                       WHERE synthesis_id=?
                       ORDER BY created_at DESC
                       LIMIT 1""",
                    (synthesis_id,)
                ).fetchone()
                if not skeptic or str(skeptic["status"])!="ACCEPTED":
                    raise ValueError("ACCEPTED synthesis requires an accepted skeptic review")
            new_status="REVIEWED" if decision=="ACCEPTED" else "ACTIVE"
            updated=con.execute("UPDATE research_syntheses SET status=? WHERE id=? AND status='CANDIDATE'",(decision,synthesis_id))
            if updated.rowcount != 1: raise ValueError("synthesis review was already resolved")
            workspace_updated=con.execute("UPDATE research_workspaces SET status=?,updated_at=? WHERE id=? AND status='SYNTHESIS_READY'",(new_status,ts,workspace["id"]))
            if workspace_updated.rowcount != 1: raise ValueError("workspace review state changed concurrently")
            queue_completed=False
            if decision=="ACCEPTED":
                # A founder-approved queue item represents the research question being worked.
                # It is complete once the governed synthesis itself is accepted; downstream
                # finding/knowledge promotion remains separately gated and auditable.
                queue_updated=con.execute(
                    "UPDATE hds_research_queue SET status='DONE',updated_at=? WHERE id=(SELECT research_queue_id FROM research_workspaces WHERE id=?) AND status='IN_PROGRESS'",
                    (ts,workspace["id"]))
                queue_completed=queue_updated.rowcount == 1
                if queue_completed:
                    con.execute(
                        "INSERT INTO audit_logs(id,event_type,entity_type,entity_id,actor,payload,created_at) VALUES (?,?,?,?,?,?,?)",
                        (str(uuid4()),"research_queue.completed","research_queue",workspace["research_queue_id"],reviewer,
                         json.dumps({"workspace_id":workspace["id"],"synthesis_id":synthesis_id},sort_keys=True),ts))
            con.execute("INSERT INTO audit_logs(id,event_type,entity_type,entity_id,actor,payload,created_at) VALUES (?,?,?,?,?,?,?)",
                        (str(uuid4()),"research_synthesis.reviewed","research_synthesis",synthesis_id,reviewer,
                         json.dumps({"decision":decision,"rationale":rationale,"research_queue_completed":queue_completed},sort_keys=True),ts))
        result=self.db.one("SELECT * FROM research_syntheses WHERE id=?",(synthesis_id,))
        if decision=="ACCEPTED":
            from app.research_handoff import ResearchHandoffCoordinator
            handoff=ResearchHandoffCoordinator(self.db).complete_accepted_synthesis(
                workspace["project_id"],synthesis_id,actor=reviewer)
            result=dict(result)
            result["handoff"]=handoff
        return result

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
        if not str(actor or "").strip(): raise ValueError("actor is required")
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
