"""Local autonomous literature-discovery scheduler for HDS.

Runs one bounded, source-grounded research pass per interval through the local API.
It never approves, publishes, or promotes AI-generated claims.
"""
from __future__ import annotations

import logging
import os
import threading
import time
from itertools import cycle

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
    def __init__(self, base_url: str = "http://127.0.0.1:8000", interval_seconds: int = 4 * 60 * 60):
        self.base_url = base_url.rstrip("/")
        self.interval_seconds = max(900, int(interval_seconds))
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

    def _run(self) -> None:
        questions = cycle(QUESTIONS)
        # Wait briefly for Uvicorn to finish binding before the first local API call.
        if self._stop.wait(8):
            return
        while not self._stop.is_set():
            question = next(questions)
            try:
                self._run_one(question)
            except Exception:
                LOG.exception("Background research cycle failed")
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


def start_background_research() -> BackgroundResearchScheduler:
    interval = int(os.getenv("HDS_BACKGROUND_RESEARCH_INTERVAL_SECONDS", str(4 * 60 * 60)))
    scheduler = BackgroundResearchScheduler(interval_seconds=interval)
    scheduler.start()
    return scheduler
