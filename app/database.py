from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

SCHEMA = """CREATE TABLE IF NOT EXISTS companies (id TEXT PRIMARY KEY, name TEXT NOT NULL, mission TEXT NOT NULL, vision TEXT NOT NULL, core_principle TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS agents (id TEXT PRIMARY KEY, name TEXT NOT NULL, role TEXT NOT NULL, mission TEXT NOT NULL, capabilities TEXT NOT NULL, permissions TEXT NOT NULL, version TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS projects (id TEXT PRIMARY KEY, company_id TEXT NOT NULL REFERENCES companies(id), objective TEXT NOT NULL, status TEXT NOT NULL, owner_agent_id TEXT NOT NULL REFERENCES agents(id), created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS tasks (id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id), title TEXT NOT NULL, status TEXT NOT NULL, assigned_agent_id TEXT REFERENCES agents(id), priority REAL NOT NULL, success_criteria TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_tasks_project_status ON tasks(project_id, status);
CREATE TABLE IF NOT EXISTS sources (id TEXT PRIMARY KEY, title TEXT NOT NULL, url TEXT NOT NULL UNIQUE, authors TEXT, publication_year INTEGER, source_type TEXT NOT NULL, verified_at TEXT NOT NULL, provenance_note TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS claims (id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id), statement TEXT NOT NULL, classification TEXT NOT NULL, evidence_level TEXT NOT NULL DEFAULT 'UNVERIFIED', confidence REAL NOT NULL DEFAULT 0.0, status TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS evidence (id TEXT PRIMARY KEY, claim_id TEXT NOT NULL REFERENCES claims(id), source_id TEXT NOT NULL REFERENCES sources(id), stance TEXT NOT NULL, excerpt TEXT NOT NULL, verified INTEGER NOT NULL, created_by TEXT NOT NULL DEFAULT 'system', created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS knowledge_items (id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id), kind TEXT NOT NULL, content TEXT NOT NULL, provenance TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS research_questions (id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id), question TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS agent_runs (id TEXT PRIMARY KEY, agent_id TEXT NOT NULL REFERENCES agents(id), task_id TEXT REFERENCES tasks(id), status TEXT NOT NULL, input_payload TEXT NOT NULL, output_payload TEXT NOT NULL, started_at TEXT NOT NULL, completed_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS evaluations (id TEXT PRIMARY KEY, agent_run_id TEXT NOT NULL REFERENCES agent_runs(id), evaluator TEXT NOT NULL, passed INTEGER NOT NULL, score REAL NOT NULL, details TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS audit_logs (id TEXT PRIMARY KEY, event_type TEXT NOT NULL, entity_type TEXT NOT NULL, entity_id TEXT NOT NULL, actor TEXT NOT NULL, payload TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS maintenance_work (
 id TEXT PRIMARY KEY,
 kind TEXT NOT NULL,
 entity_type TEXT NOT NULL,
 entity_id TEXT NOT NULL,
 title TEXT NOT NULL,
 reason TEXT NOT NULL,
 success_criteria TEXT NOT NULL,
 status TEXT NOT NULL,
 approval_id TEXT,
 created_at TEXT NOT NULL,
 updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_maintenance_work_status ON maintenance_work(status);
CREATE INDEX IF NOT EXISTS idx_maintenance_work_entity ON maintenance_work(entity_type,entity_id,status);
CREATE TABLE IF NOT EXISTS knowledge_freshness (
 id TEXT PRIMARY KEY,
 entity_type TEXT NOT NULL,
 entity_id TEXT NOT NULL,
 review_interval_days INTEGER NOT NULL,
 last_validated_at TEXT NOT NULL,
 next_review_at TEXT NOT NULL,
 status TEXT NOT NULL,
 owner TEXT NOT NULL,
 created_at TEXT NOT NULL,
 updated_at TEXT NOT NULL,
 UNIQUE(entity_type,entity_id)
);
CREATE INDEX IF NOT EXISTS idx_knowledge_freshness_review ON knowledge_freshness(next_review_at,status);
CREATE TABLE IF NOT EXISTS improvement_proposals (id TEXT PRIMARY KEY, title TEXT NOT NULL, area TEXT NOT NULL, hypothesis TEXT NOT NULL, success_metric TEXT NOT NULL, status TEXT NOT NULL, owner TEXT NOT NULL, experiment_design TEXT, baseline_note TEXT, experiment_result TEXT, outcome_note TEXT, evidence_ref TEXT, adopted_by TEXT, adoption_rationale TEXT, retired_by TEXT, retirement_rationale TEXT, created_at TEXT NOT NULL, updated_at TEXT);
CREATE TABLE IF NOT EXISTS founder_briefs (id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id), content TEXT NOT NULL, action_required INTEGER NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS failures (id TEXT PRIMARY KEY, project_id TEXT REFERENCES projects(id), stage TEXT NOT NULL, expected_result TEXT NOT NULL, actual_result TEXT NOT NULL, root_cause TEXT NOT NULL, lesson TEXT NOT NULL, created_at TEXT NOT NULL);
"""


