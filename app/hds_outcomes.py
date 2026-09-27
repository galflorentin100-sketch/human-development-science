from uuid import uuid4
from app.models import now

class HDSOutcomeService:
    """Connect HDS product activity to preregistered scientific measurement.

    Product scores are operational data. They do not become scientific evidence
    merely by being recorded; a study/measure binding is required for research use.
    """
    VALID_TYPES={"TRAINING","NEAR_TRANSFER","FAR_TRANSFER","REAL_WORLD","RETENTION"}

    def __init__(self, db):
        self.db=db

    def record(self, study_id, participant_id, outcome_name, value, unit, observation_type, timepoint, session_id=None):
        if observation_type not in self.VALID_TYPES:
            raise ValueError("invalid observation type")
        participant=self.db.one("SELECT * FROM study_participants WHERE id=? AND study_id=?", (participant_id,study_id))
        if not participant:
            raise ValueError("participant does not belong to study")
        if participant["consent_status"] not in {"CONSENTED","ENROLLED"}:
            raise ValueError("participant consent is required")
        if session_id and not self.db.one("SELECT 1 FROM study_sessions WHERE id=? AND study_id=? AND participant_id=?", (session_id,study_id,participant_id)):
            raise ValueError("session does not belong to participant and study")
        # A research outcome must match a preregistered measure/binding.
        measure=self.db.one(
            """SELECT b.*,m.name,m.scale_type,m.unit
               FROM study_measure_bindings b
               JOIN study_measure_definitions m ON m.id=b.measure_id
               WHERE b.study_id=? AND m.name=? AND b.observation_type=? AND b.timepoint=?""",
            (study_id,outcome_name,observation_type,timepoint),
        )
        if not measure:
            raise ValueError("outcome is not preregistered for this study")
        ident=str(uuid4())
        self.db.execute(
            """INSERT INTO study_outcomes
               (id,study_id,participant_id,session_id,outcome_name,value,unit,missing_reason,observation_type,timepoint,recorded_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (ident,study_id,participant_id,session_id,outcome_name,value,unit or measure["unit"],None,observation_type,timepoint,now()),
        )
        return self.db.one("SELECT * FROM study_outcomes WHERE id=?", (ident,))

    def list_for_study(self, study_id, observation_type=None):
        if observation_type is not None and observation_type not in self.VALID_TYPES:
            raise ValueError("invalid observation type")
        if observation_type:
            return self.db.all("SELECT * FROM study_outcomes WHERE study_id=? AND observation_type=? ORDER BY recorded_at", (study_id,observation_type))
        return self.db.all("SELECT * FROM study_outcomes WHERE study_id=? ORDER BY recorded_at", (study_id,))
