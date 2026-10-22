#!/usr/bin/env python3
# noqa: EXE001
"""Local terminal agent with Ask, Plan, and Agent modes.

Examples:
    python3 agent_cli.py ask "What does this repository do?"
    python3 agent_cli.py plan "Add health checks to the compose services"
    python3 agent_cli.py agent "Fix the syntax error"             # dry run
    python3 agent_cli.py agent --apply "Fix the syntax error"     # may write

All inference uses Ollama's local OpenAI-compatible endpoint.  Ask and Plan
are read-only.  Agent mode can only write below --repo, and only when --apply
is explicitly supplied.  Every run appends JSONL events under .agent/audit.

The implementation lives in the stdlib-only ``agent`` package; this file is the
stable entry point and re-exports the public names.
"""

from __future__ import annotations

from agent.cache import answer_cache_path, cached_answer, store_cached_answer
from agent.cli import interactive, main
from agent.history import estimate_history_tokens, summarize_history
from agent.loop import run_agent, run_planned
from agent.memory import consolidate_memory, remember
from agent.ollama import post, post_stream
from agent.options import RunOptions
from agent.output import apply_pending_writes, finish_run
from agent.planning import PLAN_SCHEMA, structured_plan
from agent.prompts import system_prompt
from agent.result import RunResult
from agent.routing import choose_model, routed_model
from agent.tools import (
    LocalTools,
    is_sensitive_path,
    resolve_repo_path,
    tool_definitions,
    validate_arguments,
)

__all__ = [
    "PLAN_SCHEMA",
    "LocalTools",
    "RunOptions",
    "RunResult",
    "answer_cache_path",
    "apply_pending_writes",
    "cached_answer",
    "choose_model",
    "consolidate_memory",
    "estimate_history_tokens",
    "finish_run",
    "interactive",
    "is_sensitive_path",
    "main",
    "post",
    "post_stream",
    "remember",
    "resolve_repo_path",
    "routed_model",
    "run_agent",
    "run_planned",
    "store_cached_answer",
    "structured_plan",
    "summarize_history",
    "system_prompt",
    "tool_definitions",
    "validate_arguments",
]

if __name__ == "__main__":
    raise SystemExit(main())