OPTIONAL_SCIENCE_SCHEMA = """
CREATE TABLE IF NOT EXISTS hds_experiments (id TEXT PRIMARY KEY, project_id TEXT NOT NULL, research_question TEXT NOT NULL, hypothesis TEXT NOT NULL, design TEXT NOT NULL, population TEXT NOT NULL, intervention TEXT NOT NULL, comparison TEXT NOT NULL, outcomes TEXT NOT NULL, analysis_plan TEXT NOT NULL, status TEXT NOT NULL, preregistered INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS hds_experiment_results (id TEXT PRIMARY KEY, experiment_id TEXT NOT NULL, outcome TEXT NOT NULL, interpretation TEXT NOT NULL, evidence_refs TEXT NOT NULL DEFAULT '[]', created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS research_workspaces (id TEXT PRIMARY KEY, project_id TEXT NOT NULL, question TEXT NOT NULL, scope TEXT NOT NULL, inclusion_rules TEXT NOT NULL, exclusion_rules TEXT NOT NULL, status TEXT NOT NULL, owner TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS research_syntheses (id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, synthesis TEXT NOT NULL, limitations TEXT NOT NULL, uncertainty TEXT NOT NULL, provenance_hash TEXT NOT NULL, evidence_refs TEXT NOT NULL DEFAULT '[]', status TEXT NOT NULL, created_by TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS research_skeptic_reviews (id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, synthesis_id TEXT, project_id TEXT NOT NULL, reviewer_agent_id TEXT, status TEXT NOT NULL, objections TEXT NOT NULL, missing_evidence TEXT NOT NULL, alternative_explanations TEXT NOT NULL, created_at TEXT NOT NULL, reviewed_at TEXT);
CREATE TABLE IF NOT EXISTS organizational_decisions (id TEXT PRIMARY KEY, project_id TEXT, decision_type TEXT NOT NULL, decision TEXT NOT NULL, evidence TEXT NOT NULL DEFAULT '[]', status TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS hds_research_queue (id TEXT PRIMARY KEY, project_id TEXT NOT NULL, question TEXT NOT NULL, rationale TEXT NOT NULL, trigger_type TEXT NOT NULL, priority TEXT NOT NULL, status TEXT NOT NULL, evidence_refs TEXT NOT NULL DEFAULT '[]', created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS experiment_safety_reviews (id TEXT PRIMARY KEY, experiment_id TEXT NOT NULL UNIQUE, reviewer TEXT NOT NULL, decision TEXT NOT NULL, rationale TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS knowledge_impact_reviews (id TEXT PRIMARY KEY, project_id TEXT NOT NULL, source_type TEXT NOT NULL, source_id TEXT NOT NULL, impact_type TEXT NOT NULL DEFAULT 'DEPENDENCY', affected_type TEXT NOT NULL, affected_id TEXT NOT NULL, reason TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS research_review_tasks (task_id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, synthesis_id TEXT NOT NULL, role TEXT NOT NULL, created_at TEXT NOT NULL, UNIQUE(workspace_id,synthesis_id,role));
CREATE TABLE IF NOT EXISTS company_memory (id TEXT PRIMARY KEY, project_id TEXT NOT NULL, memory_type TEXT NOT NULL, title TEXT NOT NULL, content TEXT NOT NULL, source_type TEXT NOT NULL, source_id TEXT, created_by TEXT NOT NULL, created_at TEXT NOT NULL);
"""
class Database:
    def __init__(self,path="company_os.db"):
        self.path=Path(path)
        self.migrate()
    @contextmanager
    def connect(self)->Iterator[sqlite3.Connection]:
        con=sqlite3.connect(self.path,timeout=10); con.row_factory=sqlite3.Row
        con.execute("PRAGMA foreign_keys=ON"); con.execute("PRAGMA journal_mode=WAL"); con.execute("PRAGMA busy_timeout=10000")
        try: yield con
        except BaseException: con.rollback(); raise
        else: con.commit()
        finally: con.close()
    @contextmanager
    def transaction(self)->Iterator[sqlite3.Connection]:
        con=sqlite3.connect(self.path,timeout=10); con.row_factory=sqlite3.Row
        con.execute("PRAGMA foreign_keys=ON"); con.execute("PRAGMA busy_timeout=10000")
        try:
            con.execute("BEGIN IMMEDIATE")
            yield con
        except BaseException:
            con.rollback(); raise
        else: con.commit()
        finally: con.close()
    def migrate(self):
        with self.connect() as con:
            con.executescript(SCHEMA)
            con.executescript(PHASE2_SCHEMA)
            con.executescript(PHASE3_SCHEMA)
            con.executescript(PHASE4_SCHEMA)
            con.executescript(PHASE5_SCHEMA)
            con.executescript(PHASE6_SCHEMA)
            con.executescript(PHASE7_SCHEMA)
            con.executescript(OPTIONAL_SCIENCE_SCHEMA)
            _add_phase2_columns(con)
            existing_impact={row[1] for row in con.execute("PRAGMA table_info(knowledge_impact_reviews)")}
            if "impact_type" not in existing_impact:
                con.execute("ALTER TABLE knowledge_impact_reviews ADD COLUMN impact_type TEXT NOT NULL DEFAULT 'DEPENDENCY'")
            existing_interventions={row[1] for row in con.execute("PRAGMA table_info(interventions)")}
            if "project_id" not in existing_interventions:
                con.execute("ALTER TABLE interventions ADD COLUMN project_id TEXT")
            for table,columns in _PHASE3_COLUMNS.items():
                for name,definition in columns.items():
                    existing={row[1] for row in con.execute(f"PRAGMA table_info({table})").fetchall()}
                    if name not in existing: con.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")
    def execute(self,sql,params=()):
        with self.connect() as con:
            cursor=con.execute(sql,params)
            return cursor
    def one(self,sql,params=()):
        with self.connect() as con: row=con.execute(sql,params).fetchone()
        return dict(row) if row else None
    def all(self,sql,params=()):
        with self.connect() as con: rows=con.execute(sql,params).fetchall()
        return [dict(row) for row in rows]
    def audit(self,event_type,entity_type,entity_id,actor,payload,created_at,audit_id):
        self.execute("INSERT INTO audit_logs VALUES (?, ?, ?, ?, ?, ?, ?)",(audit_id,event_type,entity_type,entity_id,actor,json.dumps(payload),created_at))
