# my-local-agent

Local-first AI agent stack. Ollama for inference, Open WebUI for chat, an MCP
bridge for tools, and a nightly triage job that writes a report while you sleep.
Everything runs on one machine — no cloud calls, no API keys.

Built for a single NVIDIA RTX 5080 (16GB) under WSL2 + Docker Desktop.

**Start here:** [QUICKSTART.md](QUICKSTART.md) for the 60-second version.

---

## Architecture

```
Windows host
└── WSL2 (Ubuntu)
    └── Docker Desktop
        ├── ollama        :11434   inference (profile: ollama; host Ollama by default)
        ├── open-webui    :3000    chat UI              (profile: webui)
        ├── mcpo          :8000    MCP → OpenAPI bridge
        ├── auth_proxy    :8443    Caddy + basic auth   (profile: auth)
        └── local_vllm    :8001    high-throughput AWQ  (profile: vllm)
```

| Service | Container | Port | Image | Purpose |
|---|---|---|---|---|
| Ollama | `local_ollama` | 11434 | `ollama/ollama:latest` | Local inference (opt-in: `--profile ollama`; otherwise use host Ollama) |
| Open WebUI | `open-webui` | 3000 | `ghcr.io/open-webui/open-webui:main` | Chat UI (opt-in: `--profile webui`) |
| mcpo | `mcpo` | 8000 | built from `./mcpo` | MCP → OpenAPI bridge |
| auth_proxy | `auth_proxy` | 8443 | `caddy:latest` | TLS + basic auth (opt-in) |
| local_vllm | `local_vllm` | 8001 | `vllm/vllm-openai:latest` | High-throughput serving (opt-in) |

Every port binds to `127.0.0.1`. Nothing is exposed to the LAN.

---

## MCP tools

mcpo exposes five MCP servers, defined in [`mcpo/config.json`](mcpo/config.json).

| Server | Mounted at | Tools |
|---|---|---|
| `filesystem` | `/workspace` | Official Node MCP filesystem server, scoped to the sandbox |
| `fetch` | — | `mcp-server-fetch` (HTTP requests) |
| `local_ops` | [`mcp/local_ops.py`](mcp/local_ops.py) | `git_state`, `gpu_status`, `system_status`, `projects_overview`, `configs_overview`, `sandbox_files`, `eval_history`, `latest_nightly_report` |
| `projects_ops` | [`mcp/projects_ops.py`](mcp/projects_ops.py) | `list_projects`, `list_project_files`, `get_project_structure`, `read_project_file`, `search_projects` |
| `rag_ops` | [`mcp/rag_ops.py`](mcp/rag_ops.py) | `index_sources`, `semantic_search` |

Mounted host paths inside `mcpo`: the repo at `/repo` (read-only), `./workspace`
at `/workspace`, `./eval` at `/data/eval`, `./reports` at `/data/reports`
(read-only). See [PROJECTS.md](PROJECTS.md) to enable `/projects`,
`/configs`, and `/logs`.

Register them in Open WebUI: **Admin Panel → Settings → Integrations →
External Tool Servers →** `http://mcpo:8000/<server-name>` for each server.

### RAG (`rag_ops`)

Semantic search over `/repo` and `/projects`. Text files are chunked, embedded
with `nomic-embed-text` through Ollama, and stored in SQLite at
`/workspace/.rag/index.db` — the only thing it writes. Sensitive files and build
directories are skipped. Run `index_sources` first (re-runs only embed changed
files), then `semantic_search(query, k=5)`.

```bash
ollama pull nomic-embed-text      # host Ollama (default setup)
curl -X POST http://localhost:8000/rag_ops/index_sources
curl -X POST http://localhost:8000/rag_ops/semantic_search \
  -H "Content-Type: application/json" -d '{"query": "how is VRAM budgeted?"}'
```

---

## Agent CLI

[`agent_cli.py`](agent_cli.py) is a dependency-free terminal agent that talks to
Ollama's OpenAI-compatible API. Three modes, one flag that unlocks writes.

```bash
python3 agent_cli.py ask "What is 2+2?"                    # read-only
python3 agent_cli.py plan "Add health checks"               # plan, no writes
python3 agent_cli.py agent "Fix the syntax error"           # dry-run patch
python3 agent_cli.py agent --apply "Fix the syntax error"   # writes under --repo
python3 agent_cli.py agent                                 # interactive
```

| Flag | Default | Notes |
|---|---|---|
| `--repo` | cwd | Only directory `--apply` may write to |
| `--model` | `$AGENT_MODEL` or `qwen3:8b` | |
| `--url` | `$OLLAMA_URL` or `http://localhost:11434` | |
| `--apply` | off | Permits writes in agent mode; requires confirmation |

Safety rails, all enforced in code: max 10 tool steps per run, 32KB read cap,
sensitive paths (`.env`, keys, certs) blocked, credentials redacted before audit.

