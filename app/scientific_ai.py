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

    BLOCKED_CERTAINTY_PATTERNS=("proved","proves","proven","caused","causes","causal","definitively","works","effective","durable","generalizes","הוכיח","הוכיחה","הוכח","גרם","גרמה","גורם","יעיל","יעילה","נשמר","נשמרה","הכליל","הכלילה")

    def validate_interpretation(self, text, *, evidence_refs=(), causal_design=False,
                                retention_observed=False, transfer_observed=False):
        """Constrain scientific prose to what the supplied design/data can support."""
        if not text or not text.strip():
            raise ValueError("scientific interpretation cannot be empty")
        lowered=text.casefold()
        blocked=[p for p in self.BLOCKED_CERTAINTY_PATTERNS if p in lowered]
        if blocked and not causal_design:
            raise ValueError("interpretation contains causal/overconfident language unsupported by the declared design")
        if any(p in lowered for p in ("durable","נשמר","נשמרה")) and not retention_observed:
            raise ValueError("durability claim requires observed retention data")
        if any(p in lowered for p in ("generalizes","הכליל","הכלילה")) and not transfer_observed:
            raise ValueError("generalization claim requires observed transfer data")
        return self.classify(text,evidence_refs=evidence_refs,requested=INFERENCE)

    def evidence_level(self, verified_sources: int, independent_reviews: int, replication_count: int) -> str:
        if verified_sources < 1: return "UNTESTED"
        if independent_reviews < 1: return "PRELIMINARY"
        if replication_count < 1: return "SUPPORTED"
        return "WELL_SUPPORTED"
