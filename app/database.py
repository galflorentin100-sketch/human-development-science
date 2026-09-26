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
        with self.connect() as con:
            cursor=con.execute(self._sql(sql),params)
            return cursor
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