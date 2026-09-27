"""Human-development product layer for HDS.

This module models the real-world product surface of HDS: programs, challenges,
competitions, and measurable human-development domains. It deliberately keeps
scientific claims separate from product activities.
"""
from uuid import uuid4
from app.models import now

HDS_DOMAINS = {
    "MENTAL_TOUGHNESS": "Mental toughness and adaptive response to challenge",
    "DISCIPLINE": "Self-regulation, consistency, and goal-directed behavior",
    "RESILIENCE": "Recovery and adaptation following setbacks or stressors",
    "PHYSICAL_PERFORMANCE": "Strength, endurance, speed, agility, and general physical capability",
    "COMBAT_SPORTS": "Supervised combat-sport skill, control, and physical performance",
    "OUTDOOR_ADVENTURE": "Navigation, terrain, environmental challenge, and expedition skills",
    "CHARACTER": "Values and character-related behaviors studied with explicit operational definitions",
    "TEAMWORK": "Coordination, cooperation, communication, and collective performance",
    "LEADERSHIP": "Leadership behaviors studied through observable tasks and outcomes",
    "PROBLEM_SOLVING": "Decision-making, reasoning, and adaptive problem solving",
}

PROGRAM_STATUSES = {"DRAFT", "ACTIVE", "PAUSED", "COMPLETED", "RETIRED"}
CHALLENGE_STATUSES = {"DRAFT", "ACTIVE", "RETIRED"}
COMPETITION_STATUSES = {"DRAFT", "REGISTRATION", "ACTIVE", "COMPLETED", "CANCELLED"}

