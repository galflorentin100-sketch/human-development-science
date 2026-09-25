"""Participant governance for human training studies.

Privacy-preserving references only. This layer records consent, withdrawal,
protocol deviations and adverse events without diagnosing participants.
It is deliberately conservative: withdrawal blocks new sessions.
"""
from uuid import uuid4
from app.models import now

class ParticipantGovernance:
    def __init__(self, db):
        self.db=db
        self._ensure()

    def _ensure(self):
        self.db.execute("""CREATE TABLE IF NOT EXISTS participant_governance (
            participant_ref TEXT PRIMARY KEY,
            consent_status TEXT NOT NULL DEFAULT 'PENDING',
            consent_version TEXT NOT NULL DEFAULT '',
            consented_at TEXT,
            withdrawn_at TEXT,
            notes TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )""")
        self.db.execute("""CREATE TABLE IF NOT EXISTS training_adverse_events (
            id TEXT PRIMARY KEY,
            participant_ref TEXT NOT NULL,
            protocol_id TEXT NOT NULL,
            severity TEXT NOT NULL,
            description TEXT NOT NULL,
            action TEXT NOT NULL,
            resolved INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        )""")
        self.db.execute("""CREATE TABLE IF NOT EXISTS protocol_deviations (
            id TEXT PRIMARY KEY,
            participant_ref TEXT NOT NULL,
            protocol_id TEXT NOT NULL,
            session_id TEXT,
            deviation TEXT NOT NULL,
            impact TEXT NOT NULL,
            created_at TEXT NOT NULL
        )""")

    def register(self, participant_ref, consent_version, actor="system"):
        if not str(participant_ref).strip() or not str(consent_version).strip():
            raise ValueError("participant reference and consent version are required")
        ts=now()
        self.db.execute("""INSERT OR REPLACE INTO participant_governance
            (participant_ref,consent_status,consent_version,consented_at,withdrawn_at,notes,created_at,updated_at)
            VALUES (?,?,?,?,?,?,COALESCE((SELECT created_at FROM participant_governance WHERE participant_ref=?),?),?)""",
            (str(participant_ref),"CONSENTED",str(consent_version),ts,None,"",str(participant_ref),ts,ts))
        return self.get(participant_ref)

    def get(self, participant_ref):
        return self.db.one("SELECT * FROM participant_governance WHERE participant_ref=?",(str(participant_ref),))

    def assert_active(self, participant_ref):
        row=self.get(participant_ref)
        if not row or row["consent_status"]!="CONSENTED" or row["withdrawn_at"]:
            raise ValueError("participant is not actively consented")
        return row

    def withdraw(self, participant_ref, reason=""):
        row=self.get(participant_ref)
        if not row: raise ValueError("participant not registered")
        ts=now()
        self.db.execute("UPDATE participant_governance SET consent_status='WITHDRAWN', withdrawn_at=?, notes=?, updated_at=? WHERE participant_ref=?",(ts,reason or "",ts,str(participant_ref)))
        return self.get(participant_ref)

    def record_adverse_event(self, participant_ref, protocol_id, severity, description, action="STOP_AND_REVIEW"):
        self.assert_active(participant_ref)
        if severity not in {"LOW","MODERATE","HIGH","CRITICAL"}: raise ValueError("invalid adverse-event severity")
        if not str(description).strip(): raise ValueError("adverse-event description is required")
        i=str(uuid4()); ts=now()
        self.db.execute("""INSERT INTO training_adverse_events
            (id,participant_ref,protocol_id,severity,description,action,created_at)
            VALUES (?,?,?,?,?,?,?)""",(i,str(participant_ref),protocol_id,severity,description,action,ts))
        return self.db.one("SELECT * FROM training_adverse_events WHERE id=?",(i,))

    def record_deviation(self, participant_ref, protocol_id, deviation, impact, session_id=None):
        self.assert_active(participant_ref)
        if not str(deviation).strip(): raise ValueError("deviation is required")
        i=str(uuid4())
        self.db.execute("""INSERT INTO protocol_deviations
            (id,participant_ref,protocol_id,session_id,deviation,impact,created_at)
            VALUES (?,?,?,?,?,?,?)""",(i,str(participant_ref),protocol_id,session_id,deviation,impact or "",now()))
        return self.db.one("SELECT * FROM protocol_deviations WHERE id=?",(i,))
