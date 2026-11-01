# Run the HDS mentality research MVP locally

## What this MVP does
The dashboard can start a bounded research run from a mental-development question. When launched with the local launcher, HDS also starts a background scheduler that rotates through a curated set of mentality questions and runs one bounded literature pass every four hours. HDS searches PubMed and Crossref, stores available readable abstracts, passes the source packet to the configured local model, and records candidate claims, excerpts, analysis, limitations, and uncertainty. The dashboard's Autonomous research feed refreshes every five minutes and lists saved runs. Outputs remain unverified and require independent review.

## Get the correct code version
The research dashboard work is currently on the `research-first-run-audit` branch, not `main`. Clone that branch:
```bash
git clone --branch research-first-run-audit https://github.com/galflorentin100-sketch/human-development-science.git
cd human-development-science
```
If you already cloned the repository, run `git switch research-first-run-audit` and `git pull`.

## Requirements
- Python 3.12 or newer.
- Ollama installed and running locally.
- Enough RAM/VRAM for the selected model. The default is Qwen 2.5 7B; smaller models can be selected with `HDS_OLLAMA_MODEL`.
- Internet access for PubMed/Crossref discovery. Access to full texts depends on lawful availability; this first pass uses available abstracts.

## One-time setup
1. Install Ollama from its official website and start it.
2. In a terminal, download a model once, for example:
   ```bash
   ollama pull qwen2.5:7b
   ```
3. In the repository root, install Python dependencies:
   ```bash
   python -m pip install -r requirements.txt
   ```

## Start
With Ollama running:
```bash
python scripts/run_local_research.py
```
Open `http://127.0.0.1:8000`.

The launcher checks that Ollama responds and that the selected model is already installed. It starts the local background scheduler automatically: the first run begins shortly after startup, followed by one research pass every four hours. Set `HDS_BACKGROUND_RESEARCH_INTERVAL_SECONDS` to change the interval (minimum 15 minutes). The scheduler stops when the local process stops; it does not run while your computer is off. The launcher does not download models, use paid APIs, expose the server publicly, or change production settings.

## Change model
Set `HDS_OLLAMA_MODEL` before starting the launcher. Example:
```bash
# macOS/Linux
HDS_OLLAMA_MODEL=qwen2.5:7b python scripts/run_local_research.py

# Windows PowerShell
$env:HDS_OLLAMA_MODEL="qwen2.5:7b"
python scripts/run_local_research.py
```

## Run a mentality research question
In the HDS Mentality Research Lab panel, you can still start a manual question. For automatic work, simply leave the local launcher running. HDS rotates through research themes without requiring a prompt. The dashboard's Autonomous research feed shows the saved runs. Each pass:
1. creates an isolated research project and workspace;
2. searches PubMed and Crossref;
3. supplies readable abstracts to the researcher agent;
4. runs one bounded model pass;
5. displays source-grounded candidate claims and the model's analysis;
6. labels the output unverified and preserves the next independent-review action.

## Important scientific boundary
This is a research-discovery MVP, not an autonomous scientist. AI suggestions are hypotheses/candidate claims, not discoveries. Exact abstract excerpts must be checked against source records, study design and limitations must be reviewed, and no candidate becomes an accepted finding without the independent review workflow. A search that returns no readable abstracts or a model that cannot run will produce a visible blocked/error state rather than invented findings.

## Troubleshooting
- Ollama unreachable: start the Ollama app/service and retry.
- Model missing: run `ollama pull <model-name>`.
- No research abstracts: try a more focused or alternate query; PubMed/Crossref coverage is not exhaustive.
- Dashboard API 401/403: local development should allow the local founder identity; do not use this local launcher for production.
- Model too large: choose a smaller model and check the output quality; a smaller model may produce weaker extraction and synthesis.


## Governed follow-up question generation

After each bounded background research pass, the local scheduler calls
`POST /api/hds/research-loops/{run_id}/generate-followups`. The generator
currently uses explicit, persisted governance signals rather than claiming
open-ended AI discovery:

- conflicting evidence, completed replication records, and completed
  falsification challenges;
- limitations and uncertainty explicitly recorded in prior research syntheses;
- literature retrievals that completed with zero results, treated as a
  search-strategy problem rather than proof that no literature exists.

Generated questions are stored as `PROPOSED` in the project-scoped research
queue and shown in the dashboard. Repeated generation is designed to reuse
existing open questions. This process does not verify evidence, resolve
contradictions, approve a question, or promote a finding. Human review and the
existing scientific admission gates remain mandatory.

This is a deterministic first version of an adaptive research agenda. It is
not yet semantic cross-paper synthesis, systematic-review automation, or
validated contradiction detection across article abstracts/full texts.


## Descriptive project evidence map (first version)

A read-only endpoint, `GET /api/hds/projects/{project_id}/evidence-map`,
returns a claim-by-claim evidence map. It includes only evidence whose review
records currently resolve to `VERIFIED`, groups excerpts by their recorded
stance (`SUPPORTS`, `CONTRADICTS`, `NEUTRAL`), counts distinct source
records, and retains source IDs, titles, publication years, URLs, and excerpts.
Non-verified evidence is counted separately and excluded from the stance map.

The output labels mixed verified stances, multiple-source same-sided records,
limited verified records, and no verified evidence. These are descriptive
signals, not evidence grades. Two source records are not necessarily
independent studies. The map does not evaluate study design, bias, sample
quality, effect sizes, population differences, or causality. It does not
change claim status or promote findings. Treat it as a navigational aid for
human reviewers, not a scientific synthesis conclusion.
