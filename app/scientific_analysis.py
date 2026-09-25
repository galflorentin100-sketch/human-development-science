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

    @staticmethod
    def _analysis_spec(plan):
        import json
        raw=plan["analysis_spec"] or "{}"
        try:
            spec=json.loads(raw)
        except (TypeError, ValueError) as exc:
            raise ValueError("frozen analysis plan contains invalid analysis_spec") from exc
        if not isinstance(spec,dict):
            raise ValueError("analysis_spec must be an object")
        return spec

    def validate_analysis_spec(self, plan):
        """Validate the minimum preregistration contract before any inferential analysis."""
        spec=self._analysis_spec(plan)
        required=("outcome_name","estimand","population","estimator","ci_method",
                  "missing_data_policy","multiplicity_policy","subgroup_policy","stopping_rule")
        missing=[k for k in required if not spec.get(k)]
        if missing:
            raise ValueError("analysis_spec missing required preregistration fields: "+", ".join(missing))
        allowed=spec.get("allowed_methods",[])
        if not isinstance(allowed,list) or not allowed:
            raise ValueError("analysis_spec.allowed_methods must be a non-empty list")
        if spec["outcome_name"] != spec.get("registered_outcome_name",spec["outcome_name"]):
            raise ValueError("analysis_spec outcome does not match registered outcome")
        return {"valid":True,"allowed_methods":allowed,"spec":spec}

    def _require_method(self, plan, method):
        spec=self._analysis_spec(plan)
        methods=spec.get("allowed_methods", spec.get("methods", []))
        if isinstance(methods,str): methods=[methods]
        if method not in methods:
            raise ValueError(f"analysis method '{method}' is not preregistered")
        return spec

    @staticmethod
    def _mean_ci95(values):
        """Normal-approximation 95% CI for a mean; descriptive/inferential boundary is explicit."""
        if not values:
            return {"mean":None,"se":None,"ci95_low":None,"ci95_high":None,"n":0}
        m=mean(values); n=len(values)
        if n < 2:
            return {"mean":m,"se":None,"ci95_low":None,"ci95_high":None,"n":n}
        se=stdev(values)/(n**0.5)
        return {"mean":m,"se":se,"ci95_low":m-1.96*se,"ci95_high":m+1.96*se,"n":n}

    @staticmethod
    def _cohens_d_independent(a,b):
        if len(a)<2 or len(b)<2: return None
        na,nb=len(a),len(b)
        va,vb=stdev(a)**2,stdev(b)**2
        pooled=((na-1)*va+(nb-1)*vb)/(na+nb-2)
        if pooled<=0: return None
        return (mean(a)-mean(b))/(pooled**0.5)

    def missingness_report(self, study_id, outcome_name):
        """Report missingness by observation type without imputing or assuming its mechanism."""
        participants=self.db.all("SELECT id FROM study_participants WHERE study_id=?",(study_id,))
        rows=self.db.all("SELECT participant_id,observation_type,value,missing_reason FROM study_outcomes WHERE study_id=? AND outcome_name=?",(study_id,outcome_name))
        by={(p["id"],t):[] for p in participants for t in ("TRAINING","NEAR_TRANSFER","FAR_TRANSFER","REAL_WORLD","RETENTION")}
        for r in rows:
            if (r["participant_id"],r["observation_type"]) in by: by[(r["participant_id"],r["observation_type"])].append(r)
        report={}
        for t in ("TRAINING","NEAR_TRANSFER","FAR_TRANSFER","REAL_WORLD","RETENTION"):
            observed=sum(any(x["value"] is not None for x in by[(p["id"],t)]) for p in participants)
            missing=len(participants)-observed
            reasons={}
            for p in participants:
                for x in by[(p["id"],t)]:
                    if x["value"] is None and x["missing_reason"]:
                        reasons[x["missing_reason"]]=reasons.get(x["missing_reason"],0)+1
            report[t]={"n_total":len(participants),"n_observed":observed,"n_missing":missing,
                       "observation_rate":observed/len(participants) if participants else None,
                       "missing_reasons":reasons}
        return report

    def longitudinal_retention_analysis(self, study_id, analysis_plan_id, outcome_name):
        """Describe post-to-retention trajectories without fitting an unregistered repeated-measures model."""
        plan=self._plan(study_id,analysis_plan_id)
        self._require_method(plan,"INFERENTIAL_RANDOMIZED_ARM")
        rows=self.db.all(
            "SELECT participant_id,observation_type,value,recorded_at FROM study_outcomes "
            "WHERE study_id=? AND outcome_name=? AND value IS NOT NULL "
            "ORDER BY participant_id,recorded_at",(study_id,outcome_name))
        grouped={}
        for r in rows:
            grouped.setdefault(r["participant_id"],{}).setdefault(r["observation_type"],[]).append(r["value"])
        trajectories=[]
        for pid,v in grouped.items():
            post=(v.get("TRAINING") or [None])[-1]
            retention=(v.get("RETENTION") or [None])[-1]
            if post is not None and retention is not None:
                trajectories.append(retention-post)
        summary=self._mean_ci95(trajectories)
        return {"post_to_retention_change":summary,
                "n_complete_trajectories":len(trajectories),
                "missing_data_policy":"No imputation; only participants with observed post and retention values are included.",
                "interpretation":"Descriptive trajectory among complete post/retention cases; does not establish durable intervention effects or rule out informative dropout."}

    def inferential_randomized_arm_analysis(self, study_id, analysis_plan_id, outcome_name):
        """
        Inferential layer for a two-arm randomized study.
        Reports unadjusted effect size and normal-approximation CI.
        This is not a substitute for a preregistered model chosen for the
        outcome distribution, sample size, missingness mechanism, or repeated measures.
        """
        plan=self._plan(study_id,analysis_plan_id)
        self._require_method(plan,"LONGITUDINAL_RETENTION")
        rows=self.db.all(
            "SELECT p.id participant_id,a.arm,o.observation_type,o.value,o.recorded_at "
            "FROM study_participants p JOIN study_assignments a ON a.participant_id=p.id AND a.study_id=p.study_id "
            "LEFT JOIN study_outcomes o ON o.participant_id=p.id AND o.study_id=? AND o.outcome_name=? "
            "WHERE p.study_id=? ORDER BY p.id,o.recorded_at",(study_id,outcome_name,study_id))
        grouped={}
        for r in rows:
            p=grouped.setdefault(r["participant_id"],{"arm":r["arm"],"values":[]})
            if r["observation_type"]=="TRAINING" and r["value"] is not None: p["values"].append(r["value"])
        changes={"INTERVENTION":[],"CONTROL":[]}
        for p in grouped.values():
            if len(p["values"])>=2 and p["arm"] in changes: changes[p["arm"]].append(p["values"][-1]-p["values"][0])
        i=self._mean_ci95(changes["INTERVENTION"]); c=self._mean_ci95(changes["CONTROL"])
        d=self._cohens_d_independent(changes["INTERVENTION"],changes["CONTROL"])
        diff=i["mean"]-c["mean"] if i["mean"] is not None and c["mean"] is not None else None
        result={"intervention":i,"control":c,"between_arm_difference":diff,"cohens_d":d,
                "limitations":["unadjusted","normal-approximation CI","complete paired cases only",
                "no multiplicity correction","no missing-data model","no longitudinal model"],
                "interpretation":"These are model-dependent statistical estimates. They should not be treated as proof of causality or generalization without checking the preregistered design assumptions."}
        rid=str(uuid4())
        with self.db.transaction() as con:
            con.execute("INSERT INTO study_analysis_results(id,study_id,analysis_plan_id,outcome_name,n_total,n_observed,estimate,uncertainty,missing_data_note,interpretation,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (rid,study_id,analysis_plan_id,outcome_name,len(grouped),sum(len(v["values"])>=2 for v in grouped.values()),
                 diff,"95% CIs use a normal approximation; Cohen's d is unadjusted.",
                 "Complete paired cases only; participants with missing baseline/post values are excluded.",
                 result["interpretation"],now()))
            metrics={
                "intervention_mean_change":(i["mean"],i["n"]),
                "intervention_ci95_low":(i["ci95_low"],i["n"]),
                "intervention_ci95_high":(i["ci95_high"],i["n"]),
                "control_mean_change":(c["mean"],c["n"]),
                "control_ci95_low":(c["ci95_low"],c["n"]),
                "control_ci95_high":(c["ci95_high"],c["n"]),
                "between_arm_difference":(diff,min(i["n"],c["n"])),
                "cohens_d":(d,min(i["n"],c["n"]))
            }
            for name,(value,denom) in metrics.items():
                con.execute("INSERT INTO study_analysis_metrics(id,study_id,analysis_plan_id,outcome_name,metric_name,metric_value,denominator,note,created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                    (str(uuid4()),study_id,analysis_plan_id,outcome_name,name,value,denom,None,now()))
        return result

    def randomized_arm_analysis(self, study_id, analysis_plan_id, outcome_name):
        """
        Preregistered-style descriptive randomized-arm analysis.
        Computes group-specific baseline->post changes and their difference.
        This is an unadjusted estimate; it is not a substitute for a full
        inferential model and does not establish population-level causality.
        """
        self._plan(study_id, analysis_plan_id)
        rows=self.db.all(
            "SELECT p.id AS participant_id,a.arm,o.observation_type,o.value,o.recorded_at "
            "FROM study_participants p "
            "JOIN study_assignments a ON a.participant_id=p.id AND a.study_id=p.study_id "
            "LEFT JOIN study_outcomes o ON o.participant_id=p.id AND o.study_id=? AND o.outcome_name=? "
            "WHERE p.study_id=? ORDER BY p.id,o.recorded_at",
            (study_id,outcome_name,study_id)
        )
        participants={}
        for r in rows:
            participants.setdefault(r["participant_id"],{"arm":r["arm"],"baseline":None,"post":None})
            if r["observation_type"]=="TRAINING" and r["value"] is not None:
                # Preserve the first and last training observations as baseline/post.
                if participants[r["participant_id"]]["baseline"] is None:
                    participants[r["participant_id"]]["baseline"]=r["value"]
                participants[r["participant_id"]]["post"]=r["value"]

        changes={"INTERVENTION":[],"CONTROL":[]}
        for p in participants.values():
            if p["arm"] in changes and p["baseline"] is not None and p["post"] is not None:
                changes[p["arm"]].append(p["post"]-p["baseline"])

        means={arm:(mean(vals) if vals else None) for arm,vals in changes.items()}
        effect=None
        if means["INTERVENTION"] is not None and means["CONTROL"] is not None:
            effect=means["INTERVENTION"]-means["CONTROL"]

        n_assigned={arm:sum(1 for p in participants.values() if p["arm"]==arm) for arm in changes}
        n_observed={arm:len(changes[arm]) for arm in changes}
        retention=self._arm_retention(study_id,outcome_name)

        result_id=str(uuid4())
        uncertainty=("Unadjusted descriptive between-arm change difference; no "
                     "confidence interval, p-value, covariate adjustment, or "
                     "missing-data model was applied.")
        interpretation=("Intervention minus control difference in observed "
                         "TRAINING pre/post change. Random assignment supports "
                         "causal interpretation only under the study's design "
                         "assumptions; this endpoint alone does not establish "
                         "generalization or durability.")
        with self.db.transaction() as con:
            con.execute(
                "INSERT INTO study_analysis_results(id,study_id,analysis_plan_id,outcome_name,n_total,n_observed,estimate,uncertainty,missing_data_note,interpretation,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (result_id,study_id,analysis_plan_id,outcome_name,sum(n_assigned.values()),
                 sum(n_observed.values()),effect,uncertainty,
                 f"INTERVENTION: {n_assigned['INTERVENTION']-n_observed['INTERVENTION']} missing paired observations; CONTROL: {n_assigned['CONTROL']-n_observed['CONTROL']} missing paired observations.",
                 interpretation,now()))
            metrics={
                "intervention_mean_change":(means["INTERVENTION"],n_observed["INTERVENTION"]),
                "control_mean_change":(means["CONTROL"],n_observed["CONTROL"]),
                "between_arm_change_difference":(effect,min(n_observed.values()) if n_observed else 0),
                "intervention_observation_rate":((n_observed["INTERVENTION"]/n_assigned["INTERVENTION"]) if n_assigned["INTERVENTION"] else None,n_assigned["INTERVENTION"]),
                "control_observation_rate":((n_observed["CONTROL"]/n_assigned["CONTROL"]) if n_assigned["CONTROL"] else None,n_assigned["CONTROL"]),
                "retention_intervention_mean":(retention["INTERVENTION"]["mean"],retention["INTERVENTION"]["n"]),
                "retention_control_mean":(retention["CONTROL"]["mean"],retention["CONTROL"]["n"])
            }
            for name,(value,denom) in metrics.items():
                con.execute("INSERT INTO study_analysis_metrics(id,study_id,analysis_plan_id,outcome_name,metric_name,metric_value,denominator,note,created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                            (str(uuid4()),study_id,analysis_plan_id,outcome_name,name,value,denom,None,now()))
        return {"result":self.db.one("SELECT * FROM study_analysis_results WHERE id=?",(result_id,)),
                "metrics":self.db.all("SELECT metric_name,metric_value,denominator,note FROM study_analysis_metrics WHERE study_id=? AND analysis_plan_id=? AND outcome_name=?",(study_id,analysis_plan_id,outcome_name)),
                "retention":retention}

    def _arm_retention(self, study_id, outcome_name):
        rows=self.db.all(
            "SELECT a.arm,o.value FROM study_assignments a JOIN study_outcomes o ON o.participant_id=a.participant_id AND o.study_id=a.study_id WHERE a.study_id=? AND o.outcome_name=? AND o.observation_type='RETENTION' AND o.value IS NOT NULL",
            (study_id,outcome_name))
        grouped={"INTERVENTION":[],"CONTROL":[]}
        for r in rows:
            if r["arm"] in grouped: grouped[r["arm"]].append(r["value"])
        return {arm:{"mean":mean(vals) if vals else None,"n":len(vals)} for arm,vals in grouped.items()}

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