PHASE2_SCHEMA = """CREATE TABLE IF NOT EXISTS goals (id TEXT PRIMARY KEY, company_id TEXT NOT NULL REFERENCES companies(id), title TEXT NOT NULL, status TEXT NOT NULL, priority REAL NOT NULL, owner TEXT NOT NULL, expected_outcome TEXT, actual_outcome TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
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
CREATE TABLE IF NOT EXISTS study_outcomes (id TEXT PRIMARY KEY, study_id TEXT NOT NULL REFERENCES studies(id), participant_id TEXT NOT NULL REFERENCES study_participants(id), session_id TEXT REFERENCES study_sessions(id), outcome_name TEXT NOT NULL, value REAL, unit TEXT, missing_reason TEXT, observation_type TEXT NOT NULL DEFAULT 'TRAINING', recorded_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS study_adherence (id TEXT PRIMARY KEY, study_id TEXT NOT NULL REFERENCES studies(id), participant_id TEXT NOT NULL REFERENCES study_participants(id), session_id TEXT REFERENCES study_sessions(id), planned INTEGER NOT NULL, completed INTEGER NOT NULL, adherence_note TEXT, recorded_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS study_analysis_plans (id TEXT PRIMARY KEY, study_id TEXT NOT NULL REFERENCES studies(id), version INTEGER NOT NULL, analysis_spec TEXT NOT NULL, frozen INTEGER NOT NULL DEFAULT 0, frozen_at TEXT, created_at TEXT NOT NULL, UNIQUE(study_id,version));
CREATE TABLE IF NOT EXISTS study_analysis_results (id TEXT PRIMARY KEY, study_id TEXT NOT NULL REFERENCES studies(id), analysis_plan_id TEXT NOT NULL REFERENCES study_analysis_plans(id), outcome_name TEXT NOT NULL, n_total INTEGER NOT NULL, n_observed INTEGER NOT NULL, estimate REAL, uncertainty TEXT, missing_data_note TEXT, interpretation TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS study_analysis_metrics (id TEXT PRIMARY KEY, study_id TEXT NOT NULL REFERENCES studies(id), analysis_plan_id TEXT NOT NULL REFERENCES study_analysis_plans(id), outcome_name TEXT NOT NULL, metric_name TEXT NOT NULL, metric_value REAL, denominator INTEGER, note TEXT, created_at TEXT NOT NULL, UNIQUE(study_id,analysis_plan_id,outcome_name,metric_name));
CREATE TABLE IF NOT EXISTS study_analysis_audit (
 id TEXT PRIMARY KEY,
 study_id TEXT NOT NULL REFERENCES studies(id),
 analysis_plan_id TEXT NOT NULL REFERENCES study_analysis_plans(id),
 analysis_result_id TEXT REFERENCES study_analysis_results(id),
 protocol_hash TEXT NOT NULL,
 analysis_plan_hash TEXT NOT NULL,
 dataset_hash TEXT NOT NULL,
 method TEXT NOT NULL,
 population_note TEXT NOT NULL,
 created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_study_analysis_audit_study ON study_analysis_audit(study_id,created_at);

CREATE INDEX IF NOT EXISTS idx_goals_company_status ON goals(company_id,status);
CREATE INDEX IF NOT EXISTS idx_decisions_company_created ON decisions(company_id,created_at);
CREATE INDEX IF NOT EXISTS idx_audit_logs_created ON audit_logs(created_at);
"""
_PHASE2_COLUMNS={"agents":{"responsibilities":"TEXT NOT NULL DEFAULT '[]'","tools":"TEXT NOT NULL DEFAULT '[]'","manager":"TEXT","performance_history":"TEXT NOT NULL DEFAULT '[]'","updated_at":"TEXT"},"projects":{"goal_id":"TEXT","budget":"REAL","updated_at":"TEXT"},"tasks":{"owner":"TEXT","expected_outcome":"TEXT","actual_outcome":"TEXT","verification_method":"TEXT","retry_limit":"INTEGER NOT NULL DEFAULT 0","retry_count":"INTEGER NOT NULL DEFAULT 0","escalation_required":"INTEGER NOT NULL DEFAULT 0","required_permissions":"TEXT NOT NULL DEFAULT '[]'"},"agent_runs":{"confidence":"REAL","evidence_refs":"TEXT NOT NULL DEFAULT '[]'","uncertainties":"TEXT NOT NULL DEFAULT '[]'","cost_metadata":"TEXT NOT NULL DEFAULT '{}'","error":"TEXT","verified":"INTEGER NOT NULL DEFAULT 0"},"failures":{"contributing_factors":"TEXT NOT NULL DEFAULT '[]'","corrective_action":"TEXT","corrective_result":"TEXT","owner":"TEXT"}}
def _add_phase2_columns(con):
    for table,columns in _PHASE2_COLUMNS.items():
        existing={row[1] for row in con.execute(f"PRAGMA table_info({table})")}
        for name,definition in columns.items():
            if name not in existing: con.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")
