from dataclasses import dataclass
from typing import Any

FACT="FACT"
INFERENCE="INFERENCE"
HYPOTHESIS="HYPOTHESIS"
OPINION="OPINION"

@dataclass(frozen=True)
class ScientificStatement:
    text: str
    classification: str
    evidence_refs: tuple[str, ...] = ()

class ScientificAIGuard:
    """Prevents unsupported certainty in AI-generated scientific content."""

    VALID={FACT,INFERENCE,HYPOTHESIS,OPINION}

    def validate(self, statement: ScientificStatement) -> ScientificStatement:
        if statement.classification not in self.VALID:
            raise ValueError("invalid scientific classification")
        if not statement.text.strip():
            raise ValueError("scientific statement cannot be empty")
        if statement.classification==FACT and not statement.evidence_refs:
            raise ValueError("FACT requires at least one evidence reference")
        return statement

    def classify(self, text: str, evidence_refs=(), requested="HYPOTHESIS") -> ScientificStatement:
        statement=ScientificStatement(text=text,classification=requested,evidence_refs=tuple(evidence_refs))
        return self.validate(statement)

    def prompt_constraints(self) -> list[str]:
        return [
            "Never invent a study, result, statistic, citation, participant, or measurement.",
            "If evidence is insufficient, explicitly state that evidence is insufficient.",
            "Never upgrade a hypothesis or inference into a fact without evidence.",
            "Separate observed data, interpretation, hypothesis, and opinion.",
            "Preserve uncertainty and contradictory evidence.",
            "Do not fabricate missing values; use null or unknown.",
        ]

    def evidence_level(self, verified_sources: int, independent_reviews: int, replication_count: int) -> str:
        if verified_sources < 1: return "UNTESTED"
        if independent_reviews < 1: return "PRELIMINARY"
        if replication_count < 1: return "SUPPORTED"
        return "WELL_SUPPORTED"
