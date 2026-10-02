from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator
from app.models import now

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
CREATE UNIQUE INDEX IF NOT EXISTS idx_maintenance_work_active_unique ON maintenance_work(kind,entity_type,entity_id) WHERE status IN ('PROPOSED','APPROVAL_PENDING','APPROVED','IN_PROGRESS');
CREATE TABLE IF NOT EXISTS code_change_proposals (
 id TEXT PRIMARY KEY,
 project_id TEXT NOT NULL REFERENCES projects(id),
 maintenance_work_id TEXT NOT NULL REFERENCES maintenance_work(id),
 title TEXT NOT NULL,
 patch_format TEXT NOT NULL,
 patch_payload TEXT NOT NULL,
 test_command TEXT NOT NULL,
 risk_level TEXT NOT NULL,
 status TEXT NOT NULL,
 proposed_by TEXT NOT NULL,
 approved_by TEXT,
 verification_run_id TEXT,
 rollback_payload TEXT,
 approval_id TEXT,
 created_at TEXT NOT NULL,
 updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_code_change_proposals_work ON code_change_proposals(maintenance_work_id,status);
CREATE TABLE IF NOT EXISTS code_change_execution_runs (
 id TEXT PRIMARY KEY,
 proposal_id TEXT NOT NULL REFERENCES code_change_proposals(id),
 run_type TEXT NOT NULL,
 project_id TEXT NOT NULL REFERENCES projects(id),
 proposal_fingerprint TEXT NOT NULL,
 status TEXT NOT NULL,
 actor TEXT NOT NULL,
 runner_mode TEXT NOT NULL,
 result_hash TEXT,
 return_code INTEGER,
 timed_out INTEGER NOT NULL DEFAULT 0,
 created_at TEXT NOT NULL,
 completed_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_code_change_execution_runs_proposal ON code_change_execution_runs(proposal_id,run_type,status);
CREATE TABLE IF NOT EXISTS code_change_verifications (
 id TEXT PRIMARY KEY,
 proposal_id TEXT NOT NULL REFERENCES code_change_proposals(id),
 verification_run_id TEXT NOT NULL UNIQUE,
 passed INTEGER NOT NULL,
 return_code INTEGER,
 timed_out INTEGER NOT NULL DEFAULT 0,
 output_digest TEXT NOT NULL,
 created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_code_change_verifications_proposal ON code_change_verifications(proposal_id,created_at);
CREATE TABLE IF NOT EXISTS maintenance_task_links (task_id TEXT PRIMARY KEY REFERENCES tasks(id), kind TEXT NOT NULL, entity_type TEXT NOT NULL, entity_id TEXT NOT NULL, created_at TEXT NOT NULL, UNIQUE(kind,entity_type,entity_id));
CREATE INDEX IF NOT EXISTS idx_maintenance_task_links_entity ON maintenance_task_links(entity_type,entity_id);
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


_HDS_LEGACY_COLUMNS = {"decisions": {"project_id": "TEXT"}, "studies": {"project_id": "TEXT"}, "hds_competition_participants": {"eligibility_status": "TEXT NOT NULL DEFAULT 'ELIGIBILITY_PENDING'", "supervision_status": "TEXT NOT NULL DEFAULT 'UNASSIGNED'", "medical_review_status": "TEXT NOT NULL DEFAULT 'NOT_REQUIRED'"}}

PROJECT_INDEX_SCHEMA = """CREATE INDEX IF NOT EXISTS idx_claims_project_created ON claims(project_id,created_at);
CREATE INDEX IF NOT EXISTS idx_studies_project_created ON studies(project_id,created_at);
CREATE INDEX IF NOT EXISTS idx_experiments_project_created ON experiments(project_id,created_at);
CREATE INDEX IF NOT EXISTS idx_hypotheses_project_created ON hypotheses(project_id,created_at);
CREATE INDEX IF NOT EXISTS idx_founder_briefs_project_created ON founder_briefs(project_id,created_at);
CREATE INDEX IF NOT EXISTS idx_failures_project_created ON failures(project_id,created_at);
CREATE INDEX IF NOT EXISTS idx_missions_project_created ON missions(project_id,created_at);
CREATE INDEX IF NOT EXISTS idx_autonomy_iterations_project_created ON autonomy_iterations(project_id,created_at);
CREATE INDEX IF NOT EXISTS idx_hds_experiments_project_created ON hds_experiments(project_id,created_at);
CREATE INDEX IF NOT EXISTS idx_research_workspaces_project_created ON research_workspaces(project_id,created_at);
CREATE INDEX IF NOT EXISTS idx_research_skeptic_reviews_project_created ON research_skeptic_reviews(project_id,created_at);
CREATE INDEX IF NOT EXISTS idx_organizational_decisions_project_created ON organizational_decisions(project_id,created_at);
CREATE INDEX IF NOT EXISTS idx_company_memory_project_created ON company_memory(project_id,created_at);
CREATE INDEX IF NOT EXISTS idx_agent_output_reviews_project_created ON agent_output_reviews(project_id,created_at);
CREATE INDEX IF NOT EXISTS idx_interventions_project_created ON interventions(project_id,created_at);
CREATE INDEX IF NOT EXISTS idx_training_protocols_project_created ON training_protocols(project_id,created_at);"""

HUMAN_DEVELOPMENT_SCHEMA = """
CREATE TABLE IF NOT EXISTS hds_constructs (
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id), domain_id TEXT NOT NULL,
 name TEXT NOT NULL, operational_definition TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'ACTIVE',
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS hds_assessment_measures (
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id), construct_id TEXT NOT NULL REFERENCES hds_constructs(id),
 name TEXT NOT NULL, unit TEXT NOT NULL, min_value REAL, max_value REAL, higher_is_better INTEGER NOT NULL DEFAULT 1,
 status TEXT NOT NULL DEFAULT 'DRAFT', created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS hds_assessment_sessions (
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id), participant_ref TEXT NOT NULL,
 timepoint TEXT NOT NULL, started_at TEXT NOT NULL, completed_at TEXT, status TEXT NOT NULL DEFAULT 'OPEN', created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS hds_assessment_observations (
 id TEXT PRIMARY KEY, session_id TEXT NOT NULL REFERENCES hds_assessment_sessions(id), measure_id TEXT NOT NULL REFERENCES hds_assessment_measures(id),
 value REAL NOT NULL, observed_at TEXT NOT NULL, note TEXT
);
CREATE INDEX IF NOT EXISTS idx_hds_constructs_project ON hds_constructs(project_id,status);
CREATE INDEX IF NOT EXISTS idx_hds_assessment_measures_project ON hds_assessment_measures(project_id,construct_id,status);
CREATE INDEX IF NOT EXISTS idx_hds_assessment_sessions_project ON hds_assessment_sessions(project_id,participant_ref,timepoint);
CREATE INDEX IF NOT EXISTS idx_hds_assessment_observations_session ON hds_assessment_observations(session_id,measure_id);

CREATE TABLE IF NOT EXISTS hds_programs (
 id TEXT PRIMARY KEY,
 project_id TEXT NOT NULL REFERENCES projects(id),
 name TEXT NOT NULL,
 objective TEXT NOT NULL,
 domain_id TEXT NOT NULL,
 status TEXT NOT NULL,
 created_at TEXT NOT NULL,
 updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_hds_programs_project ON hds_programs(project_id,status);
CREATE TABLE IF NOT EXISTS hds_challenges (
 id TEXT PRIMARY KEY,
 program_id TEXT NOT NULL REFERENCES hds_programs(id),
 name TEXT NOT NULL,
 description TEXT NOT NULL,
 challenge_type TEXT NOT NULL,
 difficulty INTEGER NOT NULL CHECK(difficulty BETWEEN 1 AND 10),
 safety_constraints TEXT NOT NULL,
 status TEXT NOT NULL,
 created_at TEXT NOT NULL,
 updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_hds_challenges_program ON hds_challenges(program_id,status);
CREATE TABLE IF NOT EXISTS hds_competitions (
 id TEXT PRIMARY KEY,
 project_id TEXT NOT NULL REFERENCES projects(id),
 name TEXT NOT NULL,
 format TEXT NOT NULL,
 status TEXT NOT NULL,
 created_at TEXT NOT NULL,
 updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_hds_competitions_project ON hds_competitions(project_id,status);
CREATE TABLE IF NOT EXISTS hds_competition_events (
 id TEXT PRIMARY KEY,
 competition_id TEXT NOT NULL REFERENCES hds_competitions(id),
 challenge_id TEXT NOT NULL REFERENCES hds_challenges(id),
 sequence INTEGER NOT NULL,
 scoring_rule TEXT NOT NULL,
 created_at TEXT NOT NULL,
 UNIQUE(competition_id,sequence)
);
CREATE TABLE IF NOT EXISTS hds_competition_participants (
 id TEXT PRIMARY KEY,
 competition_id TEXT NOT NULL REFERENCES hds_competitions(id),
 participant_ref TEXT NOT NULL,
 consent_status TEXT NOT NULL,
 eligibility_status TEXT NOT NULL DEFAULT 'ELIGIBILITY_PENDING',
 created_at TEXT NOT NULL,
 UNIQUE(competition_id,participant_ref)
);
CREATE TABLE IF NOT EXISTS hds_competition_scores (
 id TEXT PRIMARY KEY,
 event_id TEXT NOT NULL REFERENCES hds_competition_events(id),
 participant_id TEXT NOT NULL REFERENCES hds_competition_participants(id),
 metric TEXT NOT NULL,
 score REAL NOT NULL,
 observed_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_hds_scores_event_participant ON hds_competition_scores(event_id,participant_id);
CREATE TABLE IF NOT EXISTS hds_organizations (
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
 name TEXT NOT NULL, organization_type TEXT NOT NULL, status TEXT NOT NULL,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS hds_customers (
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
 external_ref TEXT NOT NULL, customer_type TEXT NOT NULL, status TEXT NOT NULL,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 UNIQUE(project_id,external_ref)
);
CREATE TABLE IF NOT EXISTS hds_products (
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
 name TEXT NOT NULL, product_type TEXT NOT NULL, description TEXT NOT NULL,
 status TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS hds_program_enrollments (
 id TEXT PRIMARY KEY, program_id TEXT NOT NULL REFERENCES hds_programs(id),
 customer_id TEXT NOT NULL REFERENCES hds_customers(id),
 status TEXT NOT NULL, started_at TEXT NOT NULL, ended_at TEXT
);
CREATE TABLE IF NOT EXISTS hds_coaches (
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
 external_ref TEXT NOT NULL, role TEXT NOT NULL, status TEXT NOT NULL,
 created_at TEXT NOT NULL,
 UNIQUE(project_id,external_ref)
);
CREATE TABLE IF NOT EXISTS hds_subscriptions (
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
 customer_id TEXT NOT NULL REFERENCES hds_customers(id),
 product_id TEXT NOT NULL REFERENCES hds_products(id),
 status TEXT NOT NULL, started_at TEXT NOT NULL, ended_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_hds_org_project ON hds_organizations(project_id,status);
CREATE INDEX IF NOT EXISTS idx_hds_customer_project ON hds_customers(project_id,status);
CREATE INDEX IF NOT EXISTS idx_hds_product_project ON hds_products(project_id,status);
CREATE INDEX IF NOT EXISTS idx_hds_enrollment_program ON hds_program_enrollments(program_id,status);
CREATE INDEX IF NOT EXISTS idx_hds_coach_project ON hds_coaches(project_id,status);
CREATE INDEX IF NOT EXISTS idx_hds_subscription_customer ON hds_subscriptions(customer_id,status);
CREATE TABLE IF NOT EXISTS hds_safety_controls (
 id TEXT PRIMARY KEY,
 project_id TEXT NOT NULL REFERENCES projects(id),
 challenge_id TEXT NOT NULL REFERENCES hds_challenges(id),
 risk_class TEXT NOT NULL,
 eligibility_required INTEGER NOT NULL DEFAULT 1,
 consent_required INTEGER NOT NULL DEFAULT 1,
 supervision_required INTEGER NOT NULL DEFAULT 1,
 medical_review_required INTEGER NOT NULL DEFAULT 0,
 stop_criteria TEXT NOT NULL,
 status TEXT NOT NULL,
 created_at TEXT NOT NULL,
 updated_at TEXT NOT NULL,
 UNIQUE(challenge_id)
);
CREATE TABLE IF NOT EXISTS hds_challenge_executions (
 id TEXT PRIMARY KEY,
 project_id TEXT NOT NULL REFERENCES projects(id),
 challenge_id TEXT NOT NULL REFERENCES hds_challenges(id),
 participant_id TEXT NOT NULL REFERENCES hds_competition_participants(id),
 status TEXT NOT NULL,
 started_at TEXT NOT NULL,
 stopped_at TEXT,
 stop_reason TEXT,
 created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_hds_challenge_exec_project ON hds_challenge_executions(project_id,challenge_id,participant_id,status);
CREATE TABLE IF NOT EXISTS hds_safety_incidents (
 id TEXT PRIMARY KEY,
 project_id TEXT NOT NULL REFERENCES projects(id),
 challenge_id TEXT REFERENCES hds_challenges(id),
 execution_id TEXT REFERENCES hds_challenge_executions(id),
 participant_id TEXT REFERENCES hds_competition_participants(id),
 severity TEXT NOT NULL,
 description TEXT NOT NULL,
 immediate_action TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'OPEN',
 reported_by TEXT NOT NULL,
 reviewed_by TEXT,
 review_note TEXT,
 created_at TEXT NOT NULL,
 updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_hds_safety_incidents_project ON hds_safety_incidents(project_id,status,created_at);
CREATE TABLE IF NOT EXISTS hds_training_adjustments (
 id TEXT PRIMARY KEY,
 project_id TEXT NOT NULL REFERENCES projects(id),
 protocol_id TEXT NOT NULL REFERENCES training_protocols(id),
 participant_ref TEXT NOT NULL,
 previous_difficulty REAL,
 new_difficulty REAL NOT NULL,
 rationale TEXT NOT NULL,
 evidence_basis TEXT NOT NULL,
 created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_hds_training_adjustments_project ON hds_training_adjustments(project_id,protocol_id,participant_ref,created_at);
CREATE TABLE IF NOT EXISTS hds_safety_reviews (
 id TEXT PRIMARY KEY,
 project_id TEXT NOT NULL REFERENCES projects(id),
 challenge_id TEXT NOT NULL REFERENCES hds_challenges(id),
 reviewer TEXT NOT NULL,
 decision TEXT NOT NULL,
 rationale TEXT NOT NULL,
 created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_hds_safety_project ON hds_safety_controls(project_id,status);
CREATE INDEX IF NOT EXISTS idx_hds_safety_reviews_challenge ON hds_safety_reviews(challenge_id,created_at);
CREATE TABLE IF NOT EXISTS hds_competition_study_bindings (
 id TEXT PRIMARY KEY, competition_id TEXT NOT NULL REFERENCES hds_competitions(id),
 participant_id TEXT NOT NULL REFERENCES hds_competition_participants(id),
 study_participant_id TEXT NOT NULL REFERENCES study_participants(id),
 UNIQUE(competition_id,participant_id), UNIQUE(study_participant_id)
);
CREATE TABLE IF NOT EXISTS hds_competition_measure_bindings (
 id TEXT PRIMARY KEY, event_id TEXT NOT NULL REFERENCES hds_competition_events(id),
 study_id TEXT NOT NULL REFERENCES studies(id),
 measure_id TEXT NOT NULL REFERENCES study_measure_definitions(id),
 observation_type TEXT NOT NULL, timepoint TEXT NOT NULL,
 UNIQUE(event_id,study_id,measure_id,observation_type,timepoint)
);
"""
OPTIONAL_SCIENCE_SCHEMA = """
CREATE TABLE IF NOT EXISTS hds_experiments (id TEXT PRIMARY KEY, project_id TEXT NOT NULL, research_question TEXT NOT NULL, hypothesis TEXT NOT NULL, design TEXT NOT NULL, population TEXT NOT NULL, intervention TEXT NOT NULL, comparison TEXT NOT NULL, outcomes TEXT NOT NULL, analysis_plan TEXT NOT NULL, status TEXT NOT NULL, preregistered INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS hds_experiment_results (id TEXT PRIMARY KEY, experiment_id TEXT NOT NULL, outcome TEXT NOT NULL, interpretation TEXT NOT NULL, evidence_refs TEXT NOT NULL DEFAULT '[]', created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS research_workspaces (id TEXT PRIMARY KEY, project_id TEXT NOT NULL, question TEXT NOT NULL, scope TEXT NOT NULL, inclusion_rules TEXT NOT NULL, exclusion_rules TEXT NOT NULL, status TEXT NOT NULL, owner TEXT NOT NULL, research_queue_id TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS research_syntheses (id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, synthesis TEXT NOT NULL, limitations TEXT NOT NULL, uncertainty TEXT NOT NULL, provenance_hash TEXT NOT NULL, evidence_refs TEXT NOT NULL DEFAULT '[]', status TEXT NOT NULL, created_by TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS research_skeptic_reviews (id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, synthesis_id TEXT, project_id TEXT NOT NULL, reviewer_agent_id TEXT, status TEXT NOT NULL, objections TEXT NOT NULL, missing_evidence TEXT NOT NULL, alternative_explanations TEXT NOT NULL, created_at TEXT NOT NULL, reviewed_at TEXT);
CREATE TABLE IF NOT EXISTS organizational_decisions (id TEXT PRIMARY KEY, project_id TEXT, decision_type TEXT NOT NULL, decision TEXT NOT NULL, evidence TEXT NOT NULL DEFAULT '[]', status TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS hds_research_queue (id TEXT PRIMARY KEY, project_id TEXT NOT NULL, research_queue_workspace_id TEXT, question TEXT NOT NULL, rationale TEXT NOT NULL, trigger_type TEXT NOT NULL, priority TEXT NOT NULL, status TEXT NOT NULL, evidence_refs TEXT NOT NULL DEFAULT '[]', created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS experiment_safety_reviews (id TEXT PRIMARY KEY, experiment_id TEXT NOT NULL UNIQUE, reviewer TEXT NOT NULL, decision TEXT NOT NULL, rationale TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS knowledge_impact_reviews (id TEXT PRIMARY KEY, project_id TEXT NOT NULL, source_type TEXT NOT NULL, source_id TEXT NOT NULL, impact_type TEXT NOT NULL DEFAULT 'DEPENDENCY', affected_type TEXT NOT NULL, affected_id TEXT NOT NULL, reason TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE UNIQUE INDEX IF NOT EXISTS idx_knowledge_impact_proposed_identity ON knowledge_impact_reviews(project_id,source_type,source_id,impact_type,affected_type,affected_id) WHERE status='PROPOSED';
CREATE TABLE IF NOT EXISTS research_review_tasks (task_id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, synthesis_id TEXT NOT NULL, role TEXT NOT NULL, created_at TEXT NOT NULL, UNIQUE(workspace_id,synthesis_id,role));
CREATE TABLE IF NOT EXISTS company_memory (id TEXT PRIMARY KEY, project_id TEXT NOT NULL, memory_type TEXT NOT NULL, title TEXT NOT NULL, content TEXT NOT NULL, source_type TEXT NOT NULL, source_id TEXT, created_by TEXT NOT NULL, created_at TEXT NOT NULL);
"""

def _ensure_hds_indexes(con):
    con.execute("CREATE INDEX IF NOT EXISTS idx_hds_programs_project ON hds_programs(project_id,status)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_hds_challenges_program ON hds_challenges(program_id,status)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_hds_competitions_project ON hds_competitions(project_id,status)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_hds_scores_event_participant ON hds_competition_scores(event_id,participant_id)")

def _ensure_hds_schema(con):
    con.execute("CREATE TABLE IF NOT EXISTS hds_constructs (id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id), domain_id TEXT NOT NULL, name TEXT NOT NULL, operational_definition TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'ACTIVE', created_at TEXT NOT NULL, updated_at TEXT NOT NULL)")
    con.execute("CREATE TABLE IF NOT EXISTS hds_assessment_measures (id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id), construct_id TEXT NOT NULL REFERENCES hds_constructs(id), name TEXT NOT NULL, unit TEXT NOT NULL, min_value REAL, max_value REAL, higher_is_better INTEGER NOT NULL DEFAULT 1, status TEXT NOT NULL DEFAULT 'DRAFT', created_at TEXT NOT NULL, updated_at TEXT NOT NULL)")
    con.execute("CREATE TABLE IF NOT EXISTS hds_assessment_sessions (id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id), participant_ref TEXT NOT NULL, timepoint TEXT NOT NULL, started_at TEXT NOT NULL, completed_at TEXT, status TEXT NOT NULL DEFAULT 'OPEN', created_at TEXT NOT NULL)")
    con.execute("CREATE TABLE IF NOT EXISTS hds_assessment_observations (id TEXT PRIMARY KEY, session_id TEXT NOT NULL REFERENCES hds_assessment_sessions(id), measure_id TEXT NOT NULL REFERENCES hds_assessment_measures(id), value REAL NOT NULL, observed_at TEXT NOT NULL, note TEXT)")

    # Keep HDS product tables explicit at the migration boundary so they cannot
    # disappear because of schema ordering or a legacy migration path.
    con.execute("""CREATE TABLE IF NOT EXISTS hds_programs (
        id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
        name TEXT NOT NULL, objective TEXT NOT NULL, domain_id TEXT NOT NULL,
        status TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
    )""")
    con.execute("""CREATE TABLE IF NOT EXISTS hds_challenges (
        id TEXT PRIMARY KEY, program_id TEXT NOT NULL REFERENCES hds_programs(id),
        name TEXT NOT NULL, description TEXT NOT NULL, challenge_type TEXT NOT NULL,
        difficulty INTEGER NOT NULL CHECK(difficulty BETWEEN 1 AND 10),
        safety_constraints TEXT NOT NULL, status TEXT NOT NULL,
        created_at TEXT NOT NULL, updated_at TEXT NOT NULL
    )""")
    con.execute("""CREATE TABLE IF NOT EXISTS hds_competitions (
        id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
        name TEXT NOT NULL, format TEXT NOT NULL, status TEXT NOT NULL,
        created_at TEXT NOT NULL, updated_at TEXT NOT NULL
    )""")
    con.execute("""CREATE TABLE IF NOT EXISTS hds_competition_events (
        id TEXT PRIMARY KEY, competition_id TEXT NOT NULL REFERENCES hds_competitions(id),
        challenge_id TEXT NOT NULL REFERENCES hds_challenges(id),
        sequence INTEGER NOT NULL, scoring_rule TEXT NOT NULL, created_at TEXT NOT NULL,
        UNIQUE(competition_id,sequence)
    )""")
    con.execute("""CREATE TABLE IF NOT EXISTS hds_competition_participants (
        id TEXT PRIMARY KEY, competition_id TEXT NOT NULL REFERENCES hds_competitions(id),
        participant_ref TEXT NOT NULL, consent_status TEXT NOT NULL, eligibility_status TEXT NOT NULL DEFAULT "ELIGIBILITY_PENDING", created_at TEXT NOT NULL,
        UNIQUE(competition_id,participant_ref)
    )""")
    con.execute("""CREATE TABLE IF NOT EXISTS hds_competition_scores (
        id TEXT PRIMARY KEY, event_id TEXT NOT NULL REFERENCES hds_competition_events(id),
        participant_id TEXT NOT NULL REFERENCES hds_competition_participants(id),
        metric TEXT NOT NULL, score REAL NOT NULL, observed_at TEXT NOT NULL
    )""")
    con.execute("""CREATE TABLE IF NOT EXISTS hds_competition_study_bindings (
        id TEXT PRIMARY KEY, competition_id TEXT NOT NULL REFERENCES hds_competitions(id),
        participant_id TEXT NOT NULL REFERENCES hds_competition_participants(id),
        study_participant_id TEXT NOT NULL REFERENCES study_participants(id),
        UNIQUE(competition_id,participant_id), UNIQUE(study_participant_id)
    )""")
    con.execute("""CREATE TABLE IF NOT EXISTS hds_competition_measure_bindings (
        id TEXT PRIMARY KEY, event_id TEXT NOT NULL REFERENCES hds_competition_events(id),
        study_id TEXT NOT NULL REFERENCES studies(id),
        measure_id TEXT NOT NULL REFERENCES study_measure_definitions(id),
        observation_type TEXT NOT NULL, timepoint TEXT NOT NULL,
        UNIQUE(event_id,study_id,measure_id,observation_type,timepoint)
    )""")
    con.execute("""CREATE TABLE IF NOT EXISTS hds_organizations (
        id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
        name TEXT NOT NULL, organization_type TEXT NOT NULL, status TEXT NOT NULL,
        created_at TEXT NOT NULL, updated_at TEXT NOT NULL
    )""")
    con.execute("""CREATE TABLE IF NOT EXISTS hds_customers (
        id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
        external_ref TEXT NOT NULL, customer_type TEXT NOT NULL, status TEXT NOT NULL,
        created_at TEXT NOT NULL, updated_at TEXT NOT NULL, UNIQUE(project_id,external_ref)
    )""")
    con.execute("""CREATE TABLE IF NOT EXISTS hds_products (
        id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
        name TEXT NOT NULL, product_type TEXT NOT NULL, description TEXT NOT NULL,
        status TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
    )""")
    con.execute("""CREATE TABLE IF NOT EXISTS hds_program_enrollments (
        id TEXT PRIMARY KEY, program_id TEXT NOT NULL REFERENCES hds_programs(id),
        customer_id TEXT NOT NULL REFERENCES hds_customers(id), status TEXT NOT NULL,
        started_at TEXT NOT NULL, ended_at TEXT
    )""")
    con.execute("""CREATE TABLE IF NOT EXISTS hds_coaches (
        id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
        external_ref TEXT NOT NULL, role TEXT NOT NULL, status TEXT NOT NULL,
        created_at TEXT NOT NULL, UNIQUE(project_id,external_ref)
    )""")
    con.execute("""CREATE TABLE IF NOT EXISTS hds_subscriptions (
        id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
        customer_id TEXT NOT NULL REFERENCES hds_customers(id),
        product_id TEXT NOT NULL REFERENCES hds_products(id), status TEXT NOT NULL,
        started_at TEXT NOT NULL, ended_at TEXT
    )""")
    for name,definition in {
        "eligibility_status":"TEXT NOT NULL DEFAULT 'ELIGIBILITY_PENDING'",
        "supervision_status":"TEXT NOT NULL DEFAULT 'UNASSIGNED'",
        "medical_review_status":"TEXT NOT NULL DEFAULT 'NOT_REQUIRED'",
    }.items():
        existing={row[1] for row in con.execute("PRAGMA table_info(hds_competition_participants)").fetchall()}
        if name not in existing:
            con.execute(f"ALTER TABLE hds_competition_participants ADD COLUMN {name} {definition}")
    con.execute("""CREATE TABLE IF NOT EXISTS hds_safety_controls (
        id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
        challenge_id TEXT NOT NULL REFERENCES hds_challenges(id), risk_class TEXT NOT NULL,
        eligibility_required INTEGER NOT NULL DEFAULT 1, consent_required INTEGER NOT NULL DEFAULT 1,
        supervision_required INTEGER NOT NULL DEFAULT 1, medical_review_required INTEGER NOT NULL DEFAULT 0,
        stop_criteria TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
        UNIQUE(challenge_id)
    )""")
    con.execute("""CREATE TABLE IF NOT EXISTS research_loop_runs (
        id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
        gap TEXT NOT NULL, workspace_id TEXT, synthesis_id TEXT, finding_id TEXT,
        claim_id TEXT, status TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
    )""")
    con.execute("""CREATE TABLE IF NOT EXISTS hds_challenge_executions (
        id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
        challenge_id TEXT NOT NULL REFERENCES hds_challenges(id),
        participant_id TEXT NOT NULL REFERENCES hds_competition_participants(id),
        status TEXT NOT NULL, started_at TEXT NOT NULL, stopped_at TEXT,
        stop_reason TEXT, created_at TEXT NOT NULL
    )""")
    con.execute("""CREATE TABLE IF NOT EXISTS hds_safety_incidents (
        id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
        challenge_id TEXT REFERENCES hds_challenges(id),
        execution_id TEXT REFERENCES hds_challenge_executions(id),
        participant_id TEXT REFERENCES hds_competition_participants(id),
        severity TEXT NOT NULL, description TEXT NOT NULL, immediate_action TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'OPEN', reported_by TEXT NOT NULL, reviewed_by TEXT,
        review_note TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
    )""")
    con.execute("CREATE INDEX IF NOT EXISTS idx_hds_safety_incidents_project ON hds_safety_incidents(project_id,status,created_at)")
    con.execute("""CREATE TABLE IF NOT EXISTS hds_training_adjustments (
        id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
        protocol_id TEXT NOT NULL REFERENCES training_protocols(id),
        participant_ref TEXT NOT NULL, previous_difficulty REAL,
        new_difficulty REAL NOT NULL, rationale TEXT NOT NULL,
        evidence_basis TEXT NOT NULL, created_at TEXT NOT NULL
    )""")
    con.execute("""CREATE TABLE IF NOT EXISTS hds_safety_reviews (
        id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
        challenge_id TEXT NOT NULL REFERENCES hds_challenges(id), reviewer TEXT NOT NULL,
        decision TEXT NOT NULL, rationale TEXT NOT NULL, created_at TEXT NOT NULL
    )""")

def _ensure_runtime_identities(con):
    """Keep the root identities available on every runtime DB connection."""
    has_agents=con.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='agents'"
    ).fetchone()
    if not has_agents:
        return
    con.execute(
        "INSERT OR IGNORE INTO agents(id,name,role,mission,capabilities,permissions,version,status,created_at) VALUES (?,?,?,?,?,?,?,?,?)",
        ("ceo","CEO","strategy","board","[]","[]","1","ACTIVE",now()),
    )
    con.execute(
        "INSERT OR IGNORE INTO agents(id,name,role,mission,capabilities,permissions,version,status,created_at) VALUES (?,?,?,?,?,?,?,?,?)",
        ("researcher","Researcher","research","research","[]","[]","1","ACTIVE",now()),
    )


class Database:
    def __init__(self,path="company_os.db"):
        self.path=Path(path)
        self.migrate()
    @contextmanager
    def connect(self)->Iterator[sqlite3.Connection]:
        con=sqlite3.connect(self.path,timeout=10); con.row_factory=sqlite3.Row
        con.execute("PRAGMA foreign_keys=ON"); con.execute("PRAGMA journal_mode=WAL"); con.execute("PRAGMA busy_timeout=10000")
        _ensure_runtime_identities(con)
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
            # HDS is a built-in company boundary used by the orchestrator and
            # project-scoped scientific services. Keep its root company/agent
            # identities present so foreign-key enforcement remains meaningful.
            con.execute("INSERT OR IGNORE INTO companies(id,name,mission,vision,core_principle,created_at) VALUES (?,?,?,?,?,?)",
                        ("hds","Human Development Science","Scientific human development","Evidence-governed human development","Truth and scientific integrity above all else",now()))
            from app.registry import all_agents
            for agent in all_agents():
                con.execute(
                    "INSERT OR IGNORE INTO agents(id,name,role,mission,capabilities,permissions,version,status,created_at,manager) VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (agent.id,agent.name,agent.role,agent.role,"[]","[]","1","ACTIVE",now(),agent.manager),
                )
            # Re-assert the two root identities after every schema/migration step.
            # This is intentionally idempotent: test databases and upgraded installations
            # must always be able to satisfy the project foreign keys.
            con.execute(
                "INSERT OR IGNORE INTO companies(id,name,mission,vision,core_principle,created_at) VALUES (?,?,?,?,?,?)",
                ("hds","Human Development Science","Scientific human development",
                 "Evidence-governed human development","Truth and scientific integrity above all else",now()),
            )
            con.execute(
                "INSERT OR IGNORE INTO agents(id,name,role,mission,capabilities,permissions,version,status,created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                ("ceo","CEO","strategy","board","[]","[]","1","ACTIVE",now()),
            )
            _ensure_hds_schema(con)
            _ensure_hds_indexes(con)
            for name,definition in {
                "eligibility_status":"TEXT NOT NULL DEFAULT 'ELIGIBILITY_PENDING'",
                "supervision_status":"TEXT NOT NULL DEFAULT 'UNASSIGNED'",
                "medical_review_status":"TEXT NOT NULL DEFAULT 'NOT_REQUIRED'",
            }.items():
                existing={row[1] for row in con.execute("PRAGMA table_info(hds_competition_participants)").fetchall()}
                if name not in existing:
                    con.execute(f"ALTER TABLE hds_competition_participants ADD COLUMN {name} {definition}")
            _add_phase2_columns(con)
            # Seed built-in agents again after all legacy columns are present.
            # Use the stable nine-column core first, then set manager separately so
            # fresh databases and older upgraded schemas both receive the identities.
            from app.registry import all_agents
            for agent in all_agents():
                con.execute(
                    "INSERT OR IGNORE INTO agents(id,name,role,mission,capabilities,permissions,version,status,created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                    (agent.id,agent.name,agent.role,agent.role,"[]","[]","1","ACTIVE",now()),
                )
                if "manager" in {row[1] for row in con.execute("PRAGMA table_info(agents)").fetchall()}:
                    con.execute("UPDATE agents SET manager=? WHERE id=?", (agent.manager,agent.id))
            # Explicit root-agent fallback: these two identities are foreign-key
            # anchors used by legacy and scientific test/install paths.
            for agent_id,agent_name,agent_role in (("ceo","CEO","strategy"),("researcher","Researcher","research")):
                con.execute(
                    "INSERT OR IGNORE INTO agents(id,name,role,mission,capabilities,permissions,version,status,created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                    (agent_id,agent_name,agent_role,agent_role,"[]","[]","1","ACTIVE",now()),
                )
            existing_impact={row[1] for row in con.execute("PRAGMA table_info(knowledge_impact_reviews)")}
            if "impact_type" not in existing_impact:
                con.execute("ALTER TABLE knowledge_impact_reviews ADD COLUMN impact_type TEXT NOT NULL DEFAULT 'DEPENDENCY'")
            existing_interventions={row[1] for row in con.execute("PRAGMA table_info(interventions)")}
            if "project_id" not in existing_interventions:
                con.execute("ALTER TABLE interventions ADD COLUMN project_id TEXT")
            for table,columns in _HDS_LEGACY_COLUMNS.items():
                for name,definition in columns.items():
                    existing={row[1] for row in con.execute(f"PRAGMA table_info({table})").fetchall()}
                    if name not in existing:
                        con.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")
            for table,columns in _PHASE3_COLUMNS.items():
                for name,definition in columns.items():
                    existing={row[1] for row in con.execute(f"PRAGMA table_info({table})").fetchall()}
                    if name not in existing: con.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")
    def execute(self,sql,params=()):
        with self.connect() as con:
            cursor=con.execute(sql,params)
            return cursor
    def table_columns(self,table):
        if not str(table).replace("_","").isalnum(): raise ValueError("invalid table name")
        return [row["name"] for row in self.all(f"PRAGMA table_info({table})")]

    def table_names(self):
        return [row["name"] for row in self.all("SELECT name FROM sqlite_master WHERE type='table'")]

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
CREATE TABLE IF NOT EXISTS studies (id TEXT PRIMARY KEY, source_id TEXT REFERENCES sources(id), project_id TEXT REFERENCES projects(id), title TEXT NOT NULL, design TEXT NOT NULL, population TEXT, findings TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS hypotheses (id TEXT PRIMARY KEY, project_id TEXT REFERENCES projects(id), statement TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS experiment_results (id TEXT PRIMARY KEY, experiment_id TEXT NOT NULL REFERENCES experiments(id), outcome TEXT NOT NULL, interpretation TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS study_participants (id TEXT PRIMARY KEY, study_id TEXT NOT NULL REFERENCES studies(id), external_ref TEXT NOT NULL, consent_status TEXT NOT NULL, created_at TEXT NOT NULL, UNIQUE(study_id,external_ref));
CREATE TABLE IF NOT EXISTS study_assignments (id TEXT PRIMARY KEY, study_id TEXT NOT NULL REFERENCES studies(id), participant_id TEXT NOT NULL REFERENCES study_participants(id), arm TEXT NOT NULL, assigned_at TEXT NOT NULL, method TEXT NOT NULL, UNIQUE(study_id,participant_id));
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
CREATE UNIQUE INDEX IF NOT EXISTS idx_study_analysis_audit_result ON study_analysis_audit(analysis_result_id) WHERE analysis_result_id IS NOT NULL;
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
CREATE TRIGGER IF NOT EXISTS trg_scientific_knowledge_version_immutable
BEFORE UPDATE ON scientific_knowledge_versions
BEGIN
 SELECT RAISE(ABORT,'scientific knowledge version is immutable');
END;
CREATE TRIGGER IF NOT EXISTS trg_scientific_knowledge_version_delete_guard
BEFORE DELETE ON scientific_knowledge_versions
BEGIN
 SELECT RAISE(ABORT,'scientific knowledge version is immutable');
END;

CREATE INDEX IF NOT EXISTS idx_knowledge_versions_claim ON scientific_knowledge_versions(claim_id,version);
CREATE TABLE IF NOT EXISTS retry_events (id TEXT PRIMARY KEY, task_id TEXT REFERENCES tasks(id), attempt INTEGER NOT NULL, reason TEXT, action TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_retry_task ON retry_events(task_id,attempt);
CREATE TABLE IF NOT EXISTS evidence_reviews (id TEXT PRIMARY KEY, evidence_id TEXT NOT NULL REFERENCES evidence(id), reviewer TEXT NOT NULL, verdict TEXT NOT NULL, rationale TEXT NOT NULL, created_at TEXT NOT NULL, UNIQUE(evidence_id,reviewer));
CREATE UNIQUE INDEX IF NOT EXISTS idx_evidence_review_reviewer ON evidence_reviews(evidence_id,reviewer);
CREATE UNIQUE INDEX IF NOT EXISTS idx_study_assignment_participant ON study_assignments(study_id,participant_id);"""
PHASE5_SCHEMA = """CREATE TABLE IF NOT EXISTS study_protocol_versions (id TEXT PRIMARY KEY, study_id TEXT NOT NULL REFERENCES studies(id), version INTEGER NOT NULL, snapshot TEXT NOT NULL, content_hash TEXT NOT NULL, created_at TEXT NOT NULL, UNIQUE(study_id,version)); """
PHASE_AGENT_OUTPUT_SCHEMA = """CREATE TABLE IF NOT EXISTS agent_output_reviews (id TEXT PRIMARY KEY, agent_run_id TEXT NOT NULL REFERENCES agent_runs(id), project_id TEXT REFERENCES projects(id), task_id TEXT REFERENCES tasks(id), evidence_refs TEXT NOT NULL, provenance_hash TEXT NOT NULL, status TEXT NOT NULL, reviewer TEXT, rationale TEXT, created_at TEXT NOT NULL, reviewed_at TEXT);
CREATE UNIQUE INDEX IF NOT EXISTS idx_agent_output_reviews_run ON agent_output_reviews(agent_run_id);
"""

PHASE3_SCHEMA = """CREATE TABLE IF NOT EXISTS schema_migrations (version TEXT PRIMARY KEY, applied_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS users (id TEXT PRIMARY KEY, external_subject TEXT NOT NULL UNIQUE, email TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS roles (id TEXT PRIMARY KEY, name TEXT NOT NULL UNIQUE, permissions TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS company_memberships (company_id TEXT NOT NULL REFERENCES companies(id), user_id TEXT NOT NULL REFERENCES users(id), role_id TEXT NOT NULL REFERENCES roles(id), status TEXT NOT NULL, created_at TEXT NOT NULL, PRIMARY KEY(company_id,user_id));
CREATE TABLE IF NOT EXISTS project_memberships (project_id TEXT NOT NULL REFERENCES projects(id), user_id TEXT NOT NULL REFERENCES users(id), role_id TEXT NOT NULL REFERENCES roles(id), status TEXT NOT NULL DEFAULT 'ACTIVE', created_at TEXT NOT NULL, PRIMARY KEY(project_id,user_id));
CREATE INDEX IF NOT EXISTS idx_project_memberships_user ON project_memberships(user_id,status);
CREATE TABLE IF NOT EXISTS service_identities (id TEXT PRIMARY KEY, name TEXT NOT NULL UNIQUE, permissions TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS approval_events (id TEXT PRIMARY KEY, approval_id TEXT NOT NULL REFERENCES approvals(id), actor TEXT NOT NULL, action TEXT NOT NULL, payload TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS idempotency_keys (key TEXT PRIMARY KEY, actor TEXT NOT NULL, operation TEXT NOT NULL, response TEXT NOT NULL, created_at TEXT NOT NULL, expires_at TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'COMPLETED', claim_token TEXT, lease_expires_at TEXT);
CREATE TABLE IF NOT EXISTS model_calls (id TEXT PRIMARY KEY, correlation_id TEXT NOT NULL, provider TEXT NOT NULL, model TEXT NOT NULL, purpose TEXT NOT NULL, input_metadata TEXT NOT NULL, output_metadata TEXT NOT NULL, input_tokens INTEGER, output_tokens INTEGER, estimated_cost REAL NOT NULL, latency_ms INTEGER NOT NULL, retry_count INTEGER NOT NULL, status TEXT NOT NULL, error TEXT, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS claim_state_transitions (id TEXT PRIMARY KEY, claim_id TEXT NOT NULL REFERENCES claims(id), prior_status TEXT NOT NULL, new_status TEXT NOT NULL, actor TEXT NOT NULL, rationale TEXT NOT NULL, evidence_id TEXT REFERENCES evidence(id), created_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_claim_state_transitions_claim ON claim_state_transitions(claim_id,created_at);
CREATE TABLE IF NOT EXISTS claim_revisions (id TEXT PRIMARY KEY, claim_id TEXT NOT NULL REFERENCES claims(id), prior_classification TEXT NOT NULL, prior_confidence REAL NOT NULL, new_classification TEXT NOT NULL, new_confidence REAL NOT NULL, reason TEXT NOT NULL, evidence_id TEXT REFERENCES evidence(id), review_required INTEGER NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS findings (id TEXT PRIMARY KEY, project_id TEXT REFERENCES projects(id), claim_id TEXT REFERENCES claims(id), category TEXT NOT NULL, title TEXT NOT NULL, change_type TEXT NOT NULL, confidence REAL NOT NULL, evidence_level TEXT, provenance TEXT NOT NULL, why_it_matters TEXT NOT NULL, recommended_action TEXT NOT NULL, review_required INTEGER NOT NULL, created_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_approvals_status ON approvals(status,created_at);
CREATE UNIQUE INDEX IF NOT EXISTS idx_approval_events_consumed_once ON approval_events(approval_id) WHERE action='CONSUMED';
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
CREATE UNIQUE INDEX IF NOT EXISTS idx_evidence_review_reviewer ON evidence_reviews(evidence_id,reviewer);
CREATE UNIQUE INDEX IF NOT EXISTS idx_study_assignment_participant ON study_assignments(study_id,participant_id);"""
PHASE4_SCHEMA = """CREATE TABLE IF NOT EXISTS budgets (id TEXT PRIMARY KEY, company_id TEXT NOT NULL REFERENCES companies(id), limit_amount REAL NOT NULL CHECK(limit_amount >= 0), spent_amount REAL NOT NULL DEFAULT 0 CHECK(spent_amount >= 0), currency TEXT NOT NULL DEFAULT 'USD', period TEXT NOT NULL DEFAULT 'LIFETIME', status TEXT NOT NULL DEFAULT 'ACTIVE', created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS cost_events (id TEXT PRIMARY KEY, budget_id TEXT NOT NULL REFERENCES budgets(id), correlation_id TEXT NOT NULL UNIQUE, actor TEXT NOT NULL, provider TEXT NOT NULL, model TEXT NOT NULL, purpose TEXT NOT NULL, amount REAL NOT NULL CHECK(amount >= 0), currency TEXT NOT NULL, status TEXT NOT NULL, metadata TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_cost_events_budget_created ON cost_events(budget_id,created_at);
CREATE TABLE IF NOT EXISTS autonomy_iterations (id TEXT PRIMARY KEY, project_id TEXT REFERENCES projects(id), iteration_number INTEGER NOT NULL, status TEXT NOT NULL, action TEXT NOT NULL, outcome TEXT NOT NULL, failure_count INTEGER NOT NULL DEFAULT 0, escalated INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL);
"""

_PHASE3_COLUMNS={"evidence":{"created_by":"TEXT NOT NULL DEFAULT 'system'","excerpt_hash":"TEXT NOT NULL DEFAULT ''"},"claim_revisions":{"source_finding_id":"TEXT","previous_statement":"TEXT NOT NULL DEFAULT ''","new_statement":"TEXT NOT NULL DEFAULT ''","previous_status":"TEXT NOT NULL DEFAULT 'PROPOSED'","new_status":"TEXT NOT NULL DEFAULT 'PROPOSED'","rationale":"TEXT NOT NULL DEFAULT ''","evidence_refs":"TEXT NOT NULL DEFAULT '[]'","revised_by":"TEXT NOT NULL DEFAULT 'system'","status":"TEXT NOT NULL DEFAULT 'PROPOSED'","prior_classification":"TEXT NOT NULL DEFAULT ''","prior_confidence":"REAL NOT NULL DEFAULT 0","new_classification":"TEXT NOT NULL DEFAULT ''","new_confidence":"REAL NOT NULL DEFAULT 0","reason":"TEXT NOT NULL DEFAULT ''","evidence_id":"TEXT","review_required":"INTEGER NOT NULL DEFAULT 1"},"idempotency_keys":{"status":"TEXT NOT NULL DEFAULT 'COMPLETED'","claim_token":"TEXT","lease_expires_at":"TEXT"},"approvals":{"reason":"TEXT","evidence":"TEXT NOT NULL DEFAULT '[]'","expected_outcome":"TEXT","expires_at":"TEXT","approved_by":"TEXT","resolved_at":"TEXT","correlation_id":"TEXT"},"sources":{"state":"TEXT NOT NULL DEFAULT 'DISCOVERED'","fetched_at":"TEXT","parsed_at":"TEXT","content_hash":"TEXT","rejection_reason":"TEXT"},"evidence_sources":{"content":"TEXT"},"claims":{"updated_at":"TEXT","interpretation":"TEXT","review_required":"INTEGER NOT NULL DEFAULT 0"},"studies":{"status":"TEXT NOT NULL DEFAULT 'APPROVED'","protocol_snapshot":"TEXT","protocol_hash":"TEXT","approval_id":"TEXT","project_id":"TEXT"}}
_PHASE2_COLUMNS={"agents":{"responsibilities":"TEXT NOT NULL DEFAULT '[]'","tools":"TEXT NOT NULL DEFAULT '[]'","manager":"TEXT","performance_history":"TEXT NOT NULL DEFAULT '[]'","updated_at":"TEXT"},"projects":{"goal_id":"TEXT","budget":"REAL","updated_at":"TEXT"},"tasks":{"owner":"TEXT","expected_outcome":"TEXT","actual_outcome":"TEXT","verification_method":"TEXT","retry_limit":"INTEGER NOT NULL DEFAULT 0","retry_count":"INTEGER NOT NULL DEFAULT 0","escalation_required":"INTEGER NOT NULL DEFAULT 0","required_permissions":"TEXT NOT NULL DEFAULT '[]'"},"agent_runs":{"confidence":"REAL","evidence_refs":"TEXT NOT NULL DEFAULT '[]'","uncertainties":"TEXT NOT NULL DEFAULT '[]'","cost_metadata":"TEXT NOT NULL DEFAULT '{}'","error":"TEXT","verified":"INTEGER NOT NULL DEFAULT 0"},"failures":{"contributing_factors":"TEXT NOT NULL DEFAULT '[]'","corrective_action":"TEXT","corrective_result":"TEXT","owner":"TEXT"}}

def _add_phase2_columns(con):
    for table,columns in _PHASE2_COLUMNS.items():
        existing={row[1] for row in con.execute(f"PRAGMA table_info({table})")}
        for name,definition in columns.items():
            if name not in existing:
                con.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")

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
        if "timepoint" not in existing:
            con.execute("ALTER TABLE study_outcomes ADD COLUMN timepoint TEXT")
        duplicate_outcomes=con.execute("""
            SELECT study_id,participant_id,outcome_name,observation_type,COALESCE(session_id,''),timepoint,COUNT(*) AS n
            FROM study_outcomes
            WHERE timepoint IS NOT NULL
            GROUP BY study_id,participant_id,outcome_name,observation_type,COALESCE(session_id,''),timepoint
            HAVING COUNT(*) > 1
        """).fetchall()
        if duplicate_outcomes:
            raise RuntimeError("cannot enforce unique study outcome observations: existing duplicate observations found")
        con.execute("DROP INDEX IF EXISTS idx_study_outcome_observation_identity")
        con.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_study_outcome_observation_identity ON study_outcomes(study_id,participant_id,outcome_name,observation_type,COALESCE(session_id,''),timepoint) WHERE timepoint IS NOT NULL")
        con.executescript(PHASE_AGENT_OUTPUT_SCHEMA); con.executescript(PHASE4_SCHEMA); con.executescript(PHASE5_SCHEMA); con.executescript(PHASE6_SCHEMA); con.executescript(PHASE7_SCHEMA); con.executescript(OPTIONAL_SCIENCE_SCHEMA)
        existing_code_change={row[1] for row in con.execute("PRAGMA table_info(code_change_proposals)")}
        if "approval_id" not in existing_code_change:
            con.execute("ALTER TABLE code_change_proposals ADD COLUMN approval_id TEXT")
        existing_research_workspace={row[1] for row in con.execute("PRAGMA table_info(research_workspaces)")}
        if "research_queue_id" not in existing_research_workspace:
            con.execute("ALTER TABLE research_workspaces ADD COLUMN research_queue_id TEXT")
        existing_research_queue={row[1] for row in con.execute("PRAGMA table_info(hds_research_queue)")}
        if "research_queue_workspace_id" not in existing_research_queue:
            con.execute("ALTER TABLE hds_research_queue ADD COLUMN research_queue_workspace_id TEXT")
        _ensure_hds_schema(con)
        _ensure_hds_indexes(con)
        con.executescript(_PHASE4_ANALYSIS_IMMUTABILITY_SQL)
        existing_studies={row[1] for row in con.execute("PRAGMA table_info(studies)")}
        if "project_id" not in existing_studies:
            con.execute("ALTER TABLE studies ADD COLUMN project_id TEXT")
        # Legacy databases may have created decisions before project scoping was introduced.
        for table,columns in _HDS_LEGACY_COLUMNS.items():
            existing={row[1] for row in con.execute(f"PRAGMA table_info({table})").fetchall()}
            for name,definition in columns.items():
                if name not in existing:
                    con.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")
        existing_decisions={row[1] for row in con.execute("PRAGMA table_info(organizational_decisions)")}
        if "evidence" not in existing_decisions: con.execute("ALTER TABLE organizational_decisions ADD COLUMN evidence TEXT NOT NULL DEFAULT '[]'")
        existing={row[1] for row in con.execute("PRAGMA table_info(training_protocols)")}
        for name,definition in {"source_claim_id":"TEXT REFERENCES claims(id)","intervention_id":"TEXT REFERENCES interventions(id)"}.items():
            if name not in existing: con.execute(f"ALTER TABLE training_protocols ADD COLUMN {name} {definition}")
        duplicate_assignments=con.execute("""
            SELECT study_id,participant_id,COUNT(*) AS n
            FROM study_assignments
            GROUP BY study_id,participant_id
            HAVING COUNT(*) > 1
        """).fetchall()
        if duplicate_assignments:
            raise RuntimeError("cannot enforce unique study assignments: existing duplicate participant assignments found")
        con.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_study_assignment_participant ON study_assignments(study_id,participant_id)")
        duplicate_sessions=con.execute("""
            SELECT study_id,participant_id,phase,session_number,COUNT(*) AS n
            FROM study_sessions
            GROUP BY study_id,participant_id,phase,session_number
            HAVING COUNT(*) > 1
        """).fetchall()
        if duplicate_sessions:
            raise RuntimeError("cannot enforce unique study sessions: existing duplicate sessions found")
        con.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_study_session_identity ON study_sessions(study_id,participant_id,phase,session_number)")
        con.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_study_measure_binding ON study_measure_bindings(study_id,measure_id,observation_type,timepoint)")
        duplicate_evidence=con.execute("""
            SELECT claim_id,source_id,stance,excerpt_hash,COUNT(*) AS n
            FROM evidence
            GROUP BY claim_id,source_id,stance,excerpt_hash
            HAVING COUNT(*) > 1
        """).fetchall()
        if duplicate_evidence:
            raise RuntimeError("cannot enforce unique evidence attachments: existing duplicate claim/source/stance/excerpt records found")
        con.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_evidence_attachment_identity ON evidence(claim_id,source_id,stance,excerpt_hash)")
        duplicate_evidence_sources=con.execute("""
            SELECT source_id,content_hash,COUNT(*) AS n
            FROM evidence_sources
            WHERE content_hash IS NOT NULL
            GROUP BY source_id,content_hash
            HAVING COUNT(*) > 1
        """).fetchall()
        if duplicate_evidence_sources:
            raise RuntimeError("cannot enforce unique parsed source content: existing duplicate source/content hashes found")
        con.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_evidence_source_content_identity ON evidence_sources(source_id,content_hash)")
        duplicate_training_sessions=con.execute("""
            SELECT protocol_id,participant_ref,session_number,COUNT(*) AS n
            FROM training_sessions
            GROUP BY protocol_id,participant_ref,session_number
            HAVING COUNT(*) > 1
        """).fetchall()
        if duplicate_training_sessions:
            raise RuntimeError("cannot enforce unique training sessions: existing duplicate protocol/participant/session records found")
        con.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_training_session_identity ON training_sessions(protocol_id,participant_ref,session_number)")
        duplicate_queue=con.execute("""
            SELECT project_id,question,COUNT(*) AS n FROM hds_research_queue
            WHERE status IN ('PROPOSED','APPROVED','IN_PROGRESS')
            GROUP BY project_id,question HAVING COUNT(*) > 1
        """).fetchall()
        if duplicate_queue:
            raise RuntimeError("cannot enforce unique active research queue items: existing duplicate project/question items found")
        con.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_research_queue_active_identity ON hds_research_queue(project_id,question) WHERE status IN ('PROPOSED','APPROVED','IN_PROGRESS')")

        duplicate_maintenance=con.execute("""
            SELECT kind,entity_type,entity_id,COUNT(*) AS n
            FROM maintenance_work
            WHERE status IN ('PROPOSED','APPROVAL_PENDING','APPROVED','IN_PROGRESS')
            GROUP BY kind,entity_type,entity_id HAVING COUNT(*) > 1
        """).fetchall()
        if duplicate_maintenance:
            raise RuntimeError("cannot enforce unique active maintenance work: existing duplicate active items found")
        con.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_maintenance_active_identity ON maintenance_work(kind,entity_type,entity_id) WHERE status IN ('PROPOSED','APPROVAL_PENDING','APPROVED','IN_PROGRESS')")

        duplicate_agent_reviews=con.execute("""
            SELECT agent_run_id,COUNT(*) AS n FROM agent_output_reviews
            GROUP BY agent_run_id HAVING COUNT(*) > 1
        """).fetchall()
        if duplicate_agent_reviews:
            raise RuntimeError("cannot enforce unique agent output reviews: existing duplicate agent runs found")
        con.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_agent_output_review_run ON agent_output_reviews(agent_run_id)")
        con.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_study_outcome_observation ON study_outcomes(study_id,participant_id,outcome_name,observation_type,session_id)")
        con.execute("DROP INDEX IF EXISTS idx_study_outcome_observation_no_session")
Database.migrate=_migrate_phase4
class DatabaseConfigurationError(RuntimeError): pass
class PostgreSQLDatabase:
    def __init__(self,url):
        self.url=url
        try:
            import psycopg
            from psycopg.rows import dict_row
        except ImportError as exc:
            raise DatabaseConfigurationError("PostgreSQL support requires the optional psycopg dependency") from exc
        self._psycopg=psycopg
        self._row_factory=dict_row
    @contextmanager
    def connect(self):
        with self._psycopg.connect(self.url, row_factory=self._row_factory) as con:
            yield con
    @contextmanager
    def transaction(self):
        with self._psycopg.connect(self.url, row_factory=self._row_factory) as con:
            with con.transaction():
                yield con
    @staticmethod
    def _sql(sql):
        sql=sql.replace("?","%s")
        if sql.lstrip().upper().startswith("INSERT OR IGNORE"):
            sql=sql.replace("INSERT OR IGNORE","INSERT",1).rstrip().rstrip(";")+" ON CONFLICT DO NOTHING"
        return sql
    def execute(self,sql,params=()):
        with self.connect() as con:
            cursor=con.execute(self._sql(sql),params)
            return cursor
    def table_columns(self,table):
        if not str(table).replace("_","").isalnum(): raise ValueError("invalid table name")
        rows=self.all("SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name=?",(table,))
        return [row["column_name"] for row in rows]

    def table_names(self):
        return [row["table_name"] for row in self.all("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")]

    def one(self,sql,params=None):
        with self.connect() as con:
            row=con.execute(self._sql(sql),params or ()).fetchone()
            return dict(row) if row is not None else None
    def all(self,sql,params=None):
        with self.connect() as con:
            return [dict(row) for row in con.execute(self._sql(sql),params or ()).fetchall()]
    def audit(self,event_type,entity_type,entity_id,actor,payload,created_at,audit_id): self.execute("INSERT INTO audit_logs VALUES (?, ?, ?, ?, ?, ?, ?)",(audit_id,event_type,entity_type,entity_id,actor,json.dumps(payload),created_at))
    def migrate(self):
        statements=[]
        for schema in (SCHEMA,PHASE2_SCHEMA,PHASE3_SCHEMA,PHASE_AGENT_OUTPUT_SCHEMA,PHASE4_SCHEMA,PHASE5_SCHEMA,PHASE6_SCHEMA,PHASE7_SCHEMA,OPTIONAL_SCIENCE_SCHEMA,HUMAN_DEVELOPMENT_SCHEMA):
            in_trigger=False
            for raw in schema.split(";"):
                statement=raw.strip()
                if not statement or statement.startswith("PRAGMA"): continue
                upper=statement.upper()
                if upper.startswith("CREATE TRIGGER"):
                    in_trigger=True
                    continue
                if in_trigger:
                    if upper == "END" or upper.endswith("\nEND"):
                        in_trigger=False
                    continue
                statements.append(statement)
        with self.connect() as con:
            for statement in statements: con.execute(self._sql(statement))
            for table,columns in {**_PHASE2_COLUMNS,**_PHASE3_COLUMNS,**{'study_outcomes':{'observation_type':"TEXT NOT NULL DEFAULT 'TRAINING'","timepoint":"TEXT"},"idempotency_keys":{"status":"TEXT NOT NULL DEFAULT 'COMPLETED'","claim_token":"TEXT","lease_expires_at":"TEXT"},"code_change_proposals":{"approval_id":"TEXT"}}}.items():
                existing={row["column_name"] for row in con.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name=%s",(table,)).fetchall()}
                for name,definition in columns.items():
                    if name not in existing: con.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")
            for statement in (s.strip() for s in PROJECT_INDEX_SCHEMA.split(";") if s.strip()):
                con.execute(self._sql(statement))
            duplicate_maintenance=con.execute("""
                SELECT kind,entity_type,entity_id,COUNT(*) AS n
                FROM maintenance_work
                WHERE status IN ('PROPOSED','APPROVAL_PENDING','APPROVED','IN_PROGRESS')
                GROUP BY kind,entity_type,entity_id
                HAVING COUNT(*) > 1
            """).fetchall()
            if duplicate_maintenance:
                raise RuntimeError("cannot enforce unique active maintenance work: existing duplicate active items found")
            con.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_maintenance_active_identity ON maintenance_work(kind,entity_type,entity_id) WHERE status IN ('PROPOSED','APPROVAL_PENDING','APPROVED','IN_PROGRESS')")
            duplicate_research_queue=con.execute("""
                SELECT project_id,question,COUNT(*) AS n FROM hds_research_queue
                WHERE status IN ('PROPOSED','APPROVED','IN_PROGRESS')
                GROUP BY project_id,question HAVING COUNT(*) > 1
            """).fetchall()
            if duplicate_research_queue:
                raise RuntimeError("cannot enforce unique active research queue items: existing duplicate project/question items found")
            con.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_research_queue_active_identity ON hds_research_queue(project_id,question) WHERE status IN ('PROPOSED','APPROVED','IN_PROGRESS')")
            duplicate_agent_reviews=con.execute("""
                SELECT agent_run_id,COUNT(*) AS n FROM agent_output_reviews
                GROUP BY agent_run_id HAVING COUNT(*) > 1
            """).fetchall()
            if duplicate_agent_reviews:
                raise RuntimeError("cannot enforce unique agent output reviews: existing duplicate agent runs found")
            con.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_agent_output_review_run ON agent_output_reviews(agent_run_id)")
            duplicate_assignments=con.execute("""
                SELECT study_id,participant_id,COUNT(*) AS n
                FROM study_assignments
                GROUP BY study_id,participant_id
                HAVING COUNT(*) > 1
            """).fetchall()
            if duplicate_assignments:
                raise RuntimeError("cannot enforce unique study assignments: existing duplicate participant assignments found")
            con.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_study_assignment_participant ON study_assignments(study_id,participant_id)")
            duplicate_evidence=con.execute("""
                SELECT claim_id,source_id,stance,excerpt_hash,COUNT(*) AS n
                FROM evidence
                GROUP BY claim_id,source_id,stance,excerpt_hash
                HAVING COUNT(*) > 1
            """).fetchall()
            if duplicate_evidence:
                raise RuntimeError("cannot enforce unique evidence attachments: existing duplicate claim/source/stance/excerpt records found")
            con.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_evidence_attachment_identity ON evidence(claim_id,source_id,stance,excerpt_hash)")
            duplicate_training_sessions=con.execute("""
                SELECT protocol_id,participant_ref,session_number,COUNT(*) AS n
                FROM training_sessions
                GROUP BY protocol_id,participant_ref,session_number
                HAVING COUNT(*) > 1
            """).fetchall()
            if duplicate_training_sessions:
                raise RuntimeError("cannot enforce unique training sessions: existing duplicate protocol/participant/session records found")
            con.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_training_session_identity ON training_sessions(protocol_id,participant_ref,session_number)")
            duplicate_sessions=con.execute("""
                SELECT study_id,participant_id,phase,session_number,COUNT(*) AS n
                FROM study_sessions
                GROUP BY study_id,participant_id,phase,session_number
                HAVING COUNT(*) > 1
            """).fetchall()
            if duplicate_sessions:
                raise RuntimeError("cannot enforce unique study sessions: existing duplicate sessions found")
            con.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_study_session_identity ON study_sessions(study_id,participant_id,phase,session_number)")
            duplicate_outcomes=con.execute("""
                SELECT study_id,participant_id,outcome_name,observation_type,COALESCE(session_id,''),COALESCE(timepoint,''),COUNT(*) AS n
                FROM study_outcomes
                GROUP BY study_id,participant_id,outcome_name,observation_type,COALESCE(session_id,''),COALESCE(timepoint,'')
                HAVING COUNT(*) > 1
            """).fetchall()
            if duplicate_outcomes:
                raise RuntimeError("cannot enforce unique study outcome observations: existing duplicate observations found")
            con.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_study_outcome_observation_identity ON study_outcomes(study_id,participant_id,outcome_name,observation_type,COALESCE(session_id,''),COALESCE(timepoint,''))")

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
CREATE UNIQUE INDEX IF NOT EXISTS idx_scientific_construct_identity ON scientific_constructs((COALESCE(project_id,'')),name,version);
CREATE TABLE IF NOT EXISTS scientific_measures (id TEXT PRIMARY KEY, construct_id TEXT NOT NULL REFERENCES scientific_constructs(id), name TEXT NOT NULL, operational_definition TEXT NOT NULL, method TEXT NOT NULL, unit TEXT, reliability_note TEXT NOT NULL, validity_note TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS interventions (id TEXT PRIMARY KEY, project_id TEXT, name TEXT NOT NULL UNIQUE, target_construct_id TEXT REFERENCES scientific_constructs(id), rationale TEXT NOT NULL, mechanism TEXT NOT NULL, evidence_level TEXT NOT NULL, dosage TEXT NOT NULL, population TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL);
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

CREATE TABLE IF NOT EXISTS intervention_evidence (id TEXT PRIMARY KEY, intervention_id TEXT NOT NULL REFERENCES interventions(id), evidence_kind TEXT NOT NULL, evidence_ref TEXT NOT NULL, notes TEXT NOT NULL, created_at TEXT NOT NULL, UNIQUE(intervention_id,evidence_kind,evidence_ref));
CREATE TABLE IF NOT EXISTS construct_versions (id TEXT PRIMARY KEY, construct_id TEXT NOT NULL REFERENCES scientific_constructs(id), version INTEGER NOT NULL, definition TEXT NOT NULL, operational_scope TEXT NOT NULL, change_reason TEXT NOT NULL, created_at TEXT NOT NULL, UNIQUE(construct_id,version));
CREATE TABLE IF NOT EXISTS study_measure_definitions (id TEXT PRIMARY KEY, study_id TEXT NOT NULL REFERENCES studies(id), name TEXT NOT NULL, construct_id TEXT REFERENCES scientific_constructs(id), operational_definition TEXT NOT NULL, method TEXT NOT NULL, scale_type TEXT NOT NULL, unit TEXT, reliability_note TEXT NOT NULL, validity_note TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL, UNIQUE(study_id,name));
CREATE TABLE IF NOT EXISTS study_measure_bindings (id TEXT PRIMARY KEY, study_id TEXT NOT NULL REFERENCES studies(id), measure_id TEXT NOT NULL REFERENCES study_measure_definitions(id), observation_type TEXT NOT NULL, timepoint TEXT NOT NULL, required INTEGER NOT NULL DEFAULT 1, UNIQUE(study_id,measure_id,observation_type,timepoint));
CREATE TRIGGER IF NOT EXISTS trg_intervention_evidence_project_guard
BEFORE INSERT ON intervention_evidence
WHEN EXISTS (
 SELECT 1 FROM interventions i
 JOIN evidence e ON e.id=NEW.evidence_ref
 JOIN claims c ON c.id=e.claim_id
 WHERE i.id=NEW.intervention_id AND i.project_id IS NOT NULL AND c.project_id != i.project_id
)
BEGIN SELECT RAISE(ABORT,'intervention evidence belongs to another project'); END;

CREATE TRIGGER IF NOT EXISTS trg_training_protocol_evidence_project_guard
BEFORE INSERT ON training_protocol_evidence
WHEN EXISTS (
 SELECT 1 FROM training_protocols p
 JOIN evidence e ON e.id=NEW.evidence_ref
 JOIN claims c ON c.id=e.claim_id
 WHERE p.id=NEW.protocol_id AND c.project_id != p.project_id
)
BEGIN SELECT RAISE(ABORT,'training protocol evidence belongs to another project'); END;

CREATE TRIGGER IF NOT EXISTS trg_intervention_insert_supported_gate
BEFORE INSERT ON interventions
WHEN NEW.status='SUPPORTED'
BEGIN SELECT RAISE(ABORT,'SUPPORTED intervention must use lifecycle promotion'); END;

CREATE TRIGGER IF NOT EXISTS trg_training_protocol_insert_supported_gate
BEFORE INSERT ON training_protocols
WHEN NEW.status='SUPPORTED'
BEGIN SELECT RAISE(ABORT,'SUPPORTED training protocol must use lifecycle promotion'); END;

CREATE TRIGGER IF NOT EXISTS trg_intervention_admitted_immutable
BEFORE UPDATE ON interventions
WHEN OLD.status IN ('SUPPORTED','RETIRED') AND (
    OLD.status='RETIRED' OR NEW.status=OLD.status
)
BEGIN SELECT RAISE(ABORT,'admitted intervention is immutable'); END;

CREATE TRIGGER IF NOT EXISTS trg_intervention_evidence_admitted_guard
BEFORE INSERT ON intervention_evidence
WHEN EXISTS (SELECT 1 FROM interventions WHERE id=NEW.intervention_id AND status IN ('SUPPORTED','RETIRED'))
BEGIN SELECT RAISE(ABORT,'evidence cannot be changed for an admitted intervention'); END;

CREATE TRIGGER IF NOT EXISTS trg_intervention_evidence_admitted_delete_guard
BEFORE DELETE ON intervention_evidence
WHEN EXISTS (SELECT 1 FROM interventions WHERE id=OLD.intervention_id AND status IN ('SUPPORTED','RETIRED'))
BEGIN SELECT RAISE(ABORT,'evidence cannot be changed for an admitted intervention'); END;

CREATE TRIGGER IF NOT EXISTS trg_training_protocol_admitted_immutable
BEFORE UPDATE ON training_protocols
WHEN OLD.status IN ('SUPPORTED','RETIRED') AND (
    OLD.status='RETIRED' OR NEW.status=OLD.status
)
BEGIN SELECT RAISE(ABORT,'admitted training protocol is immutable'); END;

CREATE TRIGGER IF NOT EXISTS trg_training_protocol_evidence_admitted_guard
BEFORE INSERT ON training_protocol_evidence
WHEN EXISTS (SELECT 1 FROM training_protocols WHERE id=NEW.protocol_id AND status IN ('SUPPORTED','RETIRED'))
BEGIN SELECT RAISE(ABORT,'evidence cannot be changed for an admitted training protocol'); END;

CREATE TRIGGER IF NOT EXISTS trg_training_protocol_evidence_admitted_delete_guard
BEFORE DELETE ON training_protocol_evidence
WHEN EXISTS (SELECT 1 FROM training_protocols WHERE id=OLD.protocol_id AND status IN ('SUPPORTED','RETIRED'))
BEGIN SELECT RAISE(ABORT,'evidence cannot be changed for an admitted training protocol'); END;

CREATE TRIGGER IF NOT EXISTS trg_intervention_supported_gate
BEFORE UPDATE OF status ON interventions
WHEN NEW.status='SUPPORTED' AND (
 NOT EXISTS (SELECT 1 FROM intervention_evidence WHERE intervention_id=NEW.id)
 OR EXISTS (
   SELECT 1 FROM intervention_evidence ie
   LEFT JOIN evidence e ON e.id=ie.evidence_ref
   WHERE ie.intervention_id=NEW.id AND (e.id IS NULL OR e.verified != 1)
 )
 OR NEW.evidence_level NOT IN ('SUPPORTED','WELL_SUPPORTED')
)
BEGIN SELECT RAISE(ABORT,'SUPPORTED intervention requires verified evidence and supported evidence level'); END;

CREATE TRIGGER IF NOT EXISTS trg_training_protocol_supported_gate
BEFORE UPDATE OF status ON training_protocols
WHEN NEW.status='SUPPORTED' AND (
 (NEW.source_claim_id IS NULL AND NEW.intervention_id IS NULL)
 OR NOT EXISTS (SELECT 1 FROM training_protocol_evidence WHERE protocol_id=NEW.id)
 OR EXISTS (
   SELECT 1 FROM training_protocol_evidence pe
   LEFT JOIN evidence e ON e.id=pe.evidence_ref
   WHERE pe.protocol_id=NEW.id AND (e.id IS NULL OR e.verified != 1)
 )
 OR NOT EXISTS (SELECT 1 FROM training_sessions WHERE protocol_id=NEW.id)
 OR NOT EXISTS (SELECT 1 FROM training_sessions WHERE protocol_id=NEW.id AND transfer_score IS NOT NULL)
 OR NOT EXISTS (SELECT 1 FROM training_sessions WHERE protocol_id=NEW.id AND retention_score IS NOT NULL)
)
BEGIN SELECT RAISE(ABORT,'SUPPORTED training protocol admission requirements are not met'); END;"""


# Keep a single authoritative SQLite migration path. The function is defined above
# but resolves PHASE6/PHASE7 globals at runtime, after all schema constants exist.

# Scientific analysis artifacts become immutable after creation/freeze/audit.
# Keep these guards in the authoritative SQLite migration path so direct SQL cannot bypass the scientific audit trail.
_PHASE4_ANALYSIS_IMMUTABILITY_SQL = """
CREATE TRIGGER IF NOT EXISTS trg_study_analysis_plan_immutable_update
BEFORE UPDATE ON study_analysis_plans
WHEN OLD.frozen=1
BEGIN SELECT RAISE(ABORT,'frozen analysis plan is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_study_analysis_plan_immutable_delete
BEFORE DELETE ON study_analysis_plans
WHEN OLD.frozen=1
BEGIN SELECT RAISE(ABORT,'frozen analysis plan is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_study_analysis_result_immutable_update
BEFORE UPDATE ON study_analysis_results
WHEN EXISTS (SELECT 1 FROM study_analysis_audit WHERE analysis_result_id=OLD.id)
BEGIN SELECT RAISE(ABORT,'audited analysis result is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_study_analysis_result_immutable_delete
BEFORE DELETE ON study_analysis_results
WHEN EXISTS (SELECT 1 FROM study_analysis_audit WHERE analysis_result_id=OLD.id)
BEGIN SELECT RAISE(ABORT,'audited analysis result is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_study_analysis_metrics_immutable_update
BEFORE UPDATE ON study_analysis_metrics
WHEN EXISTS (SELECT 1 FROM study_analysis_audit a WHERE a.study_id=OLD.study_id AND a.analysis_plan_id=OLD.analysis_plan_id AND a.outcome_name=OLD.outcome_name)
BEGIN SELECT RAISE(ABORT,'audited analysis metrics are immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_study_analysis_metrics_immutable_delete
BEFORE DELETE ON study_analysis_metrics
WHEN EXISTS (SELECT 1 FROM study_analysis_audit a WHERE a.study_id=OLD.study_id AND a.analysis_plan_id=OLD.analysis_plan_id AND a.outcome_name=OLD.outcome_name)
BEGIN SELECT RAISE(ABORT,'audited analysis metrics are immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_study_analysis_audit_immutable_update
BEFORE UPDATE ON study_analysis_audit
BEGIN SELECT RAISE(ABORT,'analysis audit is immutable'); END;
CREATE TRIGGER IF NOT EXISTS trg_study_analysis_audit_immutable_delete
BEFORE DELETE ON study_analysis_audit
BEGIN SELECT RAISE(ABORT,'analysis audit is immutable'); END;
"""
Database.migrate = _migrate_phase4

