"""Persistence and independent review for structured study extractions."""
from __future__ import annotations

import json
from uuid import uuid4

from app.models import now
from app.research_metadata import validate_study_record, serialize_study_record


class StudyExtractionService:
    def __init__(self, db):
        self.db = db
        # Idempotent SQLite migration; the table is scoped to a research workspace
        # and pins each extraction to an immutable parsed-source content hash.
        self.db.execute("""CREATE TABLE IF NOT EXISTS research_study_extractions (
            id TEXT PRIMARY KEY,
            workspace_id TEXT NOT NULL REFERENCES research_workspaces(id),
            project_id TEXT NOT NULL REFERENCES projects(id),
            source_id TEXT NOT NULL REFERENCES sources(id),
            source_content_hash TEXT NOT NULL,
            source_content_level TEXT NOT NULL,
            extraction_json TEXT NOT NULL,
            status TEXT NOT NULL,
            created_by TEXT NOT NULL,
            reviewed_by TEXT,
            review_decision TEXT,
            review_rationale TEXT,
            created_at TEXT NOT NULL,
            reviewed_at TEXT,
            UNIQUE(workspace_id,source_id,source_content_hash)
        )""")
        self.db.execute("CREATE INDEX IF NOT EXISTS idx_research_study_extractions_workspace ON research_study_extractions(workspace_id,status,created_at)")

    def create(self, workspace_id, source_id, payload, extractor, actor, source_content_level="FULL_TEXT"):
        if not str(actor or "").strip():
            raise ValueError("actor is required")
        workspace = self.db.one("SELECT * FROM research_workspaces WHERE id=?", (workspace_id,))
        if not workspace:
            raise ValueError("research workspace not found")
        if workspace["status"] not in {"ACTIVE", "SYNTHESIS_READY"}:
            raise ValueError("study extraction requires an active research workspace")
        linked = self.db.one(
            "SELECT 1 FROM research_workspace_sources WHERE workspace_id=? AND source_id=?",
            (workspace_id, source_id),
        )
        if not linked:
            raise ValueError("source is not linked to this research workspace")
        parsed = self.db.one(
            """SELECT * FROM evidence_sources
               WHERE source_id=? AND state='PARSED' AND TRIM(COALESCE(content,''))<>''
               ORDER BY parsed_at DESC LIMIT 1""",
            (source_id,),
        )
        if not parsed:
            raise ValueError("source has no parsed text; extraction is blocked")
        record = validate_study_record(
            payload, source_id=source_id, source_content_hash=parsed["content_hash"],
            extractor=extractor, source_text=parsed["content"],
            source_content_level=source_content_level,
        )
        record_json = serialize_study_record(record)
        existing = self.db.one(
            "SELECT * FROM research_study_extractions WHERE workspace_id=? AND source_id=? AND source_content_hash=?",
            (workspace_id, source_id, parsed["content_hash"]),
        )
        if existing:
            return existing
        extraction_id = str(uuid4())
        self.db.execute(
            """INSERT INTO research_study_extractions
               (id,workspace_id,project_id,source_id,source_content_hash,source_content_level,
                extraction_json,status,created_by,created_at)
               VALUES (?,?,?,?,?,?,?,'PENDING_REVIEW',?,?)""",
            (extraction_id, workspace_id, workspace["project_id"], source_id,
             parsed["content_hash"], source_content_level.upper(), record_json, actor, now()),
        )
        return self.get(extraction_id)

    def get(self, extraction_id):
        row = self.db.one("SELECT * FROM research_study_extractions WHERE id=?", (extraction_id,))
        if not row:
            raise ValueError("study extraction not found")
        result = dict(row)
        result["extraction"] = json.loads(result.pop("extraction_json"))
        return result

    def list_workspace(self, workspace_id):
        if not self.db.one("SELECT id FROM research_workspaces WHERE id=?", (workspace_id,)):
            raise ValueError("research workspace not found")
        rows = self.db.all(
            "SELECT id FROM research_study_extractions WHERE workspace_id=? ORDER BY created_at DESC",
            (workspace_id,),
        )
        return [self.get(row["id"]) for row in rows]

    def review(self, extraction_id, reviewer, decision, rationale):
        if decision not in {"ACCEPTED", "REJECTED", "NEEDS_CORRECTION"}:
            raise ValueError("decision must be ACCEPTED, REJECTED, or NEEDS_CORRECTION")
        if not str(reviewer or "").strip() or not str(rationale or "").strip():
            raise ValueError("reviewer and rationale are required")
        row = self.db.one("SELECT * FROM research_study_extractions WHERE id=?", (extraction_id,))
        if not row:
            raise ValueError("study extraction not found")
        if row["created_by"] == reviewer:
            raise ValueError("reviewer must be independent from the extractor")
        if row["status"] != "PENDING_REVIEW":
            raise ValueError("study extraction has already been reviewed")
        changed = self.db.execute(
            """UPDATE research_study_extractions
               SET status=?,reviewed_by=?,review_decision=?,review_rationale=?,reviewed_at=?
               WHERE id=? AND status='PENDING_REVIEW'""",
            (decision, reviewer, decision, rationale, now(), extraction_id),
        )
        if changed.rowcount != 1:
            raise ValueError("study extraction review was resolved concurrently")
        return self.get(extraction_id)
