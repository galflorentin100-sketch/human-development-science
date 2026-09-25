"""Structured AI output boundary. LLM text is never evidence by itself."""
from app.scientific_ai import ScientificAIGuard,ScientificStatement
class ScientificAIRuntime:
    def __init__(self,db): self.db=db; self.guard=ScientificAIGuard()
    def validate_output(self,text,classification,evidence_refs=(),transfer_observed=False,retention_observed=False,causal_design=False):
        s=ScientificStatement(text=text,classification=classification,evidence_refs=tuple(evidence_refs))
        self.guard.validate(s)
        if classification=="INFERENCE":
            self.guard.validate_interpretation(text,evidence_refs=evidence_refs,transfer_observed=transfer_observed,retention_observed=retention_observed,causal_design=causal_design)
        return {"text":text,"classification":classification,"evidence_refs":list(evidence_refs),
                "accepted_as_evidence":False,"policy":"AI output requires external evidence/review before scientific adoption"}
