from __future__ import annotations
from uuid import uuid4
from app.models import now

class MeasurementRegistry:
    VALID_SCALE_TYPES={"BINARY","PROPORTION","COUNT","DURATION","CONTINUOUS","ORDINAL","NOMINAL"}
    VALID_OBSERVATIONS={"TRAINING","NEAR_TRANSFER","FAR_TRANSFER","REAL_WORLD","RETENTION"}

    def __init__(self,db): self.db=db

    def define(self,study_id,name,operational_definition,method,scale_type,unit=None,reliability_note="",validity_note="",construct_id=None,status="PREREGISTERED"):
        if not self.db.one("SELECT 1 FROM studies WHERE id=?",(study_id,)): raise ValueError("study does not exist")
        if scale_type not in self.VALID_SCALE_TYPES: raise ValueError("invalid scale type")
        if not operational_definition.strip() or not method.strip(): raise ValueError("operational definition and method are required")
        if self.db.one("SELECT 1 FROM study_measure_definitions WHERE study_id=? AND name=?",(study_id,name)): raise ValueError("measure already defined for study")
        if construct_id and not self.db.one("SELECT 1 FROM scientific_constructs WHERE id=?",(construct_id,)): raise ValueError("construct does not exist")
        i=str(uuid4())
        self.db.execute("INSERT INTO study_measure_definitions(id,study_id,name,construct_id,operational_definition,method,scale_type,unit,reliability_note,validity_note,status,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",(i,study_id,name,construct_id,operational_definition,method,scale_type,unit,reliability_note,validity_note,status,now()))
        return self.db.one("SELECT * FROM study_measure_definitions WHERE id=?",(i,))

    def bind(self,study_id,measure_id,observation_type,timepoint,required=True):
        if observation_type not in self.VALID_OBSERVATIONS: raise ValueError("invalid observation type")
        if not self.db.one("SELECT 1 FROM study_measure_definitions WHERE id=? AND study_id=?",(measure_id,study_id)): raise ValueError("measure does not belong to study")
        i=str(uuid4())
        self.db.execute("INSERT INTO study_measure_bindings(id,study_id,measure_id,observation_type,timepoint,required) VALUES (?,?,?,?,?,?)",(i,study_id,measure_id,observation_type,timepoint,1 if required else 0))
        return self.db.one("SELECT * FROM study_measure_bindings WHERE id=?",(i,))

    def validate_observation(self,study_id,measure_id,observation_type,timepoint):
        row=self.db.one("SELECT b.*,m.name,m.scale_type,m.unit FROM study_measure_bindings b JOIN study_measure_definitions m ON m.id=b.measure_id WHERE b.study_id=? AND b.measure_id=? AND b.observation_type=? AND b.timepoint=?",(study_id,measure_id,observation_type,timepoint))
        if not row: raise ValueError("observation is not preregistered for this study")
        return row