def _migrate_phase2(self):
    with self.connect() as con: con.executescript(SCHEMA); _add_phase2_columns(con); con.executescript(PHASE2_SCHEMA)
Database.migrate=_migrate_phase2
_original_migrate_phase2=_migrate_phase2
def _migrate_all(self):
    _original_migrate_phase2(self)
    with self.connect() as con:
        con.executescript(PHASE_AGENT_OUTPUT_SCHEMA)
Database.migrate=_migrate_all
PHASE_AGENT_OUTPUT_SCHEMA = """CREATE TABLE IF NOT EXISTS agent_output_reviews (id TEXT PRIMARY KEY, agent_run_id TEXT NOT NULL REFERENCES agent_runs(id), project_id TEXT REFERENCES projects(id), task_id TEXT REFERENCES tasks(id), evidence_refs TEXT NOT NULL, provenance_hash TEXT NOT NULL, status TEXT NOT NULL, reviewer TEXT, rationale TEXT, created_at TEXT NOT NULL, reviewed_at TEXT);
"""

PHASE3_SCHEMA = """CREATE TABLE IF NOT EXISTS schema_migrations (version TEXT PRIMARY KEY, applied_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS users (id TEXT PRIMARY KEY, external_subject TEXT NOT NULL UNIQUE, email TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS roles (id TEXT PRIMARY KEY, name TEXT NOT NULL UNIQUE, permissions TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS company_memberships (company_id TEXT NOT NULL REFERENCES companies(id), user_id TEXT NOT NULL REFERENCES users(id), role_id TEXT NOT NULL REFERENCES roles(id), status TEXT NOT NULL, created_at TEXT NOT NULL, PRIMARY KEY(company_id,user_id));
CREATE TABLE IF NOT EXISTS service_identities (id TEXT PRIMARY KEY, name TEXT NOT NULL UNIQUE, permissions TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS approval_events (id TEXT PRIMARY KEY, approval_id TEXT NOT NULL REFERENCES approvals(id), actor TEXT NOT NULL, action TEXT NOT NULL, payload TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS idempotency_keys (key TEXT PRIMARY KEY, actor TEXT NOT NULL, operation TEXT NOT NULL, response TEXT NOT NULL, created_at TEXT NOT NULL, expires_at TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'COMPLETED', claim_token TEXT, lease_expires_at TEXT);
CREATE TABLE IF NOT EXISTS model_calls (id TEXT PRIMARY KEY, correlation_id TEXT NOT NULL, provider TEXT NOT NULL, model TEXT NOT NULL, purpose TEXT NOT NULL, input_metadata TEXT NOT NULL, output_metadata TEXT NOT NULL, input_tokens INTEGER, output_tokens INTEGER, estimated_cost REAL NOT NULL, latency_ms INTEGER NOT NULL, retry_count INTEGER NOT NULL, status TEXT NOT NULL, error TEXT, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS claim_state_transitions (id TEXT PRIMARY KEY, claim_id TEXT NOT NULL REFERENCES claims(id), prior_status TEXT NOT NULL, new_status TEXT NOT NULL, actor TEXT NOT NULL, rationale TEXT NOT NULL, evidence_id TEXT REFERENCES evidence(id), created_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_claim_state_transitions_claim ON claim_state_transitions(claim_id,created_at);
CREATE TABLE IF NOT EXISTS claim_revisions (id TEXT PRIMARY KEY, claim_id TEXT NOT NULL REFERENCES claims(id), prior_classification TEXT NOT NULL, prior_confidence REAL NOT NULL, new_classification TEXT NOT NULL, new_confidence REAL NOT NULL, reason TEXT NOT NULL, evidence_id TEXT REFERENCES evidence(id), review_required INTEGER NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS findings (id TEXT PRIMARY KEY, project_id TEXT REFERENCES projects(id), claim_id TEXT REFERENCES claims(id), category TEXT NOT NULL, title TEXT NOT NULL, change_type TEXT NOT NULL, confidence REAL NOT NULL, evidence_level TEXT, provenance TEXT NOT NULL, why_it_matters TEXT NOT NULL, recommended_action TEXT NOT NULL, review_required INTEGER NOT NULL, created_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_approvals_status ON approvals(status,created_at);
CREATE INDEX IF NOT EXISTS idx_model_calls_correlation ON model_calls(correlation_id,created_at);
CREATE INDEX IF NOT EXISTS idx_claim_revisions_claim ON claim_revisions(claim_id,created_at);
CREATE INDEX IF NOT EXISTS idx_findings_project_created ON findings(project_id,created_at);
CREATE TABLE IF NOT EXISTS evidence_sources (id TEXT PRIMARY KEY, source_id TEXT NOT NULL REFERENCES sources(id), state TEXT NOT NULL, content_hash TEXT, fetched_at TEXT, parsed_at TEXT, rejection_reason TEXT, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS evidence_reviews (id TEXT PRIMARY KEY, evidence_id TEXT NOT NULL REFERENCES evidence(id), reviewer TEXT NOT NULL, verdict TEXT NOT NULL, rationale TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS research_findings (
 id TEXT PRIMARY KEY,
 project_id TEXT NOT NULL REFERENCES projects(id),
 source_type TEXT NOT NULL,
 source_id TEXT,
 statement TEXT NOT NULL,
 classification TEXT NOT NULL,
 status TEXT NOT NULL,
 evidence_refs TEXT NOT NULL,
 interpretation TEXT,
 created_by TEXT NOT NULL,
 reviewed_by TEXT,
 created_at TEXT NOT NULL,
 reviewed_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_research_findings_project ON research_findings(project_id,created_at);
CREATE TABLE IF NOT EXISTS scientific_knowledge_versions (
 id TEXT PRIMARY KEY,
 claim_id TEXT NOT NULL REFERENCES claims(id),
 version INTEGER NOT NULL,
 statement TEXT NOT NULL,
 classification TEXT NOT NULL,
 status TEXT NOT NULL,
 confidence REAL NOT NULL,
 evidence_state TEXT NOT NULL,
 evidence_snapshot_hash TEXT NOT NULL,
 change_reason TEXT NOT NULL,
 created_at TEXT NOT NULL,
 UNIQUE(claim_id,version)
);
CREATE INDEX IF NOT EXISTS idx_knowledge_versions_claim ON scientific_knowledge_versions(claim_id,version);
CREATE TABLE IF NOT EXISTS retry_events (id TEXT PRIMARY KEY, task_id TEXT REFERENCES tasks(id), attempt INTEGER NOT NULL, reason TEXT, action TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_retry_task ON retry_events(task_id,attempt);
CREATE UNIQUE INDEX IF NOT EXISTS idx_evidence_review_reviewer ON evidence_reviews(evidence_id,reviewer);"""
PHASE5_SCHEMA = """CREATE TABLE IF NOT EXISTS study_protocol_versions (id TEXT PRIMARY KEY, study_id TEXT NOT NULL REFERENCES studies(id), version INTEGER NOT NULL, snapshot TEXT NOT NULL, content_hash TEXT NOT NULL, created_at TEXT NOT NULL, UNIQUE(study_id,version)); """
PHASE4_SCHEMA = """CREATE TABLE IF NOT EXISTS budgets (id TEXT PRIMARY KEY, company_id TEXT NOT NULL REFERENCES companies(id), limit_amount REAL NOT NULL CHECK(limit_amount >= 0), spent_amount REAL NOT NULL DEFAULT 0 CHECK(spent_amount >= 0), currency TEXT NOT NULL DEFAULT 'USD', period TEXT NOT NULL DEFAULT 'LIFETIME', status TEXT NOT NULL DEFAULT 'ACTIVE', created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS cost_events (id TEXT PRIMARY KEY, budget_id TEXT NOT NULL REFERENCES budgets(id), correlation_id TEXT NOT NULL UNIQUE, actor TEXT NOT NULL, provider TEXT NOT NULL, model TEXT NOT NULL, purpose TEXT NOT NULL, amount REAL NOT NULL CHECK(amount >= 0), currency TEXT NOT NULL, status TEXT NOT NULL, metadata TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_cost_events_budget_created ON cost_events(budget_id,created_at);
CREATE TABLE IF NOT EXISTS autonomy_iterations (id TEXT PRIMARY KEY, project_id TEXT REFERENCES projects(id), iteration_number INTEGER NOT NULL, status TEXT NOT NULL, action TEXT NOT NULL, outcome TEXT NOT NULL, failure_count INTEGER NOT NULL DEFAULT 0, escalated INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL);
"""

