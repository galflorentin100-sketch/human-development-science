"""Local autonomous literature-discovery scheduler for HDS.

Runs one bounded, source-grounded research pass per interval through the local API.
It never approves, publishes, or promotes AI-generated claims.
"""
from __future__ import annotations

import json
import logging
import os
import threading
from pathlib import Path

import httpx

LOG = logging.getLogger("hds.background_research")

QUESTIONS = (
    "Which psychological and behavioral processes contribute to the development and maintenance of self-discipline in adults?",
    "How do implementation intentions and planning strategies influence habit formation and goal attainment?",
    "What mechanisms support emotion regulation and resilience under everyday stress?",
    "How do self-efficacy, motivation, and feedback interact during long-term behavior change?",
    "Which learning and metacognitive strategies improve the transfer of knowledge into real-world capability?",
    "How do sleep, physical activity, and recovery relate to executive function and self-regulation?",
    "Which social and environmental factors support persistence, accountability, and prosocial leadership?",
)


class BackgroundResearchScheduler:
    def __init__(self, base_url: str = "http://127.0.0.1:8000", interval_seconds: int = 4 * 60 * 60, state_path: str | Path | None = None):
        self.base_url = base_url.rstrip("/")
        self.interval_seconds = max(900, int(interval_seconds))
        # Persist rotation so restarts do not always return to topic 1.
        self.state_path = Path(state_path or os.getenv("HDS_BACKGROUND_RESEARCH_STATE", ".hds_research_scheduler.json"))
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._run, name="hds-background-research", daemon=True)
        self._thread.start()
        LOG.info("Background research scheduler started; interval=%s seconds", self.interval_seconds)

    def stop(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)

    def _load_cursor(self) -> int:
        try:
            payload = json.loads(self.state_path.read_text(encoding="utf-8"))
            cursor = int(payload.get("next_question_index", 0))
            return cursor % len(QUESTIONS)
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return 0

    def _save_cursor(self, cursor: int) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.state_path.with_suffix(self.state_path.suffix + ".tmp")
        temporary.write_text(
            json.dumps({"next_question_index": cursor % len(QUESTIONS)}, ensure_ascii=False),
            encoding="utf-8",
        )
        temporary.replace(self.state_path)

    def _run(self) -> None:
        cursor = self._load_cursor()
        # Wait briefly for Uvicorn to finish binding before the first local API call.
        if self._stop.wait(8):
            return
        while not self._stop.is_set():
            question = QUESTIONS[cursor]
            try:
                self._run_one(question)
            except Exception:
                LOG.exception("Background research cycle failed; keeping the same question for retry")
            else:
                cursor = (cursor + 1) % len(QUESTIONS)
                try:
                    self._save_cursor(cursor)
                except OSError:
                    LOG.exception("Could not persist background research cursor")
            if self._stop.wait(self.interval_seconds):
                break

    def _run_one(self, question: str) -> None:
        timeout = httpx.Timeout(900.0, connect=5.0)
        with httpx.Client(base_url=self.base_url, timeout=timeout) as client:
            health = client.get("/health")
            health.raise_for_status()
            created = client.post("/api/hds/research-loops/bootstrap", json={"question": question})
            created.raise_for_status()
            run_id = created.json()["run"]["id"]
            LOG.info("Started background research run %s: %s", run_id, question)
            result = client.post(
                f"/api/hds/research-loops/{run_id}/run-first-pass",
                json={"query": question, "providers": ["pubmed", "crossref"], "limit": 20},
            )
            result.raise_for_status()
            payload = result.json()
            LOG.info(
                "Background research run %s finished: status=%s sources=%s",
                run_id,
                payload.get("status"),
                (payload.get("retrieval") or {}).get("result_count", 0),
            )
            # Scan only recorded, project-scoped governance signals for possible
            # follow-up questions. This never upgrades evidence or starts a study.
            try:
                followups = client.post(
                    f"/api/hds/research-loops/{run_id}/generate-followups"
                )
                followups.raise_for_status()
                proposed = len(followups.json().get("queue_items", []))
                LOG.info(
                    "Background research run %s generated %s advisory follow-up question(s)",
                    run_id,
                    proposed,
                )
            except Exception:
                LOG.exception(
                    "Follow-up question generation failed for run %s; research pass remains saved",
                    run_id,
                )


def start_background_research() -> BackgroundResearchScheduler:
    interval = int(os.getenv("HDS_BACKGROUND_RESEARCH_INTERVAL_SECONDS", str(4 * 60 * 60)))
    scheduler = BackgroundResearchScheduler(interval_seconds=interval)
    scheduler.start()
    return scheduler
