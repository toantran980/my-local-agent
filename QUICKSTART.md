# Quickstart

The 60-second version of [README.md](README.md). Commands are copy-pasteable and
match what is actually in this repo.

**Prerequisites:** Windows 10/11, Docker Desktop running on the **WSL2** backend,
an NVIDIA GPU with a current driver, and `wsl` on your PATH. Everything else comes
from the compose file.

**Portable paths.** Set `MY_LOCAL_AGENT_ROOT` to your repo root as a WSL path.
Every command below falls back to the current directory, so you can skip this if
you `cd` into the repo first.

```bash
export MY_LOCAL_AGENT_ROOT="/mnt/c/Users/yourname/my-local-agent"
```

---

## 1. Start the stack

```bash
wsl bash -lc 'cd "${MY_LOCAL_AGENT_ROOT:-$(pwd)}" && docker compose up -d --build'
```

| Service    | Port  | Purpose                                                                                                                |
| ---------- | ----- | ---------------------------------------------------------------------------------------------------------------------- |
| ollama     | 11434 | Inference. Default: the Ollama on your host. Docker container is opt-in: `--profile ollama` (quit host Ollama first) |
| open-webui | 3000  | Chat UI, opt-in: `docker compose --profile webui up -d open-webui`                                                   |
| mcpo       | 8000  | MCP → OpenAPI bridge (5 servers)                                                                                      |

The first run pulls a model (~5–6 GB). Later runs are instant. `make up` works
only where `make` is installed (inside WSL2, not native Windows PowerShell).
Port 11434 must be free: quit any Ollama app running on the Windows host first.

## 2. Verify

```bash
wsl bash -lc 'cd "${MY_LOCAL_AGENT_ROOT:-$(pwd)}" && bash scripts/smoke-test.sh'
```

Expect `SMOKE: PASS` plus a GPU row for `qwen3:8b` — that row is the proof the
model is on the GPU rather than the CPU. The script checks, in order: Ollama is
alive, a chat completion round-trips, mcpo exposes its tools, the model is
VRAM-resident, and `agent_cli.py ask` works.

## 3. Talk to it

```bash
# Chat UI (only if you enabled the webui profile)
start http://localhost:3000

# Or the OpenAI-compatible API from a Windows terminal
curl -s http://localhost:11434/v1/chat/completions -H "Content-Type: application/json" -d '{"model":"qwen3:8b","messages":[{"role":"user","content":"Hello"}]}'
```

From a WSL2 terminal, drive the agent directly:

```bash
python3 agent_cli.py ask "What is 2+2?"
python3 agent_cli.py plan "Add health checks"
python3 agent_cli.py agent "Fix the syntax error"          # dry-run
python3 agent_cli.py agent --apply "Fix the syntax error"  # writes under --repo
python3 agent_cli.py ask --stream "Summarize this repo"    # live tokens
python3 agent_cli.py agent --plan-first "Fix the syntax error"  # plan, execute, replan
python3 agent_cli.py agent --plan-first --split-models "Implement a feature"
```

`--split-models` uses `AGENT_PLANNER_MODEL` and `AGENT_EXECUTOR_MODEL` when those
models are installed; otherwise it reports the fallback to `--model`. The optional
semantic answer cache is off by default; set `AGENT_SEMANTIC_CACHE=1` to enable it
for tool-free Ask answers.

## 4. Nightly triage

```bash
wsl bash -lc 'cd "${MY_LOCAL_AGENT_ROOT:-$(pwd)}" && bash scripts/install-cron.sh'
wsl crontab -l | grep my-local-agent-nightly-triage
```

Installs a 5:00 PM daily entry (`CRON_HOUR` / `CRON_MIN` override). Reports land
in `reports/YYYY-MM-DD.md`. To get a draft PR per report as well, set `DRAFT_PR=1`
and `GH_REPO=owner/repo` before installing.

Prove it works without waiting for cron:

```bash
wsl bash -lc 'cd "${MY_LOCAL_AGENT_ROOT:-$(pwd)}" && python3 scripts/nightly-triage.py'
```

You should see the tool loop run (`git_status`, `grep`, `gpu_status`,
`models_list`) and a new report appear in `reports/`. The job also appends runtime
and GPU VRAM samples to the gitignored `reports/telemetry.jsonl`; anomaly alerts
are reported after at least five historical samples are available.

## 5. Evaluation

```bash
wsl bash -lc 'cd "${MY_LOCAL_AGENT_ROOT:-$(pwd)}" && bash scripts/run-eval.sh && python3 scripts/eval-summary.py'
```

Expect `7/7 passed` and a pass-rate trend from `eval/history.jsonl`. That number
is the project's reliability answer.

Retrieval check for the `rag_ops` server (pull the embedding model first):

```bash
ollama pull nomic-embed-text      # host Ollama (default setup)
python3 scripts/eval-rag.py
```

---

## Troubleshooting

| Symptom                       | Fix                                                                    |
| ----------------------------- | ---------------------------------------------------------------------- |
| `docker: command not found` | Start Docker Desktop; it provides the CLI in WSL2                      |
| `connection refused :11434` or `Ollama is not reachable` | Confirm `http://localhost:11434/api/tags` works inside WSL. If Ollama is Windows-hosted but bound only to `127.0.0.1`, WSL may not be able to reach it; use WSL mirrored networking or configure an `OLLAMA_URL` reachable from WSL without exposing Ollama to an untrusted network. |
| Eval reports empty replies | Start Ollama and confirm the requested model is listed by `/api/tags` from WSL; the eval script now stops before recording results if the endpoint/model is unavailable. |
| No GPU row in smoke test      | Model still pulling; re-run step 1                                     |
| WebUI won't load on :3000     | Cold start is slow; retry after ~1 min                                 |
| Cron reports not appearing    | `wsl bash -lc 'service cron start'`, then re-run `install-cron.sh` |

Full GPU troubleshooting, optional profiles, and the tool reference live in
[README.md](README.md). To grant the agent read access to your other project
directories, see [PROJECTS.md](PROJECTS.md).

All data stays local. Nothing in this project calls a cloud API.
