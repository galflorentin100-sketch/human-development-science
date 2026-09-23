from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4
def now(): return datetime.now(timezone.utc).isoformat()
class TaskStatus(str,Enum):
    BACKLOG="BACKLOG"; PLANNED="PLANNED"; ASSIGNED="ASSIGNED"; RUNNING="RUNNING"; REVIEW="REVIEW"; BLOCKED="BLOCKED"; FAILED="FAILED"; COMPLETED="COMPLETED"; CANCELLED="CANCELLED"
@dataclass(frozen=True)
class AgentDefinition:
    id:str; name:str; role:str; manager:str="coo"; capabilities:tuple[str,...]=(); permissions:tuple[str,...]=()
@dataclass
class CompanyMessage:
    id:str; from_agent:str; to_agent:str; type:str; task_id:str|None; payload:dict; confidence:float; evidence_refs:list[str]; uncertainties:list[str]; recommended_actions:list[str]; created_at:str
    @classmethod
    def create(cls,from_agent,to_agent,type,task_id,payload,confidence=0.0,evidence_refs=None,uncertainties=None,recommended_actions=None):
        return cls(str(uuid4()),from_agent,to_agent,type,task_id,payload,confidence,evidence_refs or [],uncertainties or [],recommended_actions or [],now())
    def to_dict(self): return asdict(self)
