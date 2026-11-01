# Workflows

Commands and defaults below describe `my-local-agent`. Inspect the current repository before applying them elsewhere or assuming configuration has not changed.

## Start the stack

The documented Windows setup uses Docker Desktop with the WSL2 backend. Run Docker and Python commands in WSL2, from the repository root:

```bash
docker compose up -d --build
bash scripts/smoke-test.sh
```

The smoke test checks Ollama, a chat round trip, mcpo tools, model VRAM residency, and `agent_cli.py ask`. Require `SMOKE: PASS`; a missing GPU row means the model may not yet be loaded on the GPU.

When using the skill outside this repository, its included lightweight diagnostic checks Ollama and mcpo without generating a completion:

```bash
python3 scripts/check_local_stack.py
python3 scripts/check_local_stack.py --model qwen3:8b
```

It reports installed and loaded models, but an unloaded model is informational; pass `--model` to require a specific installed model. This does not replace the full smoke test below.

For Windows-hosted command invocation from PowerShell, the documented wrapper is:

```powershell
wsl bash -lc 'cd "${MY_LOCAL_AGENT_ROOT:-$(pwd)}" && docker compose up -d --build'
wsl bash -lc 'cd "${MY_LOCAL_AGENT_ROOT:-$(pwd)}" && bash scripts/smoke-test.sh'
```

`make` targets are available only in an environment where `make` is installed, such as WSL2; they are not native PowerShell commands.

## Use agent modes

From WSL2 at the repository root:

```bash
python3 agent_cli.py ask "What does this repository do?"
python3 agent_cli.py plan "Add health checks"
python3 agent_cli.py agent "Fix the syntax error"                 # dry run
python3 agent_cli.py agent --apply "Fix the syntax error"         # apply requires confirmation
python3 agent_cli.py agent --plan-first --split-models "Implement a feature"
```

- **Ask** answers questions; **Plan** develops a plan; neither writes files.
- **Agent** proposes changes in dry-run mode. `--apply` permits writes under `--repo` and still requires explicit confirmation.
- `--plan-first` plans before execution and can replan once after test failure. `--split-models` uses configured planner/executor models; verify model availability and any fallback message.
- For an agent code change, inspect its proposed files, apply only the requested scope, then run focused tests and relevant repository checks.

## MCP and project access

mcpo exposes configured MCP servers to HTTP/OpenAPI consumers on `127.0.0.1:8000`. Check `mcpo/config.json` and the Compose mounts to see which tools are actually enabled.

External project/config/log access is opt-in. The `projects_ops` server is read-only and its mounts should remain `:ro`. Follow `PROJECTS.md` to enable it; do not add broad or writable host mounts as a shortcut.

## Local RAG

`rag_ops` indexes eligible local files for semantic retrieval. Source files are read-only; its SQLite index belongs under `/workspace/.rag`. Sensitive files and excluded runtime/build directories are skipped.

```bash
ollama pull nomic-embed-text
python3 scripts/eval-rag.py
```

For indexing/search endpoints, settings such as `HYBRID_WEIGHT`, or query rewriting, inspect `docs/RAG.md` and the live `mcpo/config.json`. Re-index or evaluate after changing chunking or retrieval behavior.

## Tests and evaluations

Choose validation that measures the requested behavior:

```bash
python3 -m pytest -q tests
ruff check .
shellcheck scripts/*.sh
bash scripts/run-eval.sh
python3 scripts/eval-summary.py
python3 scripts/eval-rag.py
```

The normal evaluation suite exercises agent behaviors. RAG evaluation measures retrieval. Check each tool's exit status and reported counts; a successful command launch alone is not proof of success.

## Nightly triage

The repository's nightly triage writes reports under `reports/` and telemetry there. Inspect `scripts/nightly-triage.py` and `docs/CONFIGURATION.md` before scheduling or enabling optional draft PR behavior. Do not enable `DRAFT_PR` or change schedules without the user's request.

```bash
python3 scripts/nightly-triage.py
```

The cron installer and schedule are documented in `QUICKSTART.md`.
