from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS companies (id TEXT PRIMARY KEY, name TEXT NOT NULL, mission TEXT NOT NULL, vision TEXT NOT NULL, core_principle TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS agents (id TEXT PRIMARY KEY, name TEXT NOT NULL, role TEXT NOT NULL, mission TEXT NOT NULL, capabilities TEXT NOT NULL, permissions TEXT NOT NULL, version TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS projects (id TEXT PRIMARY KEY, company_id TEXT NOT NULL REFERENCES companies(id), objective TEXT NOT NULL, status TEXT NOT NULL, owner_agent_id TEXT NOT NULL REFERENCES agents(id), created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS tasks (id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id), title TEXT NOT NULL, status TEXT NOT NULL, assigned_agent_id TEXT REFERENCES agents(id), priority REAL NOT NULL, success_criteria TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_tasks_project_status ON tasks(project_id, status);
CREATE TABLE IF NOT EXISTS sources (id TEXT PRIMARY KEY, title TEXT NOT NULL, url TEXT NOT NULL UNIQUE, authors TEXT, publication_year INTEGER, source_type TEXT NOT NULL, verified_at TEXT NOT NULL, provenance_note TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS claims (id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id), statement TEXT NOT NULL, classification TEXT NOT NULL, evidence_level TEXT NOT NULL, confidence REAL NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS evidence (id TEXT PRIMARY KEY, claim_id TEXT NOT NULL REFERENCES claims(id), source_id TEXT NOT NULL REFERENCES sources(id), stance TEXT NOT NULL, excerpt TEXT NOT NULL, verified INTEGER NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS knowledge_items (id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id), kind TEXT NOT NULL, content TEXT NOT NULL, provenance TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS research_questions (id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id), question TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS agent_runs (id TEXT PRIMARY KEY, agent_id TEXT NOT NULL REFERENCES agents(id), task_id TEXT REFERENCES tasks(id), status TEXT NOT NULL, input_payload TEXT NOT NULL, output_payload TEXT NOT NULL, started_at TEXT NOT NULL, completed_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS evaluations (id TEXT PRIMARY KEY, agent_run_id TEXT NOT NULL REFERENCES agent_runs(id), evaluator TEXT NOT NULL, passed INTEGER NOT NULL, score REAL NOT NULL, details TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS audit_logs (id TEXT PRIMARY KEY, event_type TEXT NOT NULL, entity_type TEXT NOT NULL, entity_id TEXT NOT NULL, actor TEXT NOT NULL, payload TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS founder_briefs (id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id), content TEXT NOT NULL, action_required INTEGER NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS failures (id TEXT PRIMARY KEY, project_id TEXT REFERENCES projects(id), stage TEXT NOT NULL, expected_result TEXT NOT NULL, actual_result TEXT NOT NULL, root_cause TEXT NOT NULL, lesson TEXT NOT NULL, created_at TEXT NOT NULL);
"""
class Database:
    def __init__(self, path: str = "company_os.db"):
        self.path = Path(path)
    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        con = sqlite3.connect(self.path, timeout=10)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys = ON")
        con.execute("PRAGMA journal_mode = WAL")
        con.execute("PRAGMA busy_timeout = 10000")
        try:
            yield con
            con.commit()
        finally:
            con.close()
    def migrate(self) -> None:
        with self.connect() as con:
            con.executescript(SCHEMA)
    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> None:
        with self.connect() as con:
            con.execute(sql, params)
    def one(self, sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
        with self.connect() as con:
            row = con.execute(sql, params).fetchone()
        return dict(row) if row else None
    def all(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        with self.connect() as con:
            rows = con.execute(sql, params).fetchall()
        return [dict(row) for row in rows]
    def audit(self, event_type: str, entity_type: str, entity_id: str, actor: str, payload: dict[str, Any], created_at: str, audit_id: str) -> None:
        self.execute("INSERT INTO audit_logs VALUES (?, ?, ?, ?, ?, ?, ?)", (audit_id, event_type, entity_type, entity_id, actor, json.dumps(payload), created_at))

PHASE2_SCHEMA = """
CREATE TABLE IF NOT EXISTS goals (id TEXT PRIMARY KEY, company_id TEXT NOT NULL REFERENCES companies(id), title TEXT NOT NULL, status TEXT NOT NULL, priority REAL NOT NULL, owner TEXT NOT NULL, expected_outcome TEXT, actual_outcome TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS missions (id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id), title TEXT NOT NULL, status TEXT NOT NULL, owner_agent_id TEXT REFERENCES agents(id), created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS task_dependencies (task_id TEXT NOT NULL REFERENCES tasks(id), depends_on_task_id TEXT NOT NULL REFERENCES tasks(id), PRIMARY KEY(task_id, depends_on_task_id), CHECK(task_id != depends_on_task_id));
CREATE TABLE IF NOT EXISTS task_attempts (id TEXT PRIMARY KEY, task_id TEXT NOT NULL REFERENCES tasks(id), attempt_number INTEGER NOT NULL, outcome TEXT NOT NULL, error TEXT, created_at TEXT NOT NULL, UNIQUE(task_id, attempt_number));
CREATE TABLE IF NOT EXISTS decisions (id TEXT PRIMARY KEY, company_id TEXT NOT NULL REFERENCES companies(id), decision TEXT NOT NULL, alternatives TEXT NOT NULL, evidence TEXT NOT NULL, assumptions TEXT NOT NULL, confidence REAL NOT NULL, expected_outcome TEXT NOT NULL, actual_outcome TEXT, owner TEXT NOT NULL, follow_up TEXT, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS risks (id TEXT PRIMARY KEY, company_id TEXT NOT NULL REFERENCES companies(id), title TEXT NOT NULL, severity TEXT NOT NULL, status TEXT NOT NULL, mitigation TEXT, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS opportunities (id TEXT PRIMARY KEY, company_id TEXT NOT NULL REFERENCES companies(id), title TEXT NOT NULL, confidence REAL NOT NULL, status TEXT NOT NULL, rationale TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS experiments (id TEXT PRIMARY KEY, project_id TEXT REFERENCES projects(id), hypothesis TEXT NOT NULL, status TEXT NOT NULL, design TEXT NOT NULL, result TEXT, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS lessons (id TEXT PRIMARY KEY, company_id TEXT NOT NULL REFERENCES companies(id), lesson TEXT NOT NULL, source_failure_id TEXT, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS approvals (id TEXT PRIMARY KEY, company_id TEXT NOT NULL REFERENCES companies(id), action TEXT NOT NULL, risk_level TEXT NOT NULL, status TEXT NOT NULL, requested_by TEXT NOT NULL, context TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS agent_permissions (agent_id TEXT NOT NULL REFERENCES agents(id), permission TEXT NOT NULL, PRIMARY KEY(agent_id, permission));
CREATE TABLE IF NOT EXISTS agent_performance (id TEXT PRIMARY KEY, agent_id TEXT NOT NULL REFERENCES agents(id), metric TEXT NOT NULL, value REAL NOT NULL, recorded_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS studies (id TEXT PRIMARY KEY, source_id TEXT REFERENCES sources(id), title TEXT NOT NULL, design TEXT NOT NULL, population TEXT, findings TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS hypotheses (id TEXT PRIMARY KEY, project_id TEXT REFERENCES projects(id), statement TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS experiment_results (id TEXT PRIMARY KEY, experiment_id TEXT NOT NULL REFERENCES experiments(id), outcome TEXT NOT NULL, interpretation TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS study_participants (id TEXT PRIMARY KEY, study_id TEXT NOT NULL REFERENCES studies(id), external_ref TEXT NOT NULL, consent_status TEXT NOT NULL, created_at TEXT NOT NULL, UNIQUE(study_id,external_ref));
CREATE TABLE IF NOT EXISTS study_assignments (id TEXT PRIMARY KEY, study_id TEXT NOT NULL REFERENCES studies(id), participant_id TEXT NOT NULL REFERENCES study_participants(id), arm TEXT NOT NULL, assigned_at TEXT NOT NULL, method TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS study_sessions (id TEXT PRIMARY KEY, study_id TEXT NOT NULL REFERENCES studies(id), participant_id TEXT NOT NULL REFERENCES study_participants(id), phase TEXT NOT NULL, session_number INTEGER NOT NULL, occurred_at TEXT NOT NULL, status TEXT NOT NULL, UNIQUE(study_id,participant_id,phase,session_number));
CREATE TABLE IF NOT EXISTS study_outcomes (id TEXT PRIMARY KEY, study_id TEXT NOT NULL REFERENCES studies(id), participant_id TEXT NOT NULL REFERENCES study_participants(id), session_id TEXT REFERENCES study_sessions(id), outcome_name TEXT NOT NULL, value REAL, unit TEXT, missing_reason TEXT, recorded_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS study_adherence (id TEXT PRIMARY KEY, study_id TEXT NOT NULL REFERENCES studies(id), participant_id TEXT NOT NULL REFERENCES study_participants(id), session_id TEXT REFERENCES study_sessions(id), planned INTEGER NOT NULL, completed INTEGER NOT NULL, adherence_note TEXT, recorded_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS study_analysis_plans (id TEXT PRIMARY KEY, study_id TEXT NOT NULL REFERENCES studies(id), version INTEGER NOT NULL, analysis_spec TEXT NOT NULL, frozen INTEGER NOT NULL DEFAULT 0, frozen_at TEXT, created_at TEXT NOT NULL, UNIQUE(study_id,version));
CREATE TABLE IF NOT EXISTS study_analysis_results (id TEXT PRIMARY KEY, study_id TEXT NOT NULL REFERENCES studies(id), analysis_plan_id TEXT NOT NULL REFERENCES study_analysis_plans(id), outcome_name TEXT NOT NULL, n_total INTEGER NOT NULL, n_observed INTEGER NOT NULL, estimate REAL, uncertainty TEXT, missing_data_note TEXT, interpretation TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_goals_company_status ON goals(company_id, status);
CREATE INDEX IF NOT EXISTS idx_decisions_company_created ON decisions(company_id, created_at);
CREATE INDEX IF NOT EXISTS idx_audit_logs_created ON audit_logs(created_at);
"""
_PHASE2_COLUMNS = {
    "agents": {"responsibilities": "TEXT NOT NULL DEFAULT '[]'", "tools": "TEXT NOT NULL DEFAULT '[]'", "manager": "TEXT", "performance_history": "TEXT NOT NULL DEFAULT '[]'", "updated_at": "TEXT"},
    "projects": {"goal_id": "TEXT", "budget": "REAL", "updated_at": "TEXT"},
    "tasks": {"owner": "TEXT", "expected_outcome": "TEXT", "actual_outcome": "TEXT", "verification_method": "TEXT", "retry_limit": "INTEGER NOT NULL DEFAULT 0", "escalation_required": "INTEGER NOT NULL DEFAULT 0", "required_permissions": "TEXT NOT NULL DEFAULT '[]'"},
    "agent_runs": {"confidence": "REAL", "evidence_refs": "TEXT NOT NULL DEFAULT '[]'", "uncertainties": "TEXT NOT NULL DEFAULT '[]'", "cost_metadata": "TEXT NOT NULL DEFAULT '{}'", "error": "TEXT", "verified": "INTEGER NOT NULL DEFAULT 0"},
    "failures": {"contributing_factors": "TEXT NOT NULL DEFAULT '[]'", "corrective_action": "TEXT", "corrective_result": "TEXT", "owner": "TEXT"},
}
def _add_phase2_columns(con: sqlite3.Connection) -> None:
    for table, columns in _PHASE2_COLUMNS.items():
        existing = {row[1] for row in con.execute(f"PRAGMA table_info({table})")}
        for name, definition in columns.items():
            if name not in existing:
                con.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")
def _migrate_phase2(self: Database) -> None:
    with self.connect() as con:
        con.executescript(SCHEMA); _add_phase2_columns(con); con.executescript(PHASE2_SCHEMA)
Database.migrate = _migrate_phase2

PHASE3_SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_migrations (version TEXT PRIMARY KEY, applied_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS users (id TEXT PRIMARY KEY, external_subject TEXT NOT NULL UNIQUE, email TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS roles (id TEXT PRIMARY KEY, name TEXT NOT NULL UNIQUE, permissions TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS company_memberships (company_id TEXT NOT NULL REFERENCES companies(id), user_id TEXT NOT NULL REFERENCES users(id), role_id TEXT NOT NULL REFERENCES roles(id), status TEXT NOT NULL, created_at TEXT NOT NULL, PRIMARY KEY(company_id,user_id));
CREATE TABLE IF NOT EXISTS service_identities (id TEXT PRIMARY KEY, name TEXT NOT NULL UNIQUE, permissions TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS approval_events (id TEXT PRIMARY KEY, approval_id TEXT NOT NULL REFERENCES approvals(id), actor TEXT NOT NULL, action TEXT NOT NULL, payload TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS idempotency_keys (key TEXT PRIMARY KEY, actor TEXT NOT NULL, operation TEXT NOT NULL, response TEXT NOT NULL, created_at TEXT NOT NULL, expires_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS model_calls (id TEXT PRIMARY KEY, correlation_id TEXT NOT NULL, provider TEXT NOT NULL, model TEXT NOT NULL, purpose TEXT NOT NULL, input_metadata TEXT NOT NULL, output_metadata TEXT NOT NULL, input_tokens INTEGER, output_tokens INTEGER, estimated_cost REAL NOT NULL, latency_ms INTEGER NOT NULL, retry_count INTEGER NOT NULL, status TEXT NOT NULL, error TEXT, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS claim_revisions (id TEXT PRIMARY KEY, claim_id TEXT NOT NULL REFERENCES claims(id), prior_classification TEXT NOT NULL, prior_confidence REAL NOT NULL, new_classification TEXT NOT NULL, new_confidence REAL NOT NULL, reason TEXT NOT NULL, evidence_id TEXT REFERENCES evidence(id), review_required INTEGER NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS findings (id TEXT PRIMARY KEY, project_id TEXT REFERENCES projects(id), claim_id TEXT REFERENCES claims(id), category TEXT NOT NULL, title TEXT NOT NULL, change_type TEXT NOT NULL, confidence REAL NOT NULL, evidence_level TEXT, provenance TEXT NOT NULL, why_it_matters TEXT NOT NULL, recommended_action TEXT NOT NULL, review_required INTEGER NOT NULL, created_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_approvals_status ON approvals(status, created_at);
CREATE INDEX IF NOT EXISTS idx_model_calls_correlation ON model_calls(correlation_id, created_at);
CREATE INDEX IF NOT EXISTS idx_claim_revisions_claim ON claim_revisions(claim_id, created_at);
CREATE INDEX IF NOT EXISTS idx_findings_project_created ON findings(project_id, created_at);
CREATE TABLE IF NOT EXISTS evidence_sources (id TEXT PRIMARY KEY, source_id TEXT NOT NULL REFERENCES sources(id), state TEXT NOT NULL, content_hash TEXT, fetched_at TEXT, parsed_at TEXT, rejection_reason TEXT, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS evidence_reviews (id TEXT PRIMARY KEY, evidence_id TEXT NOT NULL REFERENCES evidence(id), reviewer TEXT NOT NULL, verdict TEXT NOT NULL, rationale TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS retry_events (id TEXT PRIMARY KEY, task_id TEXT REFERENCES tasks(id), attempt INTEGER NOT NULL, reason TEXT, action TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_retry_task ON retry_events(task_id, attempt);

"""
_PHASE3_COLUMNS = {
    "approvals": {"reason": "TEXT", "evidence": "TEXT NOT NULL DEFAULT '[]'", "expected_outcome": "TEXT", "expires_at": "TEXT", "approved_by": "TEXT", "resolved_at": "TEXT", "correlation_id": "TEXT"},
    "sources": {"state": "TEXT NOT NULL DEFAULT 'DISCOVERED'", "fetched_at": "TEXT", "parsed_at": "TEXT", "content_hash": "TEXT", "rejection_reason": "TEXT"},
    "claims": {"updated_at": "TEXT", "interpretation": "TEXT", "review_required": "INTEGER NOT NULL DEFAULT 0"},
}
def _migrate_phase3(self: Database) -> None:
    with self.connect() as con:
        con.executescript(SCHEMA); _add_phase2_columns(con); con.executescript(PHASE2_SCHEMA)
        for table, columns in _PHASE3_COLUMNS.items():
            existing = {row[1] for row in con.execute(f"PRAGMA table_info({table})")}
            for name, definition in columns.items():
                if name not in existing: con.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")
        con.executescript(PHASE3_SCHEMA)
Database.migrate = _migrate_phase3

class DatabaseConfigurationError(RuntimeError): pass

class PostgreSQLDatabase:
    """PostgreSQL adapter implementing the same repository API as SQLite."""
    def __init__(self, url: str):
        self.url = url
        try:
            import psycopg
        except ImportError as exc:
            raise DatabaseConfigurationError(
                "PostgreSQL support requires the optional psycopg dependency"
            ) from exc
        self._psycopg = psycopg

    @contextmanager
    def connect(self):
        with self._psycopg.connect(self.url) as con:
            yield con

    @staticmethod
    def _sql(sql: str) -> str:
        sql = sql.replace("?", "%s")
        if sql.lstrip().upper().startswith("INSERT OR IGNORE"):
            sql = sql.replace("INSERT OR IGNORE", "INSERT", 1).rstrip().rstrip(";") + " ON CONFLICT DO NOTHING"
        return sql

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> None:
        with self.connect() as con:
            con.execute(self._sql(sql), params)

    def one(self, sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
        with self.connect() as con:
            cur = con.execute(self._sql(sql), params)
            row = cur.fetchone()
            if row is None:
                return None
            return dict(zip([d.name for d in cur.description], row))

    def all(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        with self.connect() as con:
            cur = con.execute(self._sql(sql), params)
            names = [d.name for d in cur.description]
            return [dict(zip(names, row)) for row in cur.fetchall()]

    def audit(self, event_type: str, entity_type: str, entity_id: str, actor: str,
              payload: dict[str, Any], created_at: str, audit_id: str) -> None:
        self.execute(
            "INSERT INTO audit_logs VALUES (?, ?, ?, ?, ?, ?, ?)",
            (audit_id, event_type, entity_type, entity_id, actor, json.dumps(payload), created_at),
        )

    def migrate(self) -> None:
        statements = []
        for schema in (SCHEMA, PHASE2_SCHEMA, PHASE3_SCHEMA):
            statements.extend(
                statement.strip()
                for statement in schema.split(";")
                if statement.strip() and not statement.strip().startswith("PRAGMA")
            )
        with self.connect() as con:
            for statement in statements:
                con.execute(self._sql(statement))
            # Additive columns used by later phases.
            for table, columns in {**_PHASE2_COLUMNS, **_PHASE3_COLUMNS}.items():
                existing = {
                    row[0]
                    for row in con.execute(
                        "SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name=%s",
                        (table,),
                    ).fetchall()
                }
                for name, definition in columns.items():
                    if name not in existing:
                        con.execute(
                            f"ALTER TABLE {table} ADD COLUMN {name} {definition}"
                        )

def database_from_settings(settings: Any) -> Database | PostgreSQLDatabase:
    if settings.database_url:
        if not settings.database_url.startswith(("postgresql://", "postgres://")):
            raise DatabaseConfigurationError("DATABASE_URL must be a PostgreSQL URL")
        return PostgreSQLDatabase(settings.database_url)
    if settings.environment == "production":
        raise DatabaseConfigurationError("production database configuration is required")
    return Database(settings.database_path)