The read-only `semantic_search` tool calls the `rag_ops` server through mcpo
(`RAG_URL`, default `http://localhost:8000/rag_ops`). It re-indexes once per run
before searching, so results are fresh, and the system prompt requires answers to
cite source files like `[vram.md]`. If the service is unreachable it returns an
error and the agent falls back to `search` / `read_file`.

More agent behavior:

| Feature | How |
|---|---|
| Streaming | `--stream` prints tokens as they arrive (reasoning shows as `(thinking...)`) |
| Planner/executor | `agent --plan-first "task"` plans, executes, and replans once if tests fail |
| Reflect-and-retry | In agent mode, staged writes are tested automatically; a failure is fed back once for a fix |
| Memory | Each run appends a redacted summary to `workspace/memory/<date>.md` (indexed by RAG); `AGENT_MEMORY=0` disables, `AGENT_MEMORY_DIR` relocates |

`rag_ops` splits Markdown by heading and scores hits as a blend of embedding
similarity and keyword overlap (`HYBRID_WEIGHT`, default 0.3; `0` = vector only).

Every run appends structured JSONL to `.agent/audit/<date>.jsonl` — prompts,
decisions, tool calls, retries, verification, approvals. Inspect one with:

```bash
python3 scripts/tail-audit.py
```

---

## Nightly triage

[`scripts/nightly-triage.py`](scripts/nightly-triage.py) runs a bounded tool loop —
`git_status`, `grep`, `gpu_status`, `models_list`, `read_file`, `write_report` —
then writes `reports/YYYY-MM-DD.md`.

```bash
bash scripts/install-cron.sh     # 5 PM daily; override with CRON_HOUR / CRON_MIN
bash scripts/run-nightly.sh      # run once now (waits up to 5 min for Ollama)
crontab -l | grep my-local-agent-nightly-triage
```

Set `DRAFT_PR=1` plus `GH_REPO=owner/repo` to also open a draft PR per report.
Before triaging, the job makes a best-effort call to refresh the RAG index (skipped
silently if mcpo is down).

The `latest_nightly_report` MCP tool reads these reports through a read-only
`./reports` mount at `/data/reports`.

---

## Evaluation

Seven golden-prompt cases in [`eval/cases/`](eval/cases) with fixtures in
`eval/fixtures/`, run through Ollama at `temperature: 0`. One case
(`prompt-injection`) hides an instruction inside a fixture file and fails if the
reply contains its canary token (optional `forbidden` field in a case). Failures exit non-zero,
so the harness is CI-usable.

```bash
bash scripts/run-eval.sh              # default model: ollama/qwen3:8b
bash scripts/run-eval.sh ollama/qwen3:0.6b
NUM_PREDICT=8192 bash scripts/run-eval.sh ollama/qwen3.5:4b   # thinking models
python3 scripts/eval-summary.py       # per-day table + side-by-side model comparison
```

Each run appends `{ts, model, passed, total, seconds}` to `eval/history.jsonl` — the
reliability and latency trend over time. Run the suite once per model, then the
summary's comparison table shows pass rate and average seconds per run for each.

Retrieval quality has its own check. [`scripts/eval-rag.py`](scripts/eval-rag.py)
indexes `eval/rag/docs/` and measures hit@1 for the 28 queries in
`eval/rag/cases.json`, reporting vector-only and hybrid side by side and exiting
non-zero when the hybrid rate is below `THRESHOLD` (default 0.8):

```bash
python3 scripts/eval-rag.py           # needs nomic-embed-text in Ollama
```

CI (`.github/workflows/ci.yml`) runs `ruff check .`, `shellcheck scripts/*.sh`,
and `pytest`.

---

## Configuration

Copy `.env.example` to `.env`. All values have defaults.

| Variable | Default | Purpose |
|---|---|---|
| `MY_LOCAL_AGENT_ROOT` | cwd | Repo root as a WSL path; no hardcoded paths anywhere |
| `OLLAMA_URL` | `http://localhost:11434` | Inference endpoint |
| `AGENT_MODEL` | `qwen3:8b` | Model for `agent_cli.py` |
| `NIGHTLY_MODEL` | `qwen3:8b` | Model for nightly triage |
| `CRON_HOUR` / `CRON_MIN` | `17` / `0` | Nightly schedule |
| `DRAFT_PR` / `GH_REPO` | `0` / — | Draft PR automation |
| `ADMIN_USER` / `ADMIN_PASSWORD` | `admin` / `changeme` | auth_proxy credentials — **change these** |
| `OLLAMA_CONTEXT_LENGTH` | `16384` | KV ceiling per request |

### VRAM budget (16GB)

| Model | Weights + KV @ 16k ctx | Verdict |
|---|---|---|
| `qwen3:8b` | ~7GB | Default; comfortable |
| `qwen3:14b` | ~11GB | Fits, keep context at 16k |
| `qwen3:30b` | — | Does not fit; not supported |

