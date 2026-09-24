from uuid import uuid4
from app.models import now

class ScientificRegistry:
    """Structured registry for constructs, measures, interventions and versioned definitions."""

    def __init__(self, db):
        self.db = db

    def construct(self, name, definition, construct_type="CAPABILITY", project_id=None, status="DRAFT", version=1):
        if not name or not str(name).strip(): raise ValueError("construct name is required")
        if not definition or not str(definition).strip(): raise ValueError("construct definition is required")
        if int(version) < 1: raise ValueError("construct version must be positive")
        existing=self.db.one("SELECT 1 FROM scientific_constructs WHERE (project_id=? OR (project_id IS NULL AND ? IS NULL)) AND name=? AND version=?",(project_id,project_id,name,int(version)))
        if existing: raise ValueError("construct version already exists")
        i=str(uuid4())
        with self.db.transaction() as con:
            con.execute("INSERT INTO scientific_constructs(id,project_id,name,definition,construct_type,status,version,created_at) VALUES (?,?,?,?,?,?,?,?)",(i,project_id,name,definition,construct_type,status,int(version),now()))
            version_id=str(uuid4())
            con.execute("INSERT INTO construct_versions(id,construct_id,version,definition,operational_scope,change_reason,created_at) VALUES (?,?,?,?,?,?,?)",(version_id,i,int(version),definition,"Initial operational scope not yet specified","initial definition",now()))
        return self.db.one("SELECT * FROM scientific_constructs WHERE id=?",(i,))

    def measure(self, construct_id, name, operational_definition, method, unit=None, reliability_note="", validity_note="", status="DRAFT"):
        if not self.db.one("SELECT 1 FROM scientific_constructs WHERE id=?",(construct_id,)): raise ValueError("construct not found")
        if not operational_definition or not str(operational_definition).strip(): raise ValueError("operational definition is required")
        if not method or not str(method).strip(): raise ValueError("measurement method is required")
        i=str(uuid4())
        self.db.execute("INSERT INTO scientific_measures(id,construct_id,name,operational_definition,method,unit,reliability_note,validity_note,status,created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",(i,construct_id,name,operational_definition,method,unit,reliability_note,validity_note,status,now()))
        return self.db.one("SELECT * FROM scientific_measures WHERE id=?",(i,))

    def intervention(self, name, rationale, mechanism, evidence_level, dosage, population, target_construct_id=None, status="EXPERIMENTAL"):
        if target_construct_id and not self.db.one("SELECT 1 FROM scientific_constructs WHERE id=?",(target_construct_id,)): raise ValueError("target construct not found")
        if evidence_level not in {"UNTESTED","PLAUSIBLE","PRELIMINARY","SUPPORTED","WELL_SUPPORTED"}: raise ValueError("invalid evidence level")
        if status not in {"EXPERIMENTAL","PILOT","SUPPORTED","RETIRED"}: raise ValueError("invalid intervention status")
        i=str(uuid4())
        self.db.execute("INSERT INTO interventions(id,name,target_construct_id,rationale,mechanism,evidence_level,dosage,population,status,created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",(i,name,target_construct_id,rationale,mechanism,evidence_level,dosage,population,status,now()))
        return self.db.one("SELECT * FROM interventions WHERE id=?",(i,))

    def intervention_evidence(self, intervention_id, evidence_kind, evidence_ref, notes=""):
        if not self.db.one("SELECT 1 FROM interventions WHERE id=?",(intervention_id,)): raise ValueError("intervention not found")
        if evidence_kind not in {"PILOT","RCT","META_ANALYSIS","SYSTEMATIC_REVIEW","MECHANISTIC","OBSERVATIONAL","EXPERT_JUDGMENT"}:
            raise ValueError("invalid intervention evidence kind")
        i=str(uuid4())
        self.db.execute("INSERT INTO intervention_evidence(id,intervention_id,evidence_kind,evidence_ref,notes,created_at) VALUES (?,?,?,?,?,?)",(i,intervention_id,evidence_kind,evidence_ref,notes,now()))
        return self.db.one("SELECT * FROM intervention_evidence WHERE id=?",(i,))

    def version_construct(self, construct_id, definition, operational_scope, change_reason):
        current=self.db.one("SELECT * FROM scientific_constructs WHERE id=?",(construct_id,))
        if not current: raise ValueError("construct not found")
        next_version=int(current["version"])+1
        i=str(uuid4())
        with self.db.transaction() as con:
            con.execute("INSERT INTO construct_versions(id,construct_id,version,definition,operational_scope,change_reason,created_at) VALUES (?,?,?,?,?,?,?)",(i,construct_id,next_version,definition,operational_scope,change_reason,now()))
            con.execute("UPDATE scientific_constructs SET definition=?,version=? WHERE id=?",(definition,next_version,construct_id))
        return self.db.one("SELECT * FROM scientific_constructs WHERE id=?",(construct_id,))
