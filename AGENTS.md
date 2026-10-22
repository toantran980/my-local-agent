# AGENTS.md

Context for AI agents working in this repo. Human-facing docs live in
[README.md](README.md), [QUICKSTART.md](QUICKSTART.md), and
[PROJECTS.md](PROJECTS.md).

## What this is

Self-hosted local AI agent stack on an NVIDIA RTX 5080 (16GB) via WSL2 + Docker
Desktop. Ollama for inference, Open WebUI for chat, an MCP bridge for tools, and
a nightly triage job.

## Layout

| Path | Contents |
| --- | --- |
| `agent_cli.py` | Terminal agent: `ask` / `plan` / `agent` modes |
| `mcp/local_ops.py` | MCP server: git, GPU, system, eval introspection |
| `mcp/projects_ops.py` | MCP server: read-only project file access |
| `mcp/rag_ops.py` | MCP server: local RAG (Ollama embeddings + SQLite index) |
| `mcpo/` | MCP→OpenAPI bridge image + `config.json` (5 servers) |
| `scripts/` | smoke test, eval harness, nightly triage, cron, audit viewer |
| `eval/` | `cases/*.json`, `fixtures/`, `rag/` (retrieval eval), `history.jsonl` |
| `tests/` | pytest suite for `agent_cli.py` and `rag_ops.py` |
| `reports/` | Nightly triage output, `YYYY-MM-DD.md` (gitignored); mounted read-only into `mcpo` at `/data/reports` |
| `.agent/audit/` | Per-run JSONL audit trail (gitignored) |
| `workspace/` | Agent file sandbox, the only writable MCP mount |
| `docs/` | Framework analysis, not operational docs |

## Commands

```bash
make up / down / ps / logs      # stack lifecycle
make smoke                      # health check: ollama, mcpo, GPU residency, agent_cli
make gpu                        # model VRAM residency
make eval                       # 7-case eval suite + summary
make eval-history               # pass-rate trend
make eval-rag                   # retrieval hit@1 for rag_ops
make cron-install / cron-run    # nightly triage
make agent-ask 'question'       # read-only
make agent-apply 'task'         # writes under --repo

bash scripts/smoke-test.sh      # same checks without make
python3 -m pytest -q           # unit tests
ruff check . && shellcheck scripts/*.sh    # what CI runs
```

Direct equivalents: `ollama ps` for GPU residency and `ollama pull qwen3:8b` to
fetch a model (prefix with `docker exec local_ollama` only when using the
opt-in Ollama container).

## Environment

`OLLAMA_URL` (default `http://localhost:11434`), `AGENT_MODEL` and
`NIGHTLY_MODEL` (default `qwen3:8b`), `CRON_HOUR` / `CRON_MIN` (17 / 0),
`DRAFT_PR` and `GH_REPO` for draft PRs, `ADMIN_USER` / `ADMIN_PASSWORD` for the
auth proxy. `AGENT_MEMORY=0` disables run memory (`AGENT_MEMORY_DIR` relocates it),
`RAG_URL` points the CLI and nightly job at mcpo's `rag_ops`, `HYBRID_WEIGHT` tunes
retrieval (0 = vector only), and `QUERY_REWRITE=1` optionally rewrites search queries.
`agent_cli.py --auto-route` opts into easy/hard local model routing; interactive
history is summarized above `AGENT_HISTORY_TOKEN_BUDGET` (default 5000 estimated tokens).
Full table in [README.md](README.md#configuration).

## Constraints

Do not violate these — they are enforced in code:

- Services bind to `127.0.0.1` only. Ollama's API has no auth.
- `agent_cli.py` writes only under `--repo`, and only with `--apply`.
- Max 10 tool steps per run (`MAX_TOOL_STEPS` in `agent_cli.py`).
- 32KB read cap (`MAX_FILE_BYTES`); 1MB write cap.
- Sensitive paths (`.env`, keys, certs) are blocked from read and write.
- Credentials are redacted before anything is written to the audit log.
- `projects_ops` is read-only; `/projects`, `/configs`, `/logs` mount `:ro`.
- `rag_ops` never writes to sources; it only writes its index to `/workspace/.rag`
  and skips sensitive files.
- Agent memory (`workspace/memory/`) is redacted like the audit log; keep it inside
  `workspace/`, the only writable sandbox.
- `mcpo/Dockerfile` pins `fastapi<0.142`; newer FastAPI breaks mcpo 0.0.20 at startup.

## VRAM (16GB card)

`qwen3:8b` ~7GB at 16k context (default), `qwen3:14b` ~11GB and fits, 30B does
not. Weights + KV + 1GB headroom must stay under ~14.5GB.
`OLLAMA_CONTEXT_LENGTH=16384` is the compose default and the KV ceiling.

## Conventions

- `ruff` with `line-length = 100`, `target-version = "py314"`, double quotes.
- `agent_cli.py` is deliberately dependency-free (stdlib `urllib` only). Do not
  add third-party imports to it.
- `scripts/nightly-triage.py` is stdlib-only for the same reason.
- Eval cases are cwd-independent: fixture contents are inlined into the prompt.
- The eval harness talks to Ollama directly rather than shelling out to
  `opencode run`, because the `opencode` on PATH here is the Desktop app binary
  and emits no stdout when headless.
