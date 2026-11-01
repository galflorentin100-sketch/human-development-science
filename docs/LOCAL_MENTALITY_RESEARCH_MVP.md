# Run the HDS mentality research MVP locally

## What this MVP does
The dashboard can start a bounded research run from a mental-development question. HDS searches PubMed and Crossref, stores available readable abstracts, passes the source packet to the configured model, and displays candidate claims, excerpts, analysis, limitations, and uncertainty. The output remains unverified and must be independently reviewed.

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
- Enough RAM/VRAM for the selected model. The default is Qwen 2.5 14B; smaller models can be selected with `HDS_OLLAMA_MODEL`.
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

The launcher checks that Ollama responds and that the selected model is already installed. It does not download models, use paid APIs, expose the server publicly, or change production settings.

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
In the HDS Mentality Research Lab panel, enter a question, choose a maximum retrieval count, and select Start research. The dashboard:
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
