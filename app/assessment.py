"""Assessment engine for longitudinal human development measurement."""
from uuid import uuid4
from app.models import now

TIMEPOINTS={"BASELINE","POST","RETENTION","FOLLOW_UP"}

class AssessmentService:
    def __init__(self,db): self.db=db
    def _project(self,project_id):
        if not self.db.one("SELECT id FROM projects WHERE id=? AND company_id='hds'",(project_id,)): raise ValueError("project not found")
    def create_construct(self,project_id,domain_id,name,operational_definition,actor):
        self._project(project_id)
        if not str(domain_id).strip() or not str(name).strip() or not str(operational_definition).strip(): raise ValueError("construct fields are required")
        i=str(uuid4()); self.db.execute("INSERT INTO hds_constructs(id,project_id,domain_id,name,operational_definition,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?)",(i,project_id,domain_id,name.strip(),operational_definition.strip(),"ACTIVE",now(),now()))
        return self.db.one("SELECT * FROM hds_constructs WHERE id=?",(i,))
    def create_measure(self,project_id,construct_id,name,unit,min_value=None,max_value=None,higher_is_better=True,actor=None):
        self._project(project_id); c=self.db.one("SELECT project_id FROM hds_constructs WHERE id=?",(construct_id,))
        if not c or c["project_id"]!=project_id: raise ValueError("construct does not belong to project")
        if not str(name).strip() or not str(unit).strip(): raise ValueError("measure name and unit are required")
        if min_value is not None and max_value is not None and float(min_value)>float(max_value): raise ValueError("min_value cannot exceed max_value")
        i=str(uuid4()); self.db.execute("INSERT INTO hds_assessment_measures(id,project_id,construct_id,name,unit,min_value,max_value,higher_is_better,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",(i,project_id,construct_id,name.strip(),unit.strip(),min_value,max_value,int(bool(higher_is_better)),"ACTIVE",now(),now()))
        return self.db.one("SELECT * FROM hds_assessment_measures WHERE id=?",(i,))
    def start(self,project_id,participant_ref,timepoint):
        self._project(project_id)
        if timepoint not in TIMEPOINTS: raise ValueError("invalid assessment timepoint")
        if not str(participant_ref).strip(): raise ValueError("participant_ref is required")
        existing=self.db.one("SELECT * FROM hds_assessment_sessions WHERE project_id=? AND participant_ref=? AND timepoint=? AND status='OPEN'",(project_id,participant_ref.strip(),timepoint))
        if existing: return existing
        i=str(uuid4()); self.db.execute("INSERT INTO hds_assessment_sessions(id,project_id,participant_ref,timepoint,started_at,status,created_at) VALUES (?,?,?,?,?,?,?)",(i,project_id,participant_ref.strip(),timepoint,now(),"OPEN",now()))
        return self.db.one("SELECT * FROM hds_assessment_sessions WHERE id=?",(i,))
    def observe(self,session_id,measure_id,value,note=None):
        s=self.db.one("SELECT * FROM hds_assessment_sessions WHERE id=?",(session_id,)); m=self.db.one("SELECT * FROM hds_assessment_measures WHERE id=?",(measure_id,))
        if not s or not m: raise ValueError("assessment session or measure not found")
        if s["project_id"]!=m["project_id"]: raise ValueError("session and measure belong to different projects")
        if s["status"]!="OPEN": raise ValueError("assessment session is closed")
        v=float(value)
        if m["min_value"] is not None and v<m["min_value"]: raise ValueError("value is below measure minimum")
        if m["max_value"] is not None and v>m["max_value"]: raise ValueError("value is above measure maximum")
        i=str(uuid4()); self.db.execute("INSERT INTO hds_assessment_observations(id,session_id,measure_id,value,observed_at,note) VALUES (?,?,?,?,?,?)",(i,session_id,measure_id,v,now(),note))
        return self.db.one("SELECT * FROM hds_assessment_observations WHERE id=?",(i,))
    def complete(self,session_id):
        s=self.db.one("SELECT * FROM hds_assessment_sessions WHERE id=?",(session_id,))
        if not s: raise ValueError("assessment session not found")
        if s["status"]!="OPEN": raise ValueError("assessment session is not open")
        self.db.execute("UPDATE hds_assessment_sessions SET status='COMPLETED',completed_at=? WHERE id=? AND status='OPEN'",(now(),session_id))
        return self.db.one("SELECT * FROM hds_assessment_sessions WHERE id=?",(session_id,))
    def progress(self,project_id,participant_ref,measure_id):
        self._project(project_id); m=self.db.one("SELECT * FROM hds_assessment_measures WHERE id=? AND project_id=?",(measure_id,project_id))
        if not m: raise ValueError("measure not found")
        rows=self.db.all("SELECT s.timepoint,s.started_at,o.value,o.observed_at FROM hds_assessment_sessions s JOIN hds_assessment_observations o ON o.session_id=s.id WHERE s.project_id=? AND s.participant_ref=? AND o.measure_id=? ORDER BY s.started_at",(project_id,participant_ref,measure_id))
        return {"measure":m,"observations":rows}