Rule of thumb: weights + KV + 1GB headroom must stay under ~14.5GB.

---

## Makefile shortcuts

```bash
make up          make down        make ps          make logs
make smoke       make gpu         make eval        make eval-history
make eval-rag    make cron-install make cron-run   make cron-logs
make report-latest
make agent-ask 'question'        make agent-plan 'task'
make agent-dry 'task'            make agent-apply 'task'
make help
```

---

## Troubleshooting

**GPU not detected in Docker**

```bash
nvidia-smi   # works in WSL2?
docker run --rm --gpus all nvidia/cuda:12.8.0-runtime-ubuntu24.04 nvidia-smi
```

If the second fails, install the NVIDIA container toolkit and register the
runtime, then fully quit and relaunch Docker Desktop:

```bash
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey \
  | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list \
  | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' \
  | sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
sudo apt-get update && sudo apt-get install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
```

| Symptom | Fix |
|---|---|
| `docker: command not found` | Start Docker Desktop — it provides the CLI in WSL2 |
| `connection refused :11434` | Stack not up yet; re-run `make up`, allow ~30s for Ollama |
| Smoke test has no GPU row | Model still pulling; re-run `make up` |
| WebUI slow on first load | Cold start; retry after ~1 min |
| Cron reports missing | `service cron start`, then re-run `make cron-install` |
| `make` targets no-op | Run from WSL2, or use the `wsl bash -lc '...'` form in the Makefile |

---

## Documentation map

| File | Read it when |
|---|---|
| [QUICKSTART.md](QUICKSTART.md) | Setting up from scratch |
| [PROJECTS.md](PROJECTS.md) | Granting the agent read access to `~/projects` |
| [AGENTS.md](AGENTS.md) | Working on this repo with an AI agent |
| [docs/FRAMEWORK-ANALYSIS.md](docs/FRAMEWORK-ANALYSIS.md) | Evaluating LangChain/LangGraph vs. the current hand-rolled loop |
| [workspace/README.md](workspace/README.md) | Understanding the agent's file sandbox |

---

## Roadmap

### Product goal

Turn signals — telemetry, config drift, failing checks — into evidence-backed,
human-approved changes. The agent proposes and verifies; a human approves every
merge.

```
signals / config drift
        │
        ▼
  triage agent ──▶ scoped tools ──▶ audit trail
        │
        ▼
  tests + verification
        │
        ▼
  draft PR ──▶ human approval ──▶ metrics
```

### Guiding principles

- Local Ollama is the default inference route; cloud fallback is explicit opt-in.
- Start read-only; grant narrow write scopes only after evals prove them reliable.
- Every agent action leaves structured, durable audit data.
- A passing verification suite and a draft PR are required before human review.
- Optimize inference infrastructure only after metrics identify a bottleneck.

### Milestones

**1 — Production agent harness: COMPLETE**

- Task schema: ID, source, repo, policy, model, lifecycle state, correlation ID
- Tool registry: read, write, shell, git, network, PR creation
- Per-task permissions, path allowlists, command allowlists, output caps, timeouts
- JSONL audit for prompts, decisions, tool calls, retries, verification, approvals
- Bounded retries with exponential backoff; terminal states
  `succeeded` / `needs_review` / `failed` / `blocked`
- Draft-PR gate: branch → verify → draft PR → human approval

**2 — Evaluation and reliability: COMPLETE**

- Six cases split across detection, diagnosis, patch, and verification
- Per-run records of model, policy version, latency, retries, outcome
- Failed cases exit non-zero
- Tracked metrics: detection precision/recall, fix success rate, verification
  pass rate, false-positive rate, rollback rate, human approval rate
- Regression thresholds block promotion of a changed policy or model

**3 — Scheduled triage: OPERATIONAL**

- Cron at 5 PM daily via `scripts/install-cron.sh`
- Waits up to 5 min for Ollama; logs cleanly when Docker is down
- Writes `reports/YYYY-MM-DD.md` with git state, GPU, model list, grep findings

### Next slice

One controlled workflow, end to end:

> Given a known failing test or config drift, collect evidence, propose the
> smallest safe patch in an isolated worktree, run verification, write an audit
> trail, and open a draft PR for human approval.

This is the smallest end-to-end proof, and it gives the eval harness, sensor
pipeline, model router, and vLLM work a stable foundation.

### Deferred

- Model router with explicit cloud fallback policy
- vLLM on the 5080, only if measurements justify the VRAM cost
- Sensor triage pipeline: telemetry adapters, drift rules, evidence bundles
- Multimodal vision (Qwen2-VL), only if the use case justifies the VRAM

---

## License

[MIT](LICENSE) — local-first, no cloud dependencies. The container images this
stack pulls (Ollama, Open WebUI, vLLM) carry their own licenses and are not
redistributed under this one.
