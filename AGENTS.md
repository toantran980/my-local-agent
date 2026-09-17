# Local Agent Project - AI Agent Context

## Project Overview
This is a self-hosted local AI agent stack running on NVIDIA RTX 5080 with WSL2 + Docker Desktop. The stack uses Ollama for inference, Open WebUI for chat interface, and MCP tools for filesystem and web operations.

## Key Components
- **Ollama**: Local inference engine (qwen3:8b default, qwen3:14b optional)
- **Open WebUI**: Chat UI at http://localhost:3000
- **mcpo**: MCP-to-OpenAPI bridge for tool integration
- **agent_cli.py**: Terminal interface with Ask/Plan/Agent modes
- **nightly-triage.py**: Scheduled agent for repository triage
- **projects_ops**: Custom MCP server for safe project directory access

## Verification Commands
- `docker compose ps` - Check service status
- `docker exec local_ollama ollama ps` - Verify GPU usage
- `./scripts/smoke-test.sh` - Automated smoke test
- `python3 -m pytest -q` - Run tests (requires .agent-venv)

## Build/Test Commands
- `docker compose up -d --build` - Build and start services
- `docker exec local_ollama ollama pull qwen3:8b` - Pull model
- `./scripts/run-eval.sh` - Run evaluation suite
- `python3 scripts/eval-summary.py` - View eval results

## Project Structure
- `agent_cli.py` - Main terminal agent interface
- `mcp/local_ops.py` - Custom MCP server for operations
- `scripts/` - Utility scripts (nightly triage, eval, cron)
- `eval/` - Evaluation cases and fixtures
- `tests/` - Unit tests for agent CLI
- `workspace/` - Agent file sandbox
- `agent-reports/` - Daily triage reports

## Environment Variables
- `OLLAMA_URL` - Ollama endpoint (default: http://localhost:11434)
- `AGENT_MODEL` - Model for agent_cli.py (default: qwen3:8b)
- `NIGHTLY_MODEL` - Model for nightly triage (default: qwen3:8b)
- `DRAFT_PR=1` - Enable draft PR creation for nightly reports
- `GH_REPO` - GitHub repo for draft PRs

## Key Constraints
- All services bind to localhost only (no authentication on Ollama API)
- Agent writes restricted to --repo directory with --apply flag
- Sensitive files (.env, keys, etc.) are protected from read/write
- File operations limited to 32KB for safety
- Maximum 10 tool steps per agent run

## VRAM Budget (16GB card)
- qwen3:8b fits comfortably at ~7GB total (32k context)
- qwen3:14b fits at ~11GB (cap context at 32k)
- qwen3:30B barely fits, not recommended
- Rule: weights + KV + 1GB headroom must stay under ~14.5GB