_PHASE3_COLUMNS={"evidence":{"created_by":"TEXT NOT NULL DEFAULT 'system'","excerpt_hash":"TEXT NOT NULL DEFAULT ''"},"idempotency_keys":{"status":"TEXT NOT NULL DEFAULT 'COMPLETED'","claim_token":"TEXT","lease_expires_at":"TEXT"},"approvals":{"reason":"TEXT","evidence":"TEXT NOT NULL DEFAULT '[]'","expected_outcome":"TEXT","expires_at":"TEXT","approved_by":"TEXT","resolved_at":"TEXT","correlation_id":"TEXT"},"sources":{"state":"TEXT NOT NULL DEFAULT 'DISCOVERED'","fetched_at":"TEXT","parsed_at":"TEXT","content_hash":"TEXT","rejection_reason":"TEXT"},"claims":{"updated_at":"TEXT","interpretation":"TEXT","review_required":"INTEGER NOT NULL DEFAULT 0"},"studies":{"status":"TEXT NOT NULL DEFAULT 'APPROVED'","protocol_snapshot":"TEXT","protocol_hash":"TEXT","approval_id":"TEXT"}}
def _migrate_phase3(self):
    with self.connect() as con:
        con.executescript(SCHEMA); con.executescript(PHASE2_SCHEMA); _add_phase2_columns(con)
        for table,columns in _PHASE3_COLUMNS.items():
            existing={row[1] for row in con.execute(f"PRAGMA table_info({table})")}
            for name,definition in columns.items():
                if name not in existing: con.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")
        con.executescript(PHASE3_SCHEMA)
