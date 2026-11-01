---
name: local-ollama-agent-stack
description: "Build, configure, operate, and troubleshoot local-first AI agent stacks using Ollama, Docker Compose, WSL2, and MCP tools. Use when setting up a local model agent, connecting MCP tools, adding read-only project access or local RAG, checking GPU/model health, evaluating agent changes, or debugging this repository."
---

# Local Ollama Agent Stack

Use this skill to work safely and reproducibly with a local-first agent stack. It is based on `my-local-agent`, which runs Ollama locally, exposes MCP tools through mcpo, and includes a sandboxed terminal agent, local RAG, evaluations, and nightly triage.

## Workflow

1. **Inspect before acting.** Read the repository's `README.md`, `QUICKSTART.md`, `AGENTS.md`, and the focused guide for the requested feature. Check the actual Compose configuration and code before assuming defaults; do not read `.env` or other credential files.
2. **Confirm the deployment context.** The documented setup uses Windows, WSL2, Docker Desktop, and an NVIDIA GPU. Prefer running Linux commands inside WSL2. The default inference endpoint is host Ollama at `http://localhost:11434`; the optional Ollama container must not compete with a host Ollama process for the same port.
3. **Start and verify incrementally.** Follow [the deployment and operation guide](./references/workflows.md). Run the smoke test before diagnosing higher-level agent or MCP behavior.
4. **Keep changes scoped and safe.** Ask and Plan are read-only. Agent mode is a dry run unless `--apply` is passed, and writes require confirmation. Preserve the repo's sandbox, path, size, sensitive-file, and localhost-only restrictions; see [safety boundaries](./references/safety-boundaries.md).
5. **Validate the requested behavior.** Use the smallest relevant test or evaluation, then report commands and their actual results. Do not claim a model, GPU, MCP server, or test passed unless its output confirms it.
6. **Troubleshoot from evidence.** Check service health, logs, endpoint reachability, and model residency in order. Use [the troubleshooting guide](./references/troubleshooting.md) and report unresolved failures explicitly.

## Quick commands

Run these from the repository root in WSL2:

```bash
docker compose up -d --build
bash scripts/smoke-test.sh
python3 agent_cli.py ask "What does this repository do?"
python3 agent_cli.py plan "Add health checks"
python3 agent_cli.py agent "Fix the syntax error"  # dry run
python3 -m pytest -q tests
```

For changes, use the repository's established workflow and request explicit confirmation before applying proposed writes. Do not expose Ollama or the MCP bridge to an untrusted network.

## Included diagnostic script

Run [the local stack check](./scripts/check_local_stack.py) after setup to verify Ollama and mcpo are reachable without generating a model response or changing state:

```bash
python3 scripts/check_local_stack.py
python3 scripts/check_local_stack.py --model qwen3:8b
```

It uses Python's standard library. Override endpoints with `--ollama-url` and `--mcpo-url` or the `OLLAMA_URL` and `MCPO_URL` environment variables. This lightweight check complements, but does not replace, the repository's full smoke test.

## Included guides

- [Workflows](./references/workflows.md): startup, agent modes, MCP/RAG, evaluations, and nightly triage.
- [Safety boundaries](./references/safety-boundaries.md): local network, write, read, and data-handling constraints.
- [Troubleshooting](./references/troubleshooting.md): common setup and runtime symptoms.
