# my-local-agent — Local Autonomous Triage Stack

A self-hosted, local-first AI agent stack running on NVIDIA RTX 5080 (16GB) via WSL2 + Docker Desktop.

## Quickstart

```bash
# 1. Start stack (one-time model pull ~5–6 GB)
wsl bash -lc 'cd "${MY_LOCAL_AGENT_ROOT:-$(pwd)}" && docker compose up -d --build'

# 2. Verify
wsl bash -lc 'cd "${MY_LOCAL_AGENT_ROOT:-$(pwd)}" && bash scripts/smoke-test.sh'
# Expect: SMOKE: PASS + GPU row (qwen3:8b on VRAM)

# 3. Chat
start http://localhost:3000
# or API: curl -s http://localhost:11434/v1/chat/completions -H "Content-Type: application/json" -d '{"model":"qwen3:8b","messages":[{"role":"user","content":"Hello"}]}'
```

---

## Scheduled Nightly Agent

```bash
# Install 5 PM daily cron (waits for Ollama, logs cleanly if Docker down)
wsl bash -lc 'cd "${MY_LOCAL_AGENT_ROOT:-$(pwd)}" && bash scripts/install-cron.sh'

# Run once now
wsl bash -lc 'cd "${MY_LOCAL_AGENT_ROOT:-$(ROOT)}" && bash scripts/run-nightly.sh'
```

Reports appear in `reports/YYYY-MM-DD.md`. Set `DRAFT_PR=1 GH_REPO=owner/repo` for draft PRs.

---

## Reliability Harness

```bash
wsl bash -lc 'cd "${MY_LOCAL_AGENT_ROOT:-$(pwd)}" && bash scripts/run-eval.sh && python3 scripts/eval-summary.py'
# Expect: 6/6 passed
```

---

## Architecture

| Service | Image | Port | Purpose |
|---------|-------|------|---------|
| Ollama | `ollama/ollama:latest` | 11434 | Local LLM (qwen3:8b, 100% VRAM) |
| mcpo | `my-local-agent-mcpo` | 8000 | MCP→OpenAPI bridge |
| Open WebUI | `ghcr.io/open-webui/open-webui:main` | 3000 | Chat UI |
| auth_proxy | `caddy:latest` | 8443 | Auth proxy (opt-in) |
| vllm | `vllm/vllm-openai:latest` | 8001 | High-throughput (opt-in) |

---

## MCP Tools (via mcpo)

| Tool | Purpose |
|------|---------|
| `filesystem` | Read/write in `/workspace` |
| `fetch` | HTTP requests |
| `local_ops` | `git_status`, `grep`, `gpu_status`, `models_list`, `projects_overview`, `configs_overview`, `system_status`, `sandbox_files`, `eval_history` |
| `projects_ops` | Safe project access: `list_projects`, `read_file`, `search`, `get_structure` |

---

## Requirements

- Windows 10/11 + **Docker Desktop** (WSL2 backend)
- NVIDIA RTX 5080 (16GB) + Windows GPU driver
- WSL2 distro (Ubuntu 26.04 recommended)
- `wsl` command in PATH

---

## Portable Paths

Set `MY_LOCAL_AGENT_ROOT` to your repo root (WSL path):

```bash
export MY_LOCAL_AGENT_ROOT="/mnt/c/Users/yourname/my-local-agent"
# or auto-detect:
export MY_LOCAL_AGENT_ROOT="$(pwd)"
```

All commands use `${MY_LOCAL_AGENT_ROOT:-$(pwd)}` — no hardcoded paths.

---

## GPU Verification

```bash
# Inside WSL2
nvidia-smi
# Then inside Docker:
docker run --rm --gpus all nvidia/cuda:12.8.0-runtime-ubuntu24.04 nvidia-smi
```

If Docker test fails, register NVIDIA runtime:
```bash
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
sudo apt-get update && sudo apt-get install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
# Fully quit & relaunch Docker Desktop (Windows)
```

---

## Optional Profiles

```bash
# Auth proxy (Caddy + basic auth + TLS)
docker compose --profile auth up -d auth_proxy
# Set ADMIN_USER / ADMIN_PASSWORD in .env first

# vLLM (high-throughput, AWQ model)
docker compose --profile vllm up -d vllm
# Endpoint: http://localhost:8001/v1
```

---

## Project Access (projects_ops)

1. `./setup-projects.sh` (creates `~/projects`, `~/configs`, `~/logs`)
2. `docker compose up -d --force-recreate mcpo`
3. Add `projects_ops` in Open WebUI: `http://mcpo:8000/projects_ops`

Tools: `list_projects`, `read_file`, `search`, `get_structure` — all read-only, path-safe.

---

## Files

| File | Purpose |
|------|---------|
| `docker-compose.yml` | Stack definition |
| `scripts/smoke-test.sh` | Health check (Ollama, mcpo, GPU) |
| `scripts/run-eval.sh` | Eval harness (6 cases) |
| `scripts/nightly-triage.py` | Nightly agent |
| `scripts/run-nightly.sh` | Cron wrapper (waits for Ollama) |
| `scripts/install-cron.sh` | Installs 5 PM cron |
| `agent_cli.py` | Interactive Ask/Plan/Agent CLI |
| `eval/cases/*.json` | Eval test cases |
| `eval/fixtures/` | Test fixtures |
| `reports/` | Nightly reports |
| `Makefile` | Shortcuts (`make up`, `make eval`, `make cron-run`, etc.) |

---


## Running the Agent (Linux/WSL2 Terminal)

```bash
# Start stack
docker compose -f docker-compose.ci.yml up -d

# Pull model (if not already)
curl -s http://localhost:11434/api/pull -d '{"name": "qwen3:0.6b"}"

# Ask mode (read-only)
python agent_cli.py ask "What is 2+2?"

# Plan mode
python agent_cli.py plan "Add health checks"

# Agent mode (dry-run)
python agent_cli.py agent "Fix the syntax error"

# Agent mode with --apply (writes files after confirmation)
python agent_cli.py agent --apply "Fix the syntax error in test_failing.py"

# Interactive mode
python agent_cli.py agent
```

## License


MIT — local-first, no cloud dependencies.