def _migrate_phase4(self):
    with self.connect() as con:
        con.executescript(SCHEMA); con.executescript(PHASE2_SCHEMA); con.executescript(PHASE3_SCHEMA); _add_phase2_columns(con)
        for table,columns in _PHASE3_COLUMNS.items():
            existing={row[1] for row in con.execute(f"PRAGMA table_info({table})")}
            for name,definition in columns.items():
                if name not in existing: con.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")
        existing={row[1] for row in con.execute("PRAGMA table_info(study_outcomes)")}
        if "observation_type" not in existing:
            con.execute("ALTER TABLE study_outcomes ADD COLUMN observation_type TEXT NOT NULL DEFAULT 'TRAINING'")
        con.executescript(PHASE_AGENT_OUTPUT_SCHEMA); con.executescript(PHASE4_SCHEMA); con.executescript(PHASE5_SCHEMA); con.executescript(PHASE6_SCHEMA); con.executescript(PHASE7_SCHEMA); con.executescript(OPTIONAL_SCIENCE_SCHEMA)
        existing_decisions={row[1] for row in con.execute("PRAGMA table_info(organizational_decisions)")}
        if "evidence" not in existing_decisions: con.execute("ALTER TABLE organizational_decisions ADD COLUMN evidence TEXT NOT NULL DEFAULT '[]'")
        existing={row[1] for row in con.execute("PRAGMA table_info(training_protocols)")}
        for name,definition in {"source_claim_id":"TEXT REFERENCES claims(id)","intervention_id":"TEXT REFERENCES interventions(id)"}.items():
            if name not in existing: con.execute(f"ALTER TABLE training_protocols ADD COLUMN {name} {definition}")
        con.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_study_assignment_participant ON study_assignments(study_id,participant_id)")
        con.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_study_measure_binding ON study_measure_bindings(study_id,measure_id,observation_type,timepoint)")
        con.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_study_outcome_observation ON study_outcomes(study_id,participant_id,outcome_name,observation_type,session_id)")
