# Local self-hosted agent (RTX 5080 + WSL2, no cloud LLM)

Shortest path to a **working** agent on your hardware: Ollama (inference, GPU)

+ Open WebUI (chat UI) + mcpo (MCP tools: filesystem, web fetch) + opencode
  (the actual agent runner, pointed at your local model). Everything runs in
  WSL2, published to Windows `localhost`.

```
Windows browser (http://localhost:3000)
        |
   WSL2  + Docker Desktop
        |
  open-webui <-> ollama (GPU, Qwen3) <-> on your RTX 5080, all local
        |            |
      mcpo           |
        |            |
  filesystem  +  fetch MCP   (Open WebUI bridges these to the model)
        |
  ./workspace (a dir on your machine the agent can read/write)
```

Why Ollama first and not vLLM: a 5080 is Blackwell `sm_120`. vLLM works, but
consumer-Blackwell support has needed source builds (`TORCH_CUDA_ARCH_LIST=12.0`),
kernel workarounds, and WSL2 2.7.0+ for CUDA graphs. Ollama ships a CUDA 12.8
runtime that just works, and on a single card the throughput gap to vLLM is
small (community measurements: Ollama ≈ 2-6% behind llama.cpp on dense models).
Start with Ollama. Do vLLM later, only if you need concurrent-serving
throughput. It is a bonus service behind the `--profile vllm` flag, not the path.

Model choice: **Qwen3 8B (default)** / **Qwen3 14B (when you want more
quality)**. Qwen3 is the best open ≤14B line for tool/function calling, and
both fit 16GB at Q4_K_M with headroom for KV cache. Skip 30B/32B+ - ~20GB+ at
Q4_K_M does not fit a 16GB card with useful context.

---

## Step 0 - Preflight (Windows host)

Blackwell needs a recent Windows driver (≥ 570; the 2026 releases are 590/610).
Old drivers cause the #1 failure below: Ollama silently falls back to CPU.

```powershell
# Windows, PowerShell
nvidia-smi                       # driver version column must be >= 570
wsl --version                    # WSL 2, kernel 6.x
wsl --update                     # if stale; pick up Blackwell dxgkrnl fixes
```

Optional RAM headroom for the WSL2 VM (it defaults to 50% of host RAM). If you
have 32GB+, this makes prompt buffering comfortable:

```powershell
# Windows: C:\Users\toant\.wslconfig
[wsl2]
memory=28GB
processors=12
swap=8GB
# then: wsl --shutdown
```

## Step 1 - Verify GPU passthrough

Inside WSL2 (your linux distro):

```bash
nvidia-smi
# SUCCESS: you see "NVIDIA GeForce RTX 5080", 16302MiB, a modern driver
# note: the driver version shown here IS your Windows driver - that is expected
```

Then GPU into Docker (this is the make-or-break check):

```bash
docker run --rm --gpus all nvidia/cuda:12.8.0-runtime-ubuntu24.04 nvidia-smi
# SUCCESS: the same RTX 5080 block prints inside the container
```

Errors like `could not select device driver "nvidia"` = the one-time toolkit
step below is missing. Docker Desktop 29.7 has the CLI support; it just needs
the runtime registered.

## Step 2 - One-time: register the NVIDIA runtime (only if Step 1 Docker test fails)

```bash
# WSL2 Ubuntu
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey \
  | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list \
  | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' \
  | sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

sudo apt-get update && sudo apt-get install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
```

Then **fully quit and relaunch Docker Desktop** (Windows) - do not rely on
`systemctl restart docker`, Docker Desktop ignores it. The toolbox can verify:

```bash
docker info | grep -i runtime    # expect: Runtimes: ... nvidia
# re-run the Step 1 docker test
```

Never install `cuda`, `cuda-drivers`, or `cuda-12-x` meta-packages inside WSL2.
They overwrite NVIDIA's `libcuda.so` stub and kill GPU access. You do not need
a CUDA toolkit at all for this stack.

