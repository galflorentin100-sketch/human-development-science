from statistics import mean, stdev
from uuid import uuid4
from app.models import now

class ScientificAnalysisEngine:
    """
    Descriptive analysis only. This layer deliberately does not estimate
    causality, significance, confidence intervals, or population effects.
    """

    def __init__(self, db):
        self.db=db

    def _plan(self, study_id, analysis_plan_id):
        plan=self.db.one("SELECT * FROM study_analysis_plans WHERE id=? AND study_id=?",(analysis_plan_id,study_id))
        if not plan or not plan["frozen"]:
            raise ValueError("analysis plan must be frozen")
        return plan

    def analyze(self, study_id, analysis_plan_id, outcome_name):
        self._plan(study_id,analysis_plan_id)
        participants=self.db.all("SELECT id FROM study_participants WHERE study_id=?",(study_id,))
        rows=self.db.all(
            "SELECT participant_id,observation_type,session_id,value,missing_reason,recorded_at "
            "FROM study_outcomes WHERE study_id=? AND outcome_name=? ORDER BY participant_id,recorded_at",
            (study_id,outcome_name)
        )
        by={}
        for r in rows:
            by.setdefault(r["participant_id"],[]).append(r)

        training_changes=[]
        retention_values=[]
        real_world_values=[]
        for pid in [p["id"] for p in participants]:
            vals=by.get(pid,[])
            numeric=[r for r in vals if r["value"] is not None]
            training=[r for r in numeric if r["observation_type"]=="TRAINING"]
            if len(training)>=2:
                training_changes.append(training[-1]["value"]-training[0]["value"])
            retention=[r["value"] for r in numeric if r["observation_type"]=="RETENTION"]
            if retention: retention_values.append(retention[-1])
            real=[r["value"] for r in numeric if r["observation_type"]=="REAL_WORLD"]
            if real: real_world_values.append(real[-1])

        n_total=len(participants)
        n_change=len(training_changes)
        metrics={
            "training_mean_change": (mean(training_changes) if training_changes else None, n_change),
            "training_sd_change": (stdev(training_changes) if len(training_changes)>=2 else None, n_change),
            "retention_mean": (mean(retention_values) if retention_values else None, len(retention_values)),
            "real_world_mean": (mean(real_world_values) if real_world_values else None, len(real_world_values)),
            "training_change_observation_rate": (n_change/n_total if n_total else None, n_total),
            "retention_observation_rate": (len(retention_values)/n_total if n_total else None, n_total),
            "real_world_observation_rate": (len(real_world_values)/n_total if n_total else None, n_total),
        }

        result_id=str(uuid4())
        missing=n_total-n_change
        with self.db.transaction() as con:
            con.execute(
                "INSERT INTO study_analysis_results(id,study_id,analysis_plan_id,outcome_name,n_total,n_observed,estimate,uncertainty,missing_data_note,interpretation,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (result_id,study_id,analysis_plan_id,outcome_name,n_total,n_change,
                 metrics["training_mean_change"][0],
                 "Descriptive only; no inferential model, confidence interval, p-value, or causal estimate.",
                 f"{missing} of {n_total} participants lacked at least two observed TRAINING values.",
                 "Within-participant pre/post change among observed values; this does not establish that the intervention caused the change.",
                 now())
            for name,(value,denom) in metrics.items():
                con.execute(
                    "INSERT INTO study_analysis_metrics(id,study_id,analysis_plan_id,outcome_name,metric_name,metric_value,denominator,note,created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                    (str(uuid4()),study_id,analysis_plan_id,outcome_name,name,value,denom,None,now())
                )
        return {
            "result":self.db.one("SELECT * FROM study_analysis_results WHERE id=?",(result_id,)),
            "metrics":self.db.all("SELECT metric_name,metric_value,denominator,note FROM study_analysis_metrics WHERE study_id=? AND analysis_plan_id=? AND outcome_name=?",(study_id,analysis_plan_id,outcome_name))
        }