Database.migrate=_migrate_phase4
class DatabaseConfigurationError(RuntimeError): pass
class PostgreSQLDatabase:
    def __init__(self,url):
        self.url=url
        try: import psycopg
        except ImportError as exc: raise DatabaseConfigurationError("PostgreSQL support requires the optional psycopg dependency") from exc
        self._psycopg=psycopg
    @contextmanager
    def connect(self):
        with self._psycopg.connect(self.url) as con: yield con
    @contextmanager
    def transaction(self):
        with self._psycopg.connect(self.url) as con:
            with con.transaction():
                yield con
    @staticmethod
    def _sql(sql):
        sql=sql.replace("?","%s")
        if sql.lstrip().upper().startswith("INSERT OR IGNORE"):
            sql=sql.replace("INSERT OR IGNORE","INSERT",1).rstrip().rstrip(";")+" ON CONFLICT DO NOTHING"
        return sql
    def execute(self,sql,params=()):
        with self.connect() as con: con.execute(self._sql(sql),params)
    def one(self,sql,params=None):
        with self.connect() as con:
            cur=con.execute(self._sql(sql),params or ()); row=cur.fetchone()
            return dict(zip([d.name for d in cur.description],row)) if row is not None else None
    def all(self,sql,params=None):
        with self.connect() as con:
            cur=con.execute(self._sql(sql),params or ()); names=[d.name for d in cur.description]
            return [dict(zip(names,row)) for row in cur.fetchall()]
    def audit(self,event_type,entity_type,entity_id,actor,payload,created_at,audit_id): self.execute("INSERT INTO audit_logs VALUES (?, ?, ?, ?, ?, ?, ?)",(audit_id,event_type,entity_type,entity_id,actor,json.dumps(payload),created_at))
    def migrate(self):
        statements=[]
        for schema in (SCHEMA,PHASE2_SCHEMA,PHASE3_SCHEMA,PHASE4_SCHEMA,PHASE5_SCHEMA,PHASE6_SCHEMA,PHASE7_SCHEMA): statements.extend(s.strip() for s in schema.split(";") if s.strip() and not s.strip().startswith("PRAGMA"))
        with self.connect() as con:
            for statement in statements: con.execute(self._sql(statement))
            for table,columns in {**_PHASE2_COLUMNS,**_PHASE3_COLUMNS,**{'study_outcomes':{'observation_type':"TEXT NOT NULL DEFAULT 'TRAINING'"},"idempotency_keys":{"status":"TEXT NOT NULL DEFAULT 'COMPLETED'","claim_token":"TEXT","lease_expires_at":"TEXT"}}}.items():
                existing={row[0] for row in con.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name=%s",(table,)).fetchall()}
                for name,definition in columns.items():
                    if name not in existing: con.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")
            con.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_study_outcome_observation ON study_outcomes(study_id,participant_id,outcome_name,observation_type,session_id)")
def database_from_settings(settings):
    if settings.database_url:
        if not settings.database_url.startswith(("postgresql://","postgres://")): raise DatabaseConfigurationError("DATABASE_URL must be a PostgreSQL URL")
        return PostgreSQLDatabase(settings.database_url)
    if settings.environment=="production": raise DatabaseConfigurationError("production database configuration is required")
    return Database(settings.database_path)

PHASE7_SCHEMA = """CREATE TABLE IF NOT EXISTS improvement_proposals (
 id TEXT PRIMARY KEY,
 title TEXT NOT NULL,
 area TEXT NOT NULL,
 hypothesis TEXT NOT NULL,
 success_metric TEXT NOT NULL,
 status TEXT NOT NULL,
 owner TEXT NOT NULL,
 experiment_design TEXT,
 baseline_note TEXT,
 experiment_result TEXT,
 outcome_note TEXT,
 evidence_ref TEXT,
 adopted_by TEXT,
 adoption_rationale TEXT,
 retired_by TEXT,
 retirement_rationale TEXT,
 created_at TEXT NOT NULL,
 updated_at TEXT
);"""

PHASE6_SCHEMA = """CREATE TABLE IF NOT EXISTS scientific_constructs (id TEXT PRIMARY KEY, project_id TEXT REFERENCES projects(id), name TEXT NOT NULL, definition TEXT NOT NULL, construct_type TEXT NOT NULL, status TEXT NOT NULL, version INTEGER NOT NULL, created_at TEXT NOT NULL, UNIQUE(project_id,name,version));
CREATE TABLE IF NOT EXISTS scientific_measures (id TEXT PRIMARY KEY, construct_id TEXT NOT NULL REFERENCES scientific_constructs(id), name TEXT NOT NULL, operational_definition TEXT NOT NULL, method TEXT NOT NULL, unit TEXT, reliability_note TEXT NOT NULL, validity_note TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS training_protocols (
 id TEXT PRIMARY KEY,
 project_id TEXT NOT NULL REFERENCES projects(id),
 name TEXT NOT NULL,
 target_construct_id TEXT REFERENCES scientific_constructs(id),
 source_claim_id TEXT REFERENCES claims(id),
 intervention_id TEXT REFERENCES interventions(id),
 mechanism_hypothesis TEXT NOT NULL,
 challenge_domain TEXT NOT NULL,
 dosage TEXT NOT NULL,
 progression_rule TEXT NOT NULL,
 transfer_target TEXT NOT NULL,
 retention_target TEXT NOT NULL,
 safety_constraints TEXT NOT NULL,
 evidence_level TEXT NOT NULL,
 status TEXT NOT NULL,
 version INTEGER NOT NULL,
 created_at TEXT NOT NULL,
 UNIQUE(project_id,name,version)
);
CREATE TABLE IF NOT EXISTS training_protocol_evidence (
 id TEXT PRIMARY KEY,
 protocol_id TEXT NOT NULL REFERENCES training_protocols(id),
 evidence_kind TEXT NOT NULL,
 evidence_ref TEXT NOT NULL,
 notes TEXT NOT NULL,
 created_at TEXT NOT NULL,
 UNIQUE(protocol_id,evidence_kind,evidence_ref)
);
CREATE TABLE IF NOT EXISTS training_sessions (
 id TEXT PRIMARY KEY,
 protocol_id TEXT NOT NULL REFERENCES training_protocols(id),
 participant_ref TEXT NOT NULL,
 session_number INTEGER NOT NULL,
 load_note TEXT NOT NULL,
 adherence INTEGER NOT NULL,
 task_success REAL,
 transfer_score REAL,
 retention_score REAL,
 decision_accuracy REAL,
 initiation_latency REAL,
 recovery_score REAL,
 fatigue_note TEXT,
 created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_training_sessions_protocol ON training_sessions(protocol_id,participant_ref,session_number);
CREATE TABLE IF NOT EXISTS interventions (id TEXT PRIMARY KEY, project_id TEXT, name TEXT NOT NULL UNIQUE, target_construct_id TEXT REFERENCES scientific_constructs(id), rationale TEXT NOT NULL, mechanism TEXT NOT NULL, evidence_level TEXT NOT NULL, dosage TEXT NOT NULL, population TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS intervention_evidence (id TEXT PRIMARY KEY, intervention_id TEXT NOT NULL REFERENCES interventions(id), evidence_kind TEXT NOT NULL, evidence_ref TEXT NOT NULL, notes TEXT NOT NULL, created_at TEXT NOT NULL, UNIQUE(intervention_id,evidence_kind,evidence_ref));
CREATE TABLE IF NOT EXISTS construct_versions (id TEXT PRIMARY KEY, construct_id TEXT NOT NULL REFERENCES scientific_constructs(id), version INTEGER NOT NULL, definition TEXT NOT NULL, operational_scope TEXT NOT NULL, change_reason TEXT NOT NULL, created_at TEXT NOT NULL, UNIQUE(construct_id,version));
CREATE TABLE IF NOT EXISTS study_measure_definitions (id TEXT PRIMARY KEY, study_id TEXT NOT NULL REFERENCES studies(id), name TEXT NOT NULL, construct_id TEXT REFERENCES scientific_constructs(id), operational_definition TEXT NOT NULL, method TEXT NOT NULL, scale_type TEXT NOT NULL, unit TEXT, reliability_note TEXT NOT NULL, validity_note TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL, UNIQUE(study_id,name));
CREATE TABLE IF NOT EXISTS study_measure_bindings (id TEXT PRIMARY KEY, study_id TEXT NOT NULL REFERENCES studies(id), measure_id TEXT NOT NULL REFERENCES study_measure_definitions(id), observation_type TEXT NOT NULL, timepoint TEXT NOT NULL, required INTEGER NOT NULL DEFAULT 1, UNIQUE(study_id,measure_id,observation_type,timepoint));"""