## Step 3 - Bring up the stack

```bash
cd /home/toant/repos/my-local-agent   # this project, from WSL2
docker compose up -d --build
docker compose ps                     # 3 services: ollama, open-webui, mcpo
```

First run of `mcpo` needs internet to download the MCP server packages (one
time). Verify the pieces:

```bash
curl -s http://localhost:11434/api/tags          # -> {"models":[]} is fine
curl -s http://localhost:8000/openapi.json | head -c 200   # mcpo tool schema
docker logs open-webui | tail -5                 # no startup errors
```

## Step 4 - Pull the model, prove it's on the GPU

```bash
docker exec local_ollama ollama pull qwen3:8b    # ~5.2GB, Q4_K_M
docker exec local_ollama ollama run qwen3:8b "say hello"   # first load is slow
```

Then, in a second terminal:

```bash
docker exec local_ollama ollama ps
# SUCCESS:  NAME      ID      SIZE  PROCESSOR  UNTIL
#           qwen3:8b  ...     6.xGB 100% GPU, 0% CPU ...
```

`0% CPU` next to `100% GPU` is the whole point. If you see CPU utilization,
see Failure Point #1.

Full API check (the same call your tools will make):

```bash
curl -s http://localhost:11434/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"qwen3:8b","messages":[{"role":"user","content":"1+1?"}],"stream":false}'
# SUCCESS: JSON with choices[0].message.content = "2" (or similar)
```

## Step 5 - Chat from your Windows browser

Open **http://localhost:3000**. Sign up (first account = admin), pick
`qwen3:8b` in the model picker, chat. This is your CSI from the prompt: same
GPU, Web UI, no new concepts. WSL2/Docker Desktop forwards `localhost` to
Windows automatically - no config needed.

## Step 6 - Give the model tools (MCP)

Open WebUI can only talk to HTTP tool servers, so `mcpo` wraps the stdio MCP
servers (`filesystem`, `fetch`) into OpenAPI endpoints. In the UI:

1. **Admin Panel -> Settings -> Integrations -> External Tool Servers**
2. Add three servers, type must be **OpenAPI**:
   - Name: `filesystem`, URL: `http://mcpo:8000/filesystem`
   - Name: `fetch`, URL: `http://mcpo:8000/fetch`
   - Name: `local_ops`, URL: `http://mcpo:8000/local_ops`  <- yours, `mcp/local_ops.py`
|                                         | **Your MCP server**: safe project directory access with security controls             |
   - (No API key. Container name `mcpo` is resolved by the open-webui backend.)
3. In a chat: enable the tools button (top-right "tools" / parenthesis icon),
   tick `filesystem` and `fetch`, then give the model a tool task.

Verify the tools exist before chatting:

```bash
curl -s http://localhost:8000/openapi.json \
  | python3 -c "import json,sys; print(list(json.load(sys.stdin)['paths']))"
# SUCCESS: /filesystem, /fetch, and /local_ops
```

Sandbox note: `filesystem` can only touch `./workspace` (mapped to `/workspace`
in mcpo). The agent edits real files there and nothing outside it. Add a
keyword web-search MCP over your own SearXNG container later if you want
search without any external API - out of scope here to keep the default lean.

## Step 7 - The actual agent: opencode on your local model

Open WebUI is a chat UI. For an agent that operates a codebase with
read/edit/shell/glob tools natively, point **opencode** at the local model
(`opencode.json` in this project does exactly that: Ollama provider, local
`small_model` for titles, sharing disabled - zero cloud calls).

```bash
curl -fsSL https://opencode.ai/install | bash
opencode models | grep ollama        # -> ollama/qwen3:8b  ollama/qwen3:14b
opencode                           # interactive TUI against local qwen3:8b
opencode run "summarize this repo" # one-shot, scriptable
```

Scheduled, unsupervised job (the "agent works while you sleep" demo):

