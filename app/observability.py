"""Operational observability helpers for HDS."""
from __future__ import annotations
import json
import logging
import sys
from uuid import uuid4

logger=logging.getLogger("hds")
_configured=False

def configure_logging():
    global _configured
    if _configured: return
    handler=logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.handlers.clear(); logger.addHandler(handler); logger.setLevel(logging.INFO)
    logger.propagate=False; _configured=True

def request_id(value=None):
    return value or str(uuid4())

def emit(event_type, **fields):
    configure_logging()
    record={"event":event_type, **fields}
    logger.info(json.dumps(record,ensure_ascii=False,sort_keys=True,default=str))
    return record

def audit(db,event_type,entity_type,entity_id,actor,payload=None):
    from app.models import now
    event_id=str(uuid4())
    db.execute(
        "INSERT INTO audit_logs(id,event_type,entity_type,entity_id,actor,payload,created_at) VALUES(?,?,?,?,?, ?,?)",
        (event_id,event_type,entity_type,entity_id,actor,json.dumps(payload or {},ensure_ascii=False,sort_keys=True),now()),
    )
    return event_id
