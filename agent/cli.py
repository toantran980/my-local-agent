"""Command-line parsing and the interactive session."""

from __future__ import annotations

import argparse
import sys
import urllib.error
from pathlib import Path

from agent.config import DEFAULT_MODEL, DEFAULT_URL
from agent.history import summarize_history
from agent.loop import run_agent, run_planned
from agent.output import finish_run

SUMMARY_ERRORS = (OSError, ValueError, KeyError, TypeError, urllib.error.URLError)


def interactive(  # noqa: PLR0913, PLR0917
    mode: str,
    repo: Path,
    model: str,
    url: str,
    apply: bool,
    stream: bool = False,
    auto_route: bool = False,
) -> int:
    """Keep a short conversation and allow mode changes without restarting."""
    history: list[dict[str, str]] = []
    print("Interactive local agent. Commands: /mode ask|plan|agent, /route on|off, /status, /quit")
    while True:
        try:
            prompt = input(f"{mode}> ").strip()
        except EOFError, KeyboardInterrupt:
            print()
            return 0
        if not prompt:
            continue
        if prompt in {"/quit", "/exit"}:
            return 0
        if prompt == "/status":
            print(
                f"mode={mode} apply={apply} repo={repo} model={model} "
                f"auto_route={auto_route} history_turns={len(history) // 2}"
            )
            continue
        if prompt.startswith("/route "):
            requested = prompt.removeprefix("/route ").strip().lower()
            if requested in {"on", "off"}:
                auto_route = requested == "on"
                print(f"Automatic model routing {'enabled' if auto_route else 'disabled'}.")
            else:
                print("Usage: /route on|off")
            continue
        if prompt.startswith("/mode "):
            requested = prompt.removeprefix("/mode ").strip().lower()
            if requested in {"ask", "plan", "agent"}:
                mode = requested
                history = []
                print(f"Switched to {mode} mode. Conversation context cleared.")
            else:
                print("Usage: /mode ask|plan|agent")
            continue
        try:
            history = _compact(history, model, url)
            result = run_agent(
                mode, prompt, repo, model, url, apply, history, stream, auto_route=auto_route
            )
            answer = finish_run(result, mode, repo, apply)
            history.extend(
                [
                    {"role": "user", "content": prompt},
                    {"role": "assistant", "content": answer},
                ]
            )
        except BaseException as exc:
            print(f"agent error: {type(exc).__name__}: {exc}", file=sys.stderr)


def _compact(history: list[dict[str, str]], model: str, url: str) -> list[dict[str, str]]:
    try:
        compacted = summarize_history(history, model, url)
    except SUMMARY_ERRORS as exc:
        print(
            f"Conversation summarization unavailable; keeping existing history: {exc}",
            file=sys.stderr,
        )
        return history
    if len(compacted) < len(history):
        print("Older conversation turns summarized to preserve context.")
    return compacted


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Self-hosted Ask / Plan / Agent terminal assistant"
    )
    parser.add_argument("mode", choices=("ask", "plan", "agent"))
    parser.add_argument("prompt", nargs="*", help="Task; omit for interactive input")
    parser.add_argument(
        "--repo", type=Path, default=Path.cwd(), help="Repository root (default: current directory)"
    )
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument(
        "--auto-route",
        action="store_true",
        help="Route easy prompts to AGENT_EASY_MODEL and complex prompts to AGENT_HARD_MODEL",
    )
    parser.add_argument(
        "--apply", action="store_true", help="Permit Agent mode to write files under --repo"
    )
    parser.add_argument(
        "--stream",
        action="store_true",
        help="Print the answer as it is generated instead of waiting for the full reply",
    )
    parser.add_argument(
        "--plan-first",
        action="store_true",
        help="Agent mode: write a plan first, execute it, and replan once if tests fail",
    )
    parser.add_argument(
        "--split-models",
        action="store_true",
        help="With --plan-first, use AGENT_PLANNER_MODEL and AGENT_EXECUTOR_MODEL",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.apply and args.mode != "agent":
        parser.error("--apply is valid only in agent mode")
    if args.plan_first and args.mode != "agent":
        parser.error("--plan-first is valid only in agent mode")
    if args.split_models and not args.plan_first:
        parser.error("--split-models requires --plan-first")
    repo = args.repo.resolve()
    if not repo.is_dir():
        parser.error(f"not a directory: {repo}")
    prompt = " ".join(args.prompt).strip()
    if not prompt:
        if args.plan_first:
            parser.error("--plan-first needs a task on the command line")
        return interactive(
            args.mode, repo, args.model, args.url, args.apply, args.stream, args.auto_route
        )
    try:
        if args.plan_first:
            result = run_planned(
                prompt,
                repo,
                args.model,
                args.url,
                args.apply,
                args.stream,
                args.auto_route,
                args.split_models,
            )
        else:
            result = run_agent(
                args.mode,
                prompt,
                repo,
                args.model,
                args.url,
                args.apply,
                stream=args.stream,
                auto_route=args.auto_route,
            )
        finish_run(result, args.mode, repo, args.apply)
    except BaseException as exc:
        print(f"agent error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    return 0