```bash
chmod +x scripts/install-cron.sh
|||| `setup-projects.sh`                                          | Creates project directories on Windows filesystem for homelab access                    |
|||| `test-projects-ops.sh`                                       | Tests the projects_ops MCP server functionality                                          |
./scripts/install-cron.sh                    # installs cron entry for 2am daily runs (default CRON_HOUR=2)
|||| `setup-projects.sh`                                          | Creates project directories on Windows filesystem for homelab access                    |
|||| `test-projects-ops.sh`                                       | Tests the projects_ops MCP server functionality                                          |
```

Once a job builds a report, it is worth 20 chat sessions on a resume. Measure
reliability before you let anything unsupervised touch a pipeline:

```bash
./scripts/run-eval.sh               # runs eval/cases/*.json, prints pass rate
./scripts/eval-summary.py           # shows the pass-rate trend over time
```

### Ask, Plan, and Agent modes from the terminal

`agent_cli.py` is a small local-first terminal interface for the three common
agent workflows. It calls Ollama directly; Ask and Plan can inspect files but
cannot write them. Agent starts in dry-run mode, so `--apply` is an explicit
write approval. Each run appends an audit record under `.agent/audit/`, and
Plan saves its result under `.agent/plans/`.

```bash
python3 agent_cli.py ask "What does this repository do?"
python3 agent_cli.py plan "Add a health check to every Compose service"
python3 agent_cli.py agent "Find the syntax error and propose the smallest fix"
python3 agent_cli.py agent --apply "Fix the syntax error and run the tests"
```

Use `--repo /path/to/repo` to operate on another local repository. Agent mode
only exposes a fixed test command (`python -m pytest -q`) and file writes
restricted to that selected repository; it does not grant arbitrary shell or
network access. Agent writes are staged as a unified diff and require a `y`
confirmation after `--apply`; without `--apply`, the diff is preview-only.

Omit the task to use an interactive session with short-term conversation
context. Commands are `/mode ask`, `/mode plan`, `/mode agent`, `/status`, and
`/quit`.

```bash
python3 agent_cli.py ask
```

For Agent-mode test verification, create a Linux-only virtual environment in
the repository and install `pytest` once:

```bash
cd ~/repos/my-local-agent
python3 -m venv .agent-venv
.agent-venv/bin/python -m pip install pytest
```

Eval cases now include real-failure detection, not just trivia: a syntax error
(`find-syntax-error`), a broken compose file (`compose-misconfig`), a failing
pytest (`find-failing-test`) - all against `eval/fixtures/`, offline and
repeatable. Each run appends to `eval/history.jsonl`.

## Step 8 - vLLM (optional, only after the above works)

**Why not to start here:** on a 5080 in WSL2, vLLM needs a build/kernel setup
that Ollama skips. If you want it anyway:

```bash
wsl --update && wsl --shutdown      # CUDA graphs on Blackwell need WSL2 2.7.0+
docker compose --profile vllm up -d vllm     # pulls ~7GB image + Qwen3-14B-AWQ
curl -s http://localhost:8001/v1/models       # expect JSON listing the model
```

If it fails to start on `sm_120`:

- Keep `VLLM_DISABLED_KERNELS` set (already in compose) - it disables the
  FP8 GEMM kernels that hang on consumer Blackwell.
- Prebuilt wheels have historically missed sm_120 kernels; the fallback is a
  source build with `TORCH_CUDA_ARCH_LIST=12.0` on CUDA 12.8+. This is the
  point where people spend an afternoon - that is why Ollama is the default.

Then point Open WebUI or opencode at it by adding an OpenAI-compatible
provider (`http://vllm:8000/v1` inside the compose network) and register
Qwen3 as the model.

## Step 9 - Networking

- **Local:** already done. `localhost:3000` (UI), `localhost:11434` (Ollama
  API), `localhost:8000` (tools). All bound to 127.0.0.1 on purpose - the
  Ollama API has **no authentication**.
