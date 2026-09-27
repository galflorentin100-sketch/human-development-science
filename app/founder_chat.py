from __future__ import annotations
import json
from uuid import uuid4
from app.models import now
from app.providers import ModelRequest, ObservableProvider, configured_provider
from app.cost_controls import CostControl
from app.founder_intelligence import FounderIntelligence

class FounderChatService:
    def __init__(self, db):
        self.db=db
        self.provider=ObservableProvider(configured_provider(),db)
        self.costs=CostControl(db)

    def ask(self, project_id: str, message: str, actor: str):
        message=str(message or "").strip()
        if not message:
            raise ValueError("message is required")
        if len(message)>8000:
            raise ValueError("message exceeds 8000 characters")
        snapshot=FounderIntelligence(self.db).snapshot(project_id)
        context=json.dumps(snapshot,sort_keys=True,default=str)
        prompt=(
            "You are the HDS Founder Intelligence assistant. "
            "Use only the supplied company snapshot. Do not invent metrics, evidence, sources, "
            "scientific conclusions, or completed work. Clearly distinguish observed state, "
            "inference, hypothesis, and unknowns. If the snapshot is insufficient, say so. "
            "Scientific truth must never be upgraded by this chat.\n\n"
            f"COMPANY SNAPSHOT:\n{context}\n\nFOUNDER QUESTION:\n{message}"
        )
        request=ModelRequest("founder-chat",prompt,"founder-safe",str(uuid4()))
        estimate=self.provider.preflight(request)
        if estimate>0:
            self.costs.reserve(request.request_id,estimate,"preflight","estimated","founder-chat",actor,metadata={"project_id":project_id})
        try:
            response=self.provider.complete(request)
            if estimate>0:
                self.costs.settle(request.request_id,float(response.estimated_cost or 0),response.provider,response.model,"founder-chat",actor,metadata={"project_id":project_id})
            elif response.estimated_cost>0:
                self.costs.record(request.request_id,response.estimated_cost,response.provider,response.model,"founder-chat",actor,metadata={"project_id":project_id})
        except Exception:
            if estimate>0:
                self.costs.release(request.request_id)
            raise
        return {
            "project_id":project_id,
            "answer":response.content,
            "provider":response.provider,
            "model":response.model,
            "verified":False,
            "uncertainty":"AI chat output is advisory and unverified; verify scientific claims through the governed research/evidence workflow.",
        }