class HumanDevelopmentService:
    def __init__(self, db):
        self.db = db

    def domains(self):
        return [{"id": k, "name": v} for k, v in HDS_DOMAINS.items()]

    def create_program(self, project_id, name, objective, domain_id, actor):
        self._project(project_id)
        if domain_id not in HDS_DOMAINS:
            raise ValueError("unknown HDS domain")
        if not str(name or "").strip() or not str(objective or "").strip():
            raise ValueError("program name and objective are required")
        i = str(uuid4())
        self.db.execute(
            "INSERT INTO hds_programs(id,project_id,name,objective,domain_id,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?)",
            (i, project_id, name.strip(), objective.strip(), domain_id, "DRAFT", now(), now()),
        )
        return self.db.one("SELECT * FROM hds_programs WHERE id=?", (i,))

    def create_challenge(self, program_id, name, description, challenge_type, difficulty, safety_constraints, actor):
        program = self.db.one("SELECT * FROM hds_programs WHERE id=?", (program_id,))
        if not program:
            raise ValueError("program not found")
        required = (name, description, challenge_type, safety_constraints)
        if any(not str(x or "").strip() for x in required):
            raise ValueError("challenge fields are required")
        difficulty = int(difficulty)
        if difficulty < 1 or difficulty > 10:
            raise ValueError("difficulty must be 1..10")
        i = str(uuid4())
        self.db.execute(
            "INSERT INTO hds_challenges(id,program_id,name,description,challenge_type,difficulty,safety_constraints,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (i, program_id, name.strip(), description.strip(), challenge_type.strip(),
             difficulty, safety_constraints.strip(), "DRAFT", now(), now()),
        )
        return self.db.one("SELECT * FROM hds_challenges WHERE id=?", (i,))

    def create_competition(self, project_id, name, format, actor):
        self._project(project_id)
        if not str(name or "").strip() or not str(format or "").strip():
            raise ValueError("competition name and format are required")
        i = str(uuid4())
        self.db.execute(
            "INSERT INTO hds_competitions(id,project_id,name,format,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?)",
            (i, project_id, name.strip(), format.strip(), "DRAFT", now(), now()),
        )
        return self.db.one("SELECT * FROM hds_competitions WHERE id=?", (i,))

    def add_event(self, competition_id, challenge_id, sequence, scoring_rule):
        competition = self.db.one("SELECT project_id FROM hds_competitions WHERE id=?", (competition_id,))
        if not competition:
            raise ValueError("competition not found")
        challenge = self.db.one(
            "SELECT p.project_id FROM hds_challenges c JOIN hds_programs p ON p.id=c.program_id WHERE c.id=?",
            (challenge_id,),
        )
        if not challenge:
            raise ValueError("challenge not found")
        if str(challenge["project_id"]) != str(competition["project_id"]):
            raise ValueError("challenge belongs to another project")
        sequence = int(sequence)
        if sequence < 1:
            raise ValueError("event sequence must be positive")
        if not str(scoring_rule or "").strip():
            raise ValueError("scoring rule is required")
        i = str(uuid4())
        self.db.execute(
            "INSERT INTO hds_competition_events(id,competition_id,challenge_id,sequence,scoring_rule,created_at) VALUES (?,?,?,?,?,?)",
            (i, competition_id, challenge_id, sequence, scoring_rule.strip(), now()),
        )
        return self.db.one("SELECT * FROM hds_competition_events WHERE id=?", (i,))

    def register_participant(self, competition_id, participant_ref):
        competition = self.db.one("SELECT id,status FROM hds_competitions WHERE id=?", (competition_id,))
        if not competition:
            raise ValueError("competition not found")
        if competition["status"] not in {"DRAFT", "REGISTRATION"}:
            raise ValueError("competition is not accepting registrations")
        if not str(participant_ref or "").strip():
            raise ValueError("participant reference is required")
        i = str(uuid4())
        try:
            self.db.execute(
                "INSERT INTO hds_competition_participants(id,competition_id,participant_ref,consent_status,created_at) VALUES (?,?,?,?,?)",
                (i, competition_id, participant_ref.strip(), "PENDING", now()),
            )
        except Exception as exc:
            raise ValueError("participant is already registered") from exc
        return self.db.one("SELECT * FROM hds_competition_participants WHERE id=?", (i,))

    def record_consent(self, participant_id):
        row = self.db.one("SELECT * FROM hds_competition_participants WHERE id=?", (participant_id,))
        if not row:
            raise ValueError("participant not found")
        if row["consent_status"] == "REVOKED":
            raise ValueError("revoked participant consent cannot be reactivated")
        self.db.execute("UPDATE hds_competition_participants SET consent_status='CONSENTED' WHERE id=?", (participant_id,))
        return self.db.one("SELECT * FROM hds_competition_participants WHERE id=?", (participant_id,))

    def create_safety_control(self, project_id, challenge_id, risk_class, stop_criteria,
                              eligibility_required=True, consent_required=True,
                              supervision_required=True, medical_review_required=False):
        challenge=self.db.one("""SELECT c.id,p.project_id FROM hds_challenges c
            JOIN hds_programs p ON p.id=c.program_id WHERE c.id=?""",(challenge_id,))
        if not challenge or challenge["project_id"] != project_id:
            raise ValueError("challenge does not belong to project")
        if risk_class not in {"LOW","MODERATE","HIGH","CRITICAL"}:
            raise ValueError("invalid risk class")
        if not str(stop_criteria or "").strip():
            raise ValueError("stop criteria are required")
        i=str(uuid4())
        self.db.execute("""INSERT INTO hds_safety_controls
            (id,project_id,challenge_id,risk_class,eligibility_required,consent_required,
             supervision_required,medical_review_required,stop_criteria,status,created_at,updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (i,project_id,challenge_id,risk_class,int(eligibility_required),int(consent_required),
             int(supervision_required),int(medical_review_required),stop_criteria.strip(),"DRAFT",now(),now()))
        return self.db.one("SELECT * FROM hds_safety_controls WHERE id=?",(i,))

    def approve_safety(self, challenge_id, reviewer, decision, rationale):
        if decision not in {"APPROVED","REJECTED"}: raise ValueError("invalid safety decision")
        control=self.db.one("SELECT * FROM hds_safety_controls WHERE challenge_id=?",(challenge_id,))
        if not control: raise ValueError("safety control not found")
        if not str(reviewer or "").strip() or not str(rationale or "").strip():
            raise ValueError("reviewer and rationale are required")
        i=str(uuid4())
        self.db.execute("""INSERT INTO hds_safety_reviews
            (id,project_id,challenge_id,reviewer,decision,rationale,created_at)
            VALUES (?,?,?,?,?,?,?)""",
            (i,control["project_id"],challenge_id,reviewer,decision,rationale,now()))
        status="APPROVED" if decision=="APPROVED" else "REJECTED"
        self.db.execute("UPDATE hds_safety_controls SET status=?,updated_at=? WHERE challenge_id=?",
                        (status,now(),challenge_id))
        return self.db.one("SELECT * FROM hds_safety_controls WHERE challenge_id=?",(challenge_id,))

    def assert_challenge_safe_to_execute(self, challenge_id, participant_id):
        control=self.db.one("SELECT * FROM hds_safety_controls WHERE challenge_id=?",(challenge_id,))
        if not control or control["status"]!="APPROVED":
            raise ValueError("challenge safety approval required")
        if control["consent_required"]:
            participant=self.db.one("""SELECT consent_status FROM hds_competition_participants
                WHERE id=?""",(participant_id,))
            if not participant or participant["consent_status"]!="CONSENTED":
                raise ValueError("participant consent required")
        if control["eligibility_required"]:
            participant=self.db.one("""SELECT eligibility_status FROM hds_competition_participants
                WHERE id=?""",(participant_id,))
            if not participant or participant["eligibility_status"] not in {"ELIGIBLE","APPROVED"}:
                raise ValueError("participant eligibility required")
        return control

    def record_score(self, event_id, participant_id, metric, score):
        row = self.db.one(
            """SELECT ce.id, ce.competition_id, cp.id AS participant_id
               FROM hds_competition_events ce
               JOIN hds_competition_participants cp ON cp.competition_id=ce.competition_id
               WHERE ce.id=? AND cp.id=?""",
            (event_id, participant_id),
        )
        if not row:
            raise ValueError("event and participant do not belong to the same competition")
        consent = self.db.one("SELECT consent_status FROM hds_competition_participants WHERE id=?", (participant_id,))
        if not consent or consent["consent_status"] != "CONSENTED":
            raise ValueError("participant consent is required before scoring")
        if not str(metric or "").strip():
            raise ValueError("score metric is required")
        i = str(uuid4())
        self.db.execute(
            "INSERT INTO hds_competition_scores(id,event_id,participant_id,metric,score,observed_at) VALUES (?,?,?,?,?,?)",
            (i, event_id, participant_id, metric.strip(), float(score), now()),
        )
        return self.db.one("SELECT * FROM hds_competition_scores WHERE id=?", (i,))

    def bind_participant_to_study(self, competition_id, participant_id, study_participant_id):
        participant=self.db.one("SELECT competition_id FROM hds_competition_participants WHERE id=?", (participant_id,))
        study_participant=self.db.one("SELECT study_id FROM study_participants WHERE id=?", (study_participant_id,))
        if not participant or participant["competition_id"] != competition_id:
            raise ValueError("competition participant not found")
        if not study_participant:
            raise ValueError("study participant not found")
        existing=self.db.one("SELECT 1 FROM hds_competition_study_bindings WHERE competition_id=? AND participant_id=?", (competition_id,participant_id))
        if existing: raise ValueError("participant is already bound to a study")
        i=str(uuid4())
        self.db.execute("""INSERT INTO hds_competition_study_bindings
            (id,competition_id,participant_id,study_participant_id) VALUES (?,?,?,?)""",
            (i,competition_id,participant_id,study_participant_id))
        return self.db.one("SELECT * FROM hds_competition_study_bindings WHERE id=?", (i,))

    def bind_event_measure(self, event_id, study_id, measure_id, observation_type, timepoint):
        event=self.db.one("""SELECT ce.competition_id,c.project_id FROM hds_competition_events ce
            JOIN hds_competitions c ON c.id=ce.competition_id WHERE ce.id=?""",(event_id,))
        measure=self.db.one("SELECT study_id,status FROM study_measure_definitions WHERE id=?",(measure_id,))
        study=self.db.one("SELECT project_id FROM studies WHERE id=?",(study_id,))
        binding=self.db.one("""SELECT 1 FROM study_measure_bindings
            WHERE study_id=? AND measure_id=? AND observation_type=? AND timepoint=?""",
            (study_id,measure_id,observation_type,timepoint))
        if not event or not measure or not study: raise ValueError("event, study, and measure are required")
        if event["project_id"] != study["project_id"] or measure["study_id"] != study_id:
            raise ValueError("competition and study must belong to the same project")
        if measure["status"] != "PREREGISTERED" or not binding:
            raise ValueError("competition outcome requires a preregistered study measure binding")
        i=str(uuid4())
        self.db.execute("""INSERT INTO hds_competition_measure_bindings
            (id,event_id,study_id,measure_id,observation_type,timepoint) VALUES (?,?,?,?,?,?)""",
            (i,event_id,study_id,measure_id,observation_type,timepoint))
        return self.db.one("SELECT * FROM hds_competition_measure_bindings WHERE id=?", (i,))

    def record_score_as_outcome(self, event_id, participant_id, metric, score):
        binding=self.db.one("""SELECT cmb.study_id,cmb.observation_type,cmb.timepoint,sp.id AS study_participant_id,
                md.name,md.unit
            FROM hds_competition_measure_bindings cmb
            JOIN hds_competition_study_bindings csb ON csb.competition_id=(SELECT competition_id FROM hds_competition_events WHERE id=cmb.event_id)
                AND csb.participant_id=?
            JOIN study_participants sp ON sp.id=csb.study_participant_id
            JOIN study_measure_definitions md ON md.id=cmb.measure_id
            WHERE cmb.event_id=? AND md.name=?""",
            (participant_id,event_id,metric))
        if not binding:
            raise ValueError("score has no preregistered scientific outcome binding")
        score_row=self.record_score(event_id,participant_id,metric,score)
        from app.hds_outcomes import HDSOutcomeService
        outcome=HDSOutcomeService(self.db).record(
            binding["study_id"],binding["study_participant_id"],binding["name"],
            float(score),binding["unit"],binding["observation_type"],binding["timepoint"])
        return {"score":score_row,"outcome":outcome}

    def competition_snapshot(self, competition_id):
        competition = self.db.one("SELECT * FROM hds_competitions WHERE id=?", (competition_id,))
        if not competition:
            raise ValueError("competition not found")
        events = self.db.all(
            """SELECT ce.*, hc.name AS challenge_name, hc.challenge_type, hc.difficulty
               FROM hds_competition_events ce
               JOIN hds_challenges hc ON hc.id=ce.challenge_id
               WHERE ce.competition_id=? ORDER BY ce.sequence""",
            (competition_id,),
        )
        participants = self.db.all(
            "SELECT * FROM hds_competition_participants WHERE competition_id=? ORDER BY created_at",
            (competition_id,),
        )
        scores = self.db.all(
            """SELECT cs.*, ce.sequence FROM hds_competition_scores cs
               JOIN hds_competition_events ce ON ce.id=cs.event_id
               WHERE ce.competition_id=? ORDER BY ce.sequence,cs.observed_at""",
            (competition_id,),
        )
        return {"competition": competition, "events": events, "participants": participants, "scores": scores}

    def _project(self, project_id):
        if not self.db.one("SELECT id FROM projects WHERE id=?", (project_id,)):
            raise ValueError("project not found")
