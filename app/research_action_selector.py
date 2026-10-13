"""Deterministic routing policy for scientific research questions.

Routing chooses the next *kind of work*; it never authorizes execution of
human-participant studies, interventions, publication, spending, or contact.
"""
class ResearchActionSelector:
    ACTIONS={"INFORMATION_GATHERING","FALSIFICATION_REVIEW","REPLICATION_REVIEW","EXPERIMENT_DESIGN"}

    def select(self,candidate):
        kind=str(candidate.get("kind",""))
        reason=str(candidate.get("reason","")).lower()
        trigger=str(candidate.get("trigger_type",candidate.get("reason",""))).upper()
        title=str(candidate.get("title","")).lower()
        if "FALSIFICATION" in trigger or "falsif" in reason or "falsif" in title:
            action="FALSIFICATION_REVIEW"
        elif "REPLICATION" in trigger or "replication" in reason or "replication" in title:
            action="REPLICATION_REVIEW"
        elif kind=="SCIENTIFIC_MAINTENANCE":
            action="INFORMATION_GATHERING"
        elif kind=="RESEARCH":
            action="INFORMATION_GATHERING"
        else:
            action="EXPERIMENT_DESIGN"
        return {
            "action":action,
            "autonomous_mode":"DIGITAL_RESEARCH" if action=="INFORMATION_GATHERING" else "GOVERNED_REVIEW",
            "execution_authorized":action=="INFORMATION_GATHERING",
            "reason":"Deterministic routing policy; authorization still follows existing governance gates."
        }

    def explain(self,candidate):
        return self.select(candidate)
