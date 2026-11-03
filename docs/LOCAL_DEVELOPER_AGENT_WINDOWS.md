# Local HDS Developer Agent (Windows)

Separate from the research scheduler. A local Ollama model proposes one small
patch per cycle. The runner validates it, applies it on a dedicated branch,
runs pytest, and commits only if tests pass.

Safety:
- Requires a clean Git working tree.
- Starts from hds-local-developer-agent and creates/uses local branch hds-agent-work.
- Refuses main or any other branch.
- Only edits existing files in app/, tests/, scripts/, docs/.
- No deletion, rename, new dependencies, secrets, workflows or model-supplied shell commands.
- Runs only python -m pytest -q.
- Commits locally; never pushes, merges, deploys or spends money.
- Logs/reports are outside the repository under %LOCALAPPDATA%\HDS.

Setup in PowerShell:
1. Install Git for Windows, Python 3.12+, and Ollama.
2. Clone this branch:
   git clone --branch hds-local-developer-agent https://github.com/galflorentin100-sketch/human-development-science.git
   cd human-development-science
3. Install dependencies: py -m pip install -r requirements.txt
4. Start Ollama and download model once: ollama pull qwen2.5:7b
5. Verify clean tree: git status --short

Test one cycle:
   py scripts/run_local_developer_agent.py --once

Run overnight:
   py scripts/run_local_developer_agent.py --interval-minutes 45

Keep PC plugged in and awake. In Windows Settings > System > Power & battery >
Screen and sleep, set sleep to Never while plugged in. Display may turn off.
Stop the process with Ctrl+C.

Reports:
- %LOCALAPPDATA%\HDS\developer_agent.log
- %LOCALAPPDATA%\HDS\developer_agent_report.json
- %LOCALAPPDATA%\HDS\developer_agent_history.jsonl

This first version does not mark backlog tasks complete, push changes, or deploy.
Review local commits and test reports before publishing anything.
