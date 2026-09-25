"""Deterministic outcome synthesis; descriptive only, never causal inference."""
class TrainingOutcomeAnalyzer:
    def __init__(self, db): self.db=db
    def summarize(self, protocol_id):
        sessions=self.db.all("SELECT * FROM training_sessions WHERE protocol_id=? ORDER BY session_number,created_at",(protocol_id,))
        def avg(field):
            vals=[float(s[field]) for s in sessions if s[field] is not None]
            return sum(vals)/len(vals) if vals else None
        adherence=[int(s["adherence"]) for s in sessions]
        return {"protocol_id":protocol_id,"n_sessions":len(sessions),
                "adherence_rate":sum(adherence)/len(adherence) if adherence else None,
                "mean_task_success":avg("task_success"),"mean_transfer_score":avg("transfer_score"),
                "mean_retention_score":avg("retention_score"),"mean_decision_accuracy":avg("decision_accuracy"),
                "mean_initiation_latency":avg("initiation_latency"),"mean_recovery_score":avg("recovery_score"),
                "interpretation":"descriptive session summary only; does not establish efficacy or causality"}
    def change(self, protocol_id, metric):
        allowed={"task_success","transfer_score","retention_score","decision_accuracy","initiation_latency","recovery_score"}
        if metric not in allowed: raise ValueError("unsupported outcome metric")
        rows=self.db.all(f"SELECT session_number,{metric} value FROM training_sessions WHERE protocol_id=? AND {metric} IS NOT NULL ORDER BY session_number",(protocol_id,))
        if len(rows)<2: return {"metric":metric,"n":len(rows),"change":None}
        first=float(rows[0]["value"]); last=float(rows[-1]["value"])
        return {"metric":metric,"n":len(rows),"first":first,"last":last,"change":last-first,
                "interpretation":"within-protocol descriptive change; no causal attribution"}
