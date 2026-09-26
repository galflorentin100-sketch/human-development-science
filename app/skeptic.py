"""Skeptic review layer for research work.

It produces a reviewable challenge to a synthesis; it never changes claims or
scientific status automatically.
"""
from __future__ import annotations
import json
from uuid import uuid4
from app.models import now

class SkepticService:
    def __init__(self,db):
        self.db=db
        self.db.execute("""CREATE TABLE IF NOT EXISTS research_skeptic_reviews (
            id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, synthesis_id TEXT,
            project_id TEXT NOT NULL, reviewer_agent_id TEXT, status TEXT NOT NULL,
            objections TEXT NOT NULL, missing_evidence TEXT NOT NULL,
            alternative_explanations TEXT NOT NULL, created_at TEXT NOT NULL,
            reviewed_at TEXT
        )""")

    def create(self,workspace_id,synthesis_id=None,agent_id=None):
        ws=self.db.one("SELECT * FROM research_workspaces WHERE id=?",(workspace_id,))
        if not ws: raise ValueError("research workspace not found")
        syn=self.db.one("SELECT * FROM research_syntheses WHERE id=?",(synthesis_id,)) if synthesis_id else None
        if synthesis_id and not syn: raise ValueError("synthesis not found")
        if syn and syn["workspace_id"]!=workspace_id: raise ValueError("synthesis does not belong to workspace")
        rid=str(uuid4())
        self.db.execute(
            "INSERT INTO research_skeptic_reviews(id,workspace_id,synthesis_id,project_id,reviewer_agent_id,status,objections,missing_evidence,alternative_explanations,created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (rid,workspace_id,synthesis_id,ws["project_id"],agent_id,"READY_FOR_REVIEW","[]","[]","[]",now()))
        return self.get(rid)

    def record(self,review_id,objections=(),missing_evidence=(),alternative_explanations=()):
        row=self.get(review_id)
        if row["status"]!="READY_FOR_REVIEW": raise ValueError("skeptic review is not editable")
        self.db.execute(
            "UPDATE research_skeptic_reviews SET objections=?,missing_evidence=?,alternative_explanations=? WHERE id=?",
            (json.dumps(list(objections),sort_keys=True),json.dumps(list(missing_evidence),sort_keys=True),
             json.dumps(list(alternative_explanations),sort_keys=True),review_id))
        return self.get(review_id)

    def review(self,review_id,decision,reviewer,rationale):
        row=self.get(review_id)
        if decision not in {"ACCEPTED","NEEDS_EVIDENCE","REJECTED"}: raise ValueError("invalid skeptic decision")
        if not str(rationale or "").strip(): raise ValueError("review rationale is required")
        if row.get("reviewer_agent_id") and str(row["reviewer_agent_id"])==str(reviewer):
            raise ValueError("skeptic review requires an independent reviewer")
        ts=now()
        with self.db.transaction() as con:
            updated=con.execute("UPDATE research_skeptic_reviews SET status=?,reviewed_at=? WHERE id=? AND status='READY_FOR_REVIEW'",(decision,ts,review_id))
            if updated.rowcount != 1: raise ValueError("skeptic review was already resolved")
            con.execute("INSERT INTO audit_logs(id,event_type,entity_type,entity_id,actor,payload,created_at) VALUES (?,?,?,?,?,?,?)",
                        (str(uuid4()),"scientific.skeptic_reviewed","research_skeptic_review",review_id,reviewer,
                         json.dumps({"decision":decision,"rationale":rationale},sort_keys=True),ts))
        return self.get(review_id)

    def get(self,review_id):
        row=self.db.one("SELECT * FROM research_skeptic_reviews WHERE id=?",(review_id,))
        if not row: raise ValueError("skeptic review not found")
        for key in ("objections","missing_evidence","alternative_explanations"):
            row[key]=json.loads(row[key] or "[]")
        return row
