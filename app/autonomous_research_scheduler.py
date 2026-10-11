"""Governed scheduler for low-risk autonomous digital research.

This layer may start bounded literature/research-agent work without per-cycle
founder approval. It never authorizes participant research, interventions,
publication, spending, or external contact.
"""
import json
from uuid import uuid4
from app.models import now
from app.autonomous_research import AutonomousResearchPlanner
from app.research_queue import ResearchQueue
from app.research_action_selector import ResearchActionSelector
from app.research_action_executor import ResearchActionExecutor

class AutonomousResearchScheduler:
    DIGITAL_ONLY = "DIGITAL_RESEARCH"

    def __init__(self, db):
        self.db = db

    def _eligible(self, candidate):
        return candidate.get("kind") in {"RESEARCH", "SCIENTIFIC_MAINTENANCE"}

    def schedule_once(self, project_id, actor="autonomous-research"):
        project=self.db.one("SELECT * FROM projects WHERE id=?",(project_id,))
        if not project:
            raise ValueError("project not found")
        if project["status"] not in {"ACTIVE","RUNNING"}:
            return {"status":"PROJECT_NOT_EXECUTABLE","project_status":project["status"]}

        # Refresh deterministic research gaps before selection. This only creates
        # OPEN questions; it never mutates claims or scientific truth.
        from app.research_question_generator import ResearchQuestionGenerator
        gap_report=ResearchQuestionGenerator(self.db).generate(project_id)
        plan=AutonomousResearchPlanner(self.db).next_work()
        candidate=next((x for x in plan["next"] if self._eligible(x)), None)
        if not candidate:
            return {"status":"NO_ELIGIBLE_DIGITAL_RESEARCH","candidate_count":plan["candidate_count"],"gap_report":gap_report}

        route=ResearchActionSelector().select(candidate)
        candidate={**candidate,"action_type":route["action"],"route":route}
        # Only information-gathering is eligible for autonomous execution.
        if not route["execution_authorized"]:
            return {"status":"GOVERNED_REVIEW_REQUIRED","candidate":candidate,"gap_report":gap_report}
        question=str(candidate["title"]).strip()
        queue=ResearchQueue(self.db)
        item=queue.propose(
            project_id, question,
            rationale="Autonomous low-risk digital research selected by evidence-gap/risk policy.",
            trigger_type="AUTONOMOUS_SCHEDULER",
            priority="HIGH" if candidate["priority"] >= 90 else "NORMAL",
        )
        item_id=item["id"]

        # Autonomous execution is permitted only for the explicit digital mode.
        if candidate.get("kind") not in {"RESEARCH","SCIENTIFIC_MAINTENANCE"}:
            raise ValueError("autonomous execution policy permits digital research only")

        started=queue.autonomous_begin(item_id, actor, mode=self.DIGITAL_ONLY)
        workspace=started["workspace"]
        run_id=str(uuid4())
        ts=now()
        self.db.execute(
            "INSERT INTO autonomous_research_runs(id,project_id,queue_item_id,workspace_id,mode,status,reason,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
            (run_id,project_id,item_id,workspace["id"],self.DIGITAL_ONLY,"STARTED",
             "Autonomous digital research; governed gates remain in force.",ts,ts))
        # The scheduler must retrieve actual literature before preparing a research
        # task. Without this step the researcher is correctly blocked for lacking
        # source material, but the autonomous loop would never make progress.
        from app.scientific_retrieval import ScientificRetrievalService
        retrieval_service=ScientificRetrievalService(self.db)
        retrieval_queries=self._retrieval_queries(question)
        retrieval_runs=[
            retrieval_service.retrieve(
                workspace["id"], query=query, providers=("pubmed","crossref"), limit=20
            )
            for query in retrieval_queries
        ]
        # Preserve the legacy single-run field while exposing the full reproducible
        # search set. All discovered records remain explicitly unverified.
        retrieval=retrieval_runs[-1] if retrieval_runs else None
        execution=ResearchActionExecutor(self.db).execute(workspace["id"],candidate["action_type"],actor=actor)
        if execution["status"] != "TASK_CREATED":
            self.db.execute("UPDATE autonomous_research_runs SET status='GOVERNED_REVIEW_REQUIRED',updated_at=? WHERE id=?",(now(),run_id))
            return {"status":execution["status"],"run_id":run_id,"queue_item_id":item_id,
                    "workspace_id":workspace["id"],"task":execution["task"],"retrieval":retrieval,
                    "retrieval_runs":retrieval_runs,"retrieval_queries":retrieval_queries,
                    "candidate":candidate,"gap_report":gap_report}
        task_status=str(execution["task"].get("status") or "")
        run_status="BLOCKED_NO_SOURCES" if task_status=="BLOCKED" else "TASK_CREATED"
        self.db.execute("UPDATE autonomous_research_runs SET status=?,updated_at=? WHERE id=?",(run_status,now(),run_id))
        return {"status":run_status,"run_id":run_id,"queue_item_id":item_id,
                "workspace_id":workspace["id"],"task":execution["task"],"retrieval":retrieval,
                "retrieval_runs":retrieval_runs,"retrieval_queries":retrieval_queries,
                "candidate":candidate,"gap_report":gap_report}


    @staticmethod
    def _retrieval_queries(question):
        """Use separate reproducible searches for the initial self-discipline study."""
        normalized=str(question or "").lower().replace("—","-")
        if "self-discipline" in normalized or "self discipline" in normalized or "משמעת עצמית" in normalized:
            return [
                '("self-discipline" OR "self discipline") AND (definition OR construct OR measure OR scale OR measurement)',
                '(self-control OR self-regulation) AND (conceptualization OR measurement OR scale)',
                '("self-discipline" OR self-control OR self-regulation) AND ("systematic review" OR meta-analysis) AND (intervention OR training OR improve OR development)',
                '("self-control" OR "self-regulation" OR "self-discipline") AND (randomized OR trial OR intervention OR training)',
            ]
        return [str(question).strip()]

    def run(self, project_id, cycles=1):
        if not 1 <= int(cycles) <= 25:
            raise ValueError("cycles must be 1..25")
        results=[]
        for _ in range(int(cycles)):
            result=self.schedule_once(project_id)
            results.append(result)
            if result["status"] != "TASK_CREATED":
                break
            # A prepared task must be executed and reviewed before scheduling
            # another one. The scheduler itself does not yet run the agent.
            break
        last_status=results[-1]["status"] if results else "NO_WORK"
        # This scheduler currently prepares a governed researcher task; it does
        # not execute an agent/model run or finish evidence review. Never label
        # task preparation as a completed research run.
        if last_status == "TASK_CREATED":
            status="TASKS_PREPARED"
        elif last_status == "BLOCKED_NO_SOURCES":
            status="BLOCKED_NO_SOURCES"
        else:
            status=last_status
        return {"status":status,"cycles":len(results),"results":results}

    def run_and_execute_once(self, project_id, actor="autonomous-research"):
        """Prepare and execute exactly one bounded research task, stopping at review gates."""
        prepared=self.schedule_once(project_id,actor=actor)
        if prepared.get("status") != "TASK_CREATED":
            return prepared
        task=prepared.get("task") or {}
        task_id=task.get("id")
        if not task_id:
            raise RuntimeError("scheduler created a research task without an ID")

        # Execute only the task this research run prepared; never accidentally run
        # a different, higher-priority project task.
        from app.orchestrator import CompanyOrchestrator
        execution=CompanyOrchestrator(self.db).execute_next(project_id,task_id=task_id)
        execution_status=str(execution.get("status") or "UNKNOWN")
        if execution_status in {"WAITING_FOR_OUTPUT_REVIEW","WAITING_FOR_APPROVAL"}:
            run_status=execution_status
        elif execution_status in {"EXECUTION_FAILED","EXECUTION_PREFLIGHT_FAILED","EXECUTION_RECORD_MISSING","FAILED"}:
            run_status=execution_status
        elif execution_status=="COMPLETED":
            # Task completion is not equivalent to scientific completion.
            run_status="AGENT_EXECUTION_RECORDED"
        else:
            run_status=execution_status
        self.db.execute(
            "UPDATE autonomous_research_runs SET status=?,updated_at=? WHERE id=?",
            (run_status,now(),prepared["run_id"]),
        )
        return {
            **prepared,
            "status":run_status,
            "execution":execution,
            "research_completed":False,
            "next_gate":(
                "independent evidence review"
                if execution_status=="WAITING_FOR_OUTPUT_REVIEW"
                else "inspect execution result and satisfy the applicable scientific review gates"
            ),
        }
