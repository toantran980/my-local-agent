# Quickstart — start the whole stack from WSL2

This is the 60-second version of README.md. Copy the commands verbatim —
every file name below matches what is actually in this repo.

> You need: Docker Desktop **running** with the **WSL2 backend**, and the
> `wsl` command available from a Windows PowerShell/CMD prompt. Everything else
> is given to you by the compose file.
>
> **Portable paths:** set `MY_LOCAL_AGENT_ROOT` to your repo root (WSL path).
> Defaults to the current directory if unset.
> 
> ```bash
> # Example (adjust to your actual path):
> export MY_LOCAL_AGENT_ROOT="/mnt/c/Users/yourname/my-local-agent"
> # Or auto-detect from current dir:
> export MY_LOCAL_AGENT_ROOT="$(pwd)"
> ```

---

## 1. One command to start everything

    wsl bash -lc 'cd "${MY_LOCAL_AGENT_ROOT:-$(pwd)}" && docker compose up -d --build'

This starts three containers + pulls a model the first time:

| Service    | Purpose              | Address        |
| ---------- | -------------------- | -------------- |
| Ollama     | Local model runtime  | :11434 / UI    |
| mcpo       | MCP bridge (3 tools) | :8000          |
| Open WebUI | Chat UI              | :3000          |

First run does a one-time model pull (~5–6 GB). Later runs are instant.

---

## 2. Verify it is actually working

    wsl bash -lc 'cd "${MY_LOCAL_AGENT_ROOT:-$(pwd)}" && bash scripts/smoke-test.sh'

Expect: `SMOKE: PASS` and a GPU row `qwen3:8b  … VRAM …` (proof it's on the
RTX 5080, not CPU).

---

## 3. Talk to it

    # Open WebUI chat UI
    start http://localhost:3000

    # or from a Windows terminal via the OpenAI-compatible API
    curl -s http://localhost:11434/v1/chat/completions -H "Content-Type: application/json" `
      -d '{"model":"qwen3:8b","messages":[{"role":"user","content":"Say hello to local agent"}]}' |
      python -c "import json,sys; print(json.load(sys.stdin)['choices'][0]['message']['content'])"

---

## 4. Scheduled night agent (the "works while you sleep" part)

The stack includes a real nightly agent: a Python triage job that inspects the
repo + GPU and writes a dated report.

    wsl bash -lc 'cd "${MY_LOCAL_AGENT_ROOT:-$(pwd)}" && bash scripts/install-cron.sh'

This installs a cron entry that runs the agent every day at **5:00 PM** (`0 17 * * *`). Grab the hourly override if you ever need a different one: `CRON_HOUR=17 CRON_MIN=0 ./scripts/install-cron.sh`.
Verify it landed:

    wsl crontab -l            # look for the "my-local-agent-nightly-triage" line

Reports appear in `reports/<YYYY-MM-DD>.md` each morning. To also get a draft
PR you approve, set `DRAFT_PR=1` with a `GH_REPO` when installing.

Run it once immediately (no cron needed) to prove it works:

    wsl bash -lc 'cd "${MY_LOCAL_AGENT_ROOT:-$(pwd)}" && python3 scripts/nightly-triage.py'

You should see a tool loop print (`git_status`, `gpu_status`, `models_list`,
`grep`, …) and a written `reports/<today>.md`.

---

## 5. Reliability harness (measure it, don't hope)

    wsl bash -lc 'cd "${MY_LOCAL_AGENT_ROOT:-$(pwd)}" && bash scripts/run-eval.sh && python3 scripts/eval-summary.py'

Expected result: `6/6 passed` and a pass-rate trend printed from
`eval/history.jsonl`. That number is the "reliability" answer for the project.

---

## 6. Health dashboard (optional)

If you have `wsl-vpnkit`-style setup or just want a plain HTTP check from
Windows:

    curl -s -o NUL -w "ollama %{http_code}  " http://localhost:11434
    curl -s -o NUL -w "mcpo %{http_code}  " http://localhost:8000
    curl -s -o NUL -w "webui %{http_code}`n" http://localhost:3000

Three 200s = everything is serving.

---

## Troubleshooting

| Symptom                              | Fix                                                                 |
| ------------------------------------ | ------------------------------------------------------------------- |
| `command not found: docker`           | Start **Docker Desktop** (it provides the docker CLI in WSL2)       |
| `connection refused: 11434`          | Containers not up yet → re-run step 1 and wait ~30 s for Ollama      |
| Smoke test "GPU" row missing/failing | Model not finished pulling → re-run step 1 once                     |
| WebUI won't load on :3000            | First cold start is slow; retry after ~1 min                        |
| Cron reports not appearing           | `wsl bash -lc 'service cron start'` then re-run `install-cron.sh`    |

All data stays local. Nothing in this file calls a cloud API.

For homelab setup and project access features, see [HOMELAB-SETUP.md](HOMELAB-SETUP.md).