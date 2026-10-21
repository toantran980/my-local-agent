# my-local-agent Makefile
# Shortcuts for common operations

SHELL := /bin/bash
ROOT := $(shell pwd)
MY_LOCAL_AGENT_ROOT ?= $(ROOT)

.PHONY: up down build restart logs test eval cron cron-install logs-ollama logs-mcpo logs-webui clean

# ── Core stack ──────────────────────────────────────────────────
up:
	wsl bash -lc 'cd "$${MY_LOCAL_AGENT_ROOT:-$(ROOT)}" && docker compose up -d --build'

down:
	wsl bash -lc 'cd "$${MY_LOCAL_AGENT_ROOT:-$(ROOT)}" && docker compose down'

build:
	wsl bash -lc 'cd "$${MY_LOCAL_AGENT_ROOT:-$(ROOT)}" && docker compose build'

restart:
	wsl bash -lc 'cd "$${MY_LOCAL_AGENT_ROOT:-$(ROOT)}" && docker compose restart'

logs:
	wsl bash -lc 'cd "$${MY_LOCAL_AGENT_ROOT:-$(ROOT)}" && docker compose logs -f'

logs-ollama:
	wsl bash -lc 'cd "$${MY_LOCAL_AGENT_ROOT:-$(ROOT)}" && docker compose logs -f ollama'

logs-mcpo:
	wsl bash -lc 'cd "$${MY_LOCAL_AGENT_ROOT:-$(ROOT)}" && docker compose logs -f mcpo'

logs-webui:
	wsl bash -lc 'cd "$${MY_LOCAL_AGENT_ROOT:-$(ROOT)}" && docker compose logs -f open-webui'

# ── Health / verify ─────────────────────────────────────────────
smoke:
	wsl bash -lc 'cd "$${MY_LOCAL_AGENT_ROOT:-$(ROOT)}" && bash scripts/smoke-test.sh'

ps:
	wsl bash -lc 'cd "$${MY_LOCAL_AGENT_ROOT:-$(ROOT)}" && docker compose ps'

gpu:
	wsl bash -lc 'curl -s http://localhost:11434/api/ps | python3 -c "import json,sys; d=json.load(sys.stdin); [print(f\"{m[\"name\"]}: {m.get(\"size_vram\",0)/1e9:.1f}GB VRAM\") for m in d.get(\"models\",[])]"'

# ── Evaluation ──────────────────────────────────────────────────
eval:
	wsl bash -lc 'cd "$${MY_LOCAL_AGENT_ROOT:-$(ROOT)}" && bash scripts/run-eval.sh && python3 scripts/eval-summary.py'

eval-history:
	wsl bash -lc 'cd "$${MY_LOCAL_AGENT_ROOT:-$(ROOT)}" && python3 scripts/eval-summary.py'

eval-rag:
	wsl bash -lc 'cd "$${MY_LOCAL_AGENT_ROOT:-$(ROOT)}" && python3 scripts/eval-rag.py'

# ── Cron / nightly ──────────────────────────────────────────────
cron-install:
	wsl bash -lc 'cd "$${MY_LOCAL_AGENT_ROOT:-$(ROOT)}" && bash scripts/install-cron.sh'

cron-verify:
	wsl bash -lc 'crontab -l | grep my-local-agent-nightly-triage'

cron-run:
	wsl bash -lc 'cd "$${MY_LOCAL_AGENT_ROOT:-$(ROOT)}" && bash scripts/run-nightly.sh'

cron-logs:
	wsl bash -lc 'tail -f "$${MY_LOCAL_AGENT_ROOT:-$(ROOT)}/logs/nightly-triage.log"'

# ── Reports ─────────────────────────────────────────────────────
reports:
	ls -la "$${MY_LOCAL_AGENT_ROOT:-$(ROOT)}/reports/"

report-latest:
	cat "$${MY_LOCAL_AGENT_ROOT:-$(ROOT)}/reports/$$(date -I).md" 2>/dev/null || echo "No report for today"

# ── Agent CLI ───────────────────────────────────────────────────
agent-ask:
	wsl bash -lc 'cd "$${MY_LOCAL_AGENT_ROOT:-$(ROOT)}" && python3 agent_cli.py ask "$(filter-out $@,$(MAKECMDGOALS))"'

agent-plan:
	wsl bash -lc 'cd "$${MY_LOCAL_AGENT_ROOT:-$(ROOT)}" && python3 agent_cli.py plan "$(filter-out $@,$(MAKECMDGOALS))"'

agent-dry:
	wsl bash -lc 'cd "$${MY_LOCAL_AGENT_ROOT:-$(ROOT)}" && python3 agent_cli.py agent "$(filter-out $@,$(MAKECMDGOALS))"'

agent-apply:
	wsl bash -lc 'cd "$${MY_LOCAL_AGENT_ROOT:-$(ROOT)}" && python3 agent_cli.py agent --apply "$(filter-out $@,$(MAKECMDGOALS))"'

# Allow extra args to be passed through
%:
	@:

# ── Utility ─────────────────────────────────────────────────────
clean:
	wsl bash -lc 'cd "$${MY_LOCAL_AGENT_ROOT:-$(ROOT)}" && docker compose down -v'

clean-logs:
	rm -f "$${MY_LOCAL_AGENT_ROOT:-$(ROOT)}/logs/nightly-triage.log"
	rm -rf "$${MY_LOCAL_AGENT_ROOT:-$(ROOT)}/reports/*"

# Print available targets
help:
	@echo "my-local-agent Makefile"
	@echo ""
	@echo "Stack:"
	@echo "  make up           - Start stack (build + up)"
	@echo "  make down         - Stop stack"
	@echo "  make restart      - Restart all services"
	@echo "  make logs         - Follow all logs"
	@echo ""
	@echo "Health:"
	@echo "  make smoke        - Run smoke test (SMOKE: PASS)"
	@echo "  make ps           - Show container status"
	@echo "  make gpu          - Show GPU model residency"
	@echo ""
	@echo "Eval:"
	@echo "  make eval         - Run eval suite + summary"
	@echo "  make eval-history - Show eval history trend"
	@echo "  make eval-rag     - Retrieval hit-rate eval (needs nomic-embed-text)"
	@echo ""
	@echo "Cron / Nightly:"
	@echo "  make cron-install - Install 5 PM cron"
	@echo "  make cron-verify  - Verify cron entry"
	@echo "  make cron-run     - Run nightly once now"
	@echo "  make cron-logs    - Tail cron log"
	@echo ""
	@echo "Reports:"
	@echo "  make reports      - List all reports"
	@echo "  make report-latest- Show today's report"
	@echo ""
	@echo "Agent CLI (pass prompt after target):"
	@echo "  make agent-ask 'question'"
	@echo "  make agent-plan 'task'"
	@echo "  make agent-dry 'task'      # dry-run"
	@echo "  make agent-apply 'task'    # with --apply"
	@echo ""
	@echo "Utils:"
	@echo "  make clean        - Down + remove volumes"
	@echo "  make clean-logs   - Clear cron logs + reports"
	@echo "  make help         - This help"