- **Remote (optional):** use Tailscale, never a port forward.
  Install on **Windows**, `tailscale up`, then:

  ```powershell
  tailscale serve --bg 3000        # gives you https://<machine>.ts.net -> Open WebUI
  ```

  Do not `tailscale serve` 11434 or 8000 or 8001 - raw model/API endpoints
  exposed to your tailnet are an open door.

---

## VRAM budget (16GB, approx - Q4_K_M weights + q8_0 KV cache + ~1GB overhead)

| Model (Ollama tag)  | Weights | KV @ 8k | KV @ 16k | Est. total @16k | Fits 16GB?                                        |
| ------------------- | ------- | ------- | -------- | --------------- | ------------------------------------------------- |
| qwen3:0.6b          | 0.6GB   | 0.1GB   | 0.2GB    | ~1.8GB          | Deep comfort. GPU sanity check                    |
| qwen3:4b            | 2.8GB   | 0.3GB   | 0.5GB    | ~4.3GB          | Comfort                                           |
| **qwen3:8b**  | 5.2GB   | 0.4GB   | 0.7GB    | **~7GB**  | **Default. Also runs 32k ctx (~9GB)**       |
| **qwen3:14b** | 9.4GB   | 0.4GB   | 0.7GB    | **~11GB** | **Yes. Max for agent work. Cap ctx <= 32k** |
| qwen3:30b-a3b       | ~14GB   | 0.3GB   | 0.5GB    | ~15.5GB         | Barely, tiny KV headroom only. Not recommended    |
| qwen3:32b           | ~20GB   | -       | -        | -               | No. Does not fit - do not try                     |

Rule of thumb on 16GB: weights + KV + 1GB headroom must stay under ~14.5GB.
If a model OOMs under load, lower `OLLAMA_CONTEXT_LENGTH`, or pick one size
down - dropping to Q3_K_M to squeeze a bigger model degrades tool-calling
accuracy before it degrades chat quality.

## 5-minute smoke test

```bash
./scripts/smoke-test.sh            # 4 automated checks, ends "SMOKE: PASS"
```

Then the human half, in the browser:

1. Open http://localhost:3000 -> chat with `qwen3:8b`: "3*9?" -> answer.
2. Enable the `filesystem` tool, ask: "Create `notes.txt` in /workspace
   containing 'hello from agent', then read it back."
3. Check on the host (WSL2): `cat workspace/notes.txt` -> "hello from agent".

The model decided to call a tool, mcpo executed it on your filesystem, and
the result came back into chat. That is a working agent.

## 2-3 most likely failure points on THIS hardware (sm_120 + WSL2)

1. **Old Windows driver -> Ollama silently runs on CPU.**
   `ollama ps` shows `0% GPU / 100% CPU`, or 5 tok/s on an 8B. Fix: update the
   Windows NVIDIA driver to >= 570 (current = 590/610), restart Windows
   explicitly if WSL2 still caches the old stub (`wsl --shutdown`).
2. **`could not select device driver "nvidia"` on `docker run --gpus all`.**
   The container runtime isn't registered with the Docker Desktop engine.
   Fix: install `nvidia-container-toolkit` (Step 2), run
   `sudo nvidia-ctk runtime configure --runtime=docker`, then **fully quit and
   relaunch Docker Desktop**. Verify: `docker info | grep -i runtime`.
3. **Installed `cuda`/`cuda-drivers` inside WSL2 at some point.**
   Overwrites the `libcuda.so` stub; GPU dies even though nvidia-smi once
   worked. Fix: determine WSL2 is broken via `wsl --shutdown` + reinstall of
   the distro (destructive but quick) - or avoid ever installing those
   packages. Only `cuda-toolkit-13-x` is safe, and you don't need it here.
4. **vLLM on 5080 (only if you chase Step 8).** Prebuilt wheels may lack
   sm_120 kernels; FP8 GEMM can hang; FP8 tensor cores are not exposed through
   WSL2's virtualization layer (so AWQ > FP8 here). Fixes: the compose already
   sets the kernel disables; otherwise source-build with
   `TORCH_CUDA_ARCH_LIST=12.0`. This is the documented reason people run
   Ollama on 50-series cards.

