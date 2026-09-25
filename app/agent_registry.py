"""Minimal role registry for the autonomous company layer."""
class AgentRegistry:
    ROLES={
        "researcher":"Find and synthesize relevant evidence.",
        "skeptic":"Challenge claims, assumptions, and evidence quality.",
        "evidence_auditor":"Audit provenance and evidence states.",
        "experiment_designer":"Design preregisterable experiments.",
        "analyst":"Run descriptive/statistical analyses.",
        "training_scientist":"Translate supported knowledge into testable protocols.",
        "safety_reviewer":"Review safety constraints and adverse events.",
        "knowledge_manager":"Maintain graph, freshness, and dependencies.",
        "product_scientist":"Translate validated knowledge into product requirements.",
        "qa":"Verify software and scientific invariants.",
        "founder_advisor":"Summarize decisions, blockers, risks, and opportunities.",
    }
    def list(self): return [{"id":k,"mission":v} for k,v in self.ROLES.items()]
