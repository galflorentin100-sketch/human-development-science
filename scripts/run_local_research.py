"""Preflight and launch the local HDS mentality research dashboard.

Requires Ollama to be installed and running, with the configured model already pulled.
This script never downloads models or contacts a paid provider.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import httpx
import uvicorn

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    os.chdir(ROOT)
    os.environ.setdefault("COMPANY_OS_ENV", "development")
    os.environ.setdefault("HDS_MODEL_PROVIDER", "ollama")
    os.environ.setdefault("HDS_OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    os.environ.setdefault("HDS_OLLAMA_MODEL", "qwen2.5:7b")

    if os.environ["HDS_MODEL_PROVIDER"].strip().lower() != "ollama":
        print("This local launcher only supports Ollama. No paid provider will be started.")
        return 2

    base = os.environ["HDS_OLLAMA_BASE_URL"].rstrip("/")
    model = os.environ["HDS_OLLAMA_MODEL"].strip()
    try:
        response = httpx.get(base + "/api/tags", timeout=4.0)
        response.raise_for_status()
        models = response.json().get("models", [])
    except Exception as exc:
        print("Ollama is not reachable at " + base)
        print("Install/start Ollama, then run this launcher again. Details: " + str(exc))
        return 2

    available = {item.get("name", "") for item in models}
    if model not in available and not any(name.startswith(model + ":") for name in available):
        print("Required model is not installed: " + model)
        print("Run: ollama pull " + model)
        return 2

    print("Ollama ready. Model: " + model)
    print("Starting HDS dashboard at http://127.0.0.1:8000")
    print("Local development mode: no public network binding; no paid API provider.")
    print("Autonomous mentality research: one bounded literature pass every 4 hours.")
    print("The background researcher stops when this local process stops.")
    from app.background_research import start_background_research
    scheduler = start_background_research()
    try:
        uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=False)
    finally:
        scheduler.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