## Closing the gaps

The stack above is the serving part. These three artifacts are the part that
reads like "I own the agent layer", because they are the harness, the
measurement, and the autonomy:

1. **Real scheduled work, with a month of history.** `nightly-triage.sh`
   archives one dated report per day in `agent-reports/` and a rolling
   `index.json`. Let it run for a month via cron and you have one artifact
   that shows the agent working nightly - not a demo. Optional PR-gated
   autonomy: `DRAFT_PR=1 GH_REPO=you/yourrepo` makes the agent open a draft
   PR you approve before merge.
2. **Measurable reliability.** The eval harness doubles as a regression test
   for the agent: real failure cases + a pass rate you can chart
   (`eval-summary.py` reads `eval/history.jsonl`). Before trusting the agent
   unsupervised, run it on the cases that actually break your setup and watch
   the rate. That is the "9/10, only false positives after tests fail" number.
3. **An MCP server you wrote.** `mcp/local_ops.py` is a working MCP server
|                                         | **Your MCP server**: safe project directory access with security controls             |
   (stdlib, no cloud) exposing the agent's own operations: git state,
   latest nightly report, eval trend, sandbox contents, and current VRAM via
   Ollama. It is wired into mcpo (`http://mcpo:8000/local_ops`) and is the
   sort of tool you'd extend to wrap a real sensor/fleet API.

Point at any of these during a conversation and you can answer "what have
you shipped" with something the interviewer cannot hand-wave away.

## What each file does

| File                                                           | Purpose                                                                                  |
| -------------------------------------------------------------- | ---------------------------------------------------------------------------------------- |
| `docker-compose.yml`                                         | Ollama + Open WebUI + mcpo (default); vLLM and the old terminal chat behind`--profile` |
| `mcpo/`                                                      | Small image that bridges stdio MCP servers -> OpenAPI for Open WebUI                     |
| `mcpo/config.json`                                           | Declares filesystem, fetch, local_ops, and projects_ops MCP servers
| `mcp/local_ops.py`                                           | **Your MCP server**: git state, nightly reports, eval history, sandbox, VRAM       |
| `mcp/projects_ops.py`                                        | **Your MCP server**: safe project directory access with security controls             |
| `workspace/`                                                 | Agent file sandbox shared host <-> mcpo                                                  |
| `agent-reports/`                                             | Daily triage reports +`index.json` (the month-of-work artifact)                        |
| `opencode.json`                                              | Points opencode at local Ollama; no cloud calls, sharing off                             |
| `scripts/smoke-test.sh`                                      | 4-step automated smoke test                                                              |
| `scripts/run-eval.sh` + `eval/cases/` + `eval/fixtures/` | Golden-prompt eval harness incl. real-failure detection; appends`eval/history.jsonl`   |
| `scripts/eval-summary.py`                                    | Pass-rate trend from eval history                                                        |
| `scripts/nightly-triage.py`                                  | Real scheduled agent: tool-loop against local Ollama, writes`reports/YYYY-MM-DD.md`    |
| `scripts/install-cron.sh`                                    | Installs the cron entry (2:00 daily) for nightly-triage                                  |
|| `setup-projects.sh`                                          | Creates project directories on Windows filesystem for homelab access                    |
|| `test-projects-ops.sh`                                       | Tests the projects_ops MCP server functionality                                          |

## Homelab Expansion (New)

The setup now includes homelab-ready project access capabilities:

- **projects_ops MCP Server**: Safe read-only access to project directories with security controls
- **Windows Filesystem Integration**: Uses /mnt/c/Users/toant/ paths for WSL2 compatibility
- **Enhanced Docker Configuration**: Authentication proxy and network access options
- **Setup Scripts**: Automated directory creation and testing

See HOMELAB-SETUP.md for complete homelab configuration guide and NEXT-STEPS.md for current setup status.
