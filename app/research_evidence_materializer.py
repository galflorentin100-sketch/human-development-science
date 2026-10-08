"""Materialize Research Agent output into strictly unverified, reviewable scientific artifacts.

This service is deliberately conservative: malformed output, missing source provenance,
or excerpts that cannot be located in stored source material are rejected rather than
repaired by inference.
"""
from __future__ import annotations
import json
from uuid import uuid4
from app.models import now
from app.evidence_pipeline import EvidencePipeline

_ALLOWED_CLASSIFICATIONS={"FACT","INFERENCE","HYPOTHESIS","OPINION"}
_ALLOWED_STANCES={"SUPPORTS","CONTRADICTS","NEUTRAL"}

class ResearchEvidenceMaterializer:
    def __init__(self,db):
        self.db=db
        self.evidence=EvidencePipeline(db)

    def materialize(self,agent_run_id):
        run=self.db.one("SELECT * FROM agent_runs WHERE id=?",(agent_run_id,))
        if not run:
            raise ValueError("agent run not found")
        task=self.db.one("SELECT * FROM tasks WHERE id=?",(run["task_id"],))
        if not task:
            raise ValueError("agent run task not found")
        link=self.db.one("SELECT * FROM research_agent_tasks WHERE task_id=?",(run["task_id"],))
        if not link:
            raise ValueError("research agent task mapping not found")
        ws=self.db.one("SELECT * FROM research_workspaces WHERE id=?",(link["workspace_id"],))
        if not ws or str(ws["project_id"]) != str(task["project_id"]):
            raise ValueError("research workspace/project mismatch")

        payload=self._payload(run["output_payload"])
        candidates=payload.get("candidate_claims",[])
        if isinstance(payload.get("result"),dict):
            result=payload["result"]
            candidates=result.get("candidate_claims",candidates)
        if not isinstance(candidates,list):
            raise ValueError("candidate_claims must be a JSON list")

        source_rows=self.db.all(
            """SELECT r.source_id,s.title,s.url,COALESCE(es.content,'') AS content
               FROM research_retrieval_results r
               JOIN sources s ON s.id=r.source_id
               LEFT JOIN evidence_sources es ON es.source_id=r.source_id AND es.state='PARSED'
               WHERE r.workspace_id=?
               AND r.retrieval_run_id=(SELECT id FROM research_retrieval_runs WHERE workspace_id=? ORDER BY created_at DESC LIMIT 1)""",
            (link["workspace_id"],link["workspace_id"]))
        sources={str(r["source_id"]):r for r in source_rows}
        created=[]
        errors=[]

        for index,candidate in enumerate(candidates):
            try:
                item=self._validate_candidate(candidate,index,sources)
                claim=self._claim(ws["project_id"],item["statement"],item["classification"])
                evidence=self.evidence.attach(
                    claim["id"],item["source_id"],item["exact_excerpt"],
                    stance=item["stance"],verified=False,actor=str(run["agent_id"]))
                review_task=self._create_review_task(
                    evidence["id"],ws["id"],ws["project_id"],str(run["agent_id"]))
                created.append({
                    "claim_id":claim["id"],
                    "evidence_id":evidence["id"],
                    "review_task_id":review_task["id"],
                    "source_id":item["source_id"],
                    "classification":item["classification"],
                    "stance":item["stance"],
                })
            except Exception as exc:
                errors.append({"index":index,"error":str(exc)})

        if not created and candidates:
            raise ValueError("no candidate claims could be materialized: "+json.dumps(errors,sort_keys=True))
        return {
            "agent_run_id":agent_run_id,
            "workspace_id":ws["id"],
            "project_id":ws["project_id"],
            "created":created,
            "rejected":errors,
            "candidate_count":len(candidates),
            "scientific_status":"UNVERIFIED_REVIEW_REQUIRED",
        }

    def _payload(self,raw):
        try:
            payload=json.loads(raw or "{}")
        except (TypeError,ValueError) as exc:
            raise ValueError("agent output_payload is not valid JSON") from exc
        if not isinstance(payload,dict):
            raise ValueError("agent output_payload must be a JSON object")
        return payload

    def _validate_candidate(self,candidate,index,sources):
        if not isinstance(candidate,dict):
            raise ValueError(f"candidate {index} must be an object")
        statement=str(candidate.get("statement") or "").strip()
        source_id=str(candidate.get("source_id") or "").strip()
        excerpt=str(candidate.get("exact_excerpt") or "")
        classification=str(candidate.get("classification") or "").upper().strip()
        stance=str(candidate.get("stance") or "SUPPORTS").upper().strip()
        if not statement: raise ValueError(f"candidate {index} has no statement")
        if classification not in _ALLOWED_CLASSIFICATIONS: raise ValueError(f"candidate {index} has invalid classification")
        if stance not in _ALLOWED_STANCES: raise ValueError(f"candidate {index} has invalid stance")
        if source_id not in sources: raise ValueError(f"candidate {index} cites a source outside the latest retrieval packet")
        if not excerpt.strip(): raise ValueError(f"candidate {index} has no exact_excerpt")
        content=sources[source_id]["content"] or ""
        if excerpt not in content:
            raise ValueError(f"candidate {index} exact_excerpt is not present in stored source content")
        return {"statement":statement,"source_id":source_id,"exact_excerpt":excerpt,
                "classification":classification,"stance":stance}

    def _claim(self,project_id,statement,classification):
        existing=self.db.one("SELECT * FROM claims WHERE project_id=? AND statement=?",(project_id,statement))
        if existing:
            if str(existing["classification"]) != classification:
                raise ValueError("existing claim has a different classification")
            return existing
        claim_id=str(uuid4())
        self.db.execute(
            """INSERT INTO claims
               (id,project_id,statement,classification,evidence_level,confidence,status,created_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            (claim_id,project_id,statement,classification,"UNVERIFIED",0.0,"PROPOSED",now()))
        return self.db.one("SELECT * FROM claims WHERE id=?",(claim_id,))

    def _create_review_task(self,evidence_id,workspace_id,project_id,creator_agent_id):
        aliases=("evidence-auditor","evidence","skeptic")
        placeholders=",".join("?" for _ in aliases)
        params=list(aliases)+list(aliases)
        reviewer=self.db.one(
            f"""SELECT id FROM agents
                WHERE status IN ('ACTIVE','IDLE')
                AND id != ?
                AND (id IN ({placeholders}) OR role IN ({placeholders}))
                ORDER BY created_at ASC,id ASC LIMIT 1""",
            (creator_agent_id,*params))
        if not reviewer:
            raise ValueError("independent evidence reviewer agent not found")
        existing=self.db.one(
            "SELECT * FROM research_evidence_review_tasks WHERE evidence_id=? AND reviewer_agent_id=?",
            (evidence_id,reviewer["id"]))
        if existing: return existing
        task_id=str(uuid4()); ts=now()
        with self.db.transaction() as con:
            con.execute(
                """INSERT INTO tasks
                   (id,project_id,title,status,assigned_agent_id,priority,success_criteria,
                    created_at,updated_at,owner,required_permissions,retry_limit)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (task_id,project_id,f"[EVIDENCE_AUDIT] {evidence_id}","PLANNED",
                 reviewer["id"],1.9,
                 json.dumps({"action":"REVIEW_SCIENTIFIC_EVIDENCE","evidence_id":evidence_id,
                             "guardrails":["Check the exact excerpt against the stored source.",
                                           "Do not infer beyond the excerpt.",
                                           "Return VERIFIED, REJECTED, UNCERTAIN, or CONFLICTED with rationale.",
                                           "Do not invent missing methods, participants, statistics, or results."],
                             "required_output":{"verdict":"one allowed verdict","rationale":"specific audit rationale"}},
                            sort_keys=True),
                 ts,ts,reviewer["id"],json.dumps(["READ"]),1))
            rid=str(uuid4())
            con.execute(
                """INSERT INTO research_evidence_review_tasks
                   (id,evidence_id,workspace_id,project_id,reviewer_agent_id,status,created_at)
                   VALUES (?,?,?,?,?,?,?)""",
                (rid,evidence_id,workspace_id,project_id,reviewer["id"],"PLANNED",ts))
        return self.db.one("SELECT * FROM research_evidence_review_tasks WHERE id=?",(rid,))
