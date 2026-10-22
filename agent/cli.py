"""Command-line parsing and the interactive session."""

from __future__ import annotations

import argparse
import sys
import urllib.error
from dataclasses import replace
from pathlib import Path

from agent.config import DEFAULT_MODEL, DEFAULT_URL
from agent.history import summarize_history
from agent.loop import run_agent, run_planned
from agent.options import RunOptions
from agent.output import finish_run

SUMMARY_ERRORS = (OSError, ValueError, KeyError, TypeError, urllib.error.URLError)


class Session:
    """Mutable state of an interactive conversation plus its slash commands."""

    def __init__(self, mode: str, options: RunOptions) -> None:
        self.mode = mode
        self.options = options
        self.history: list[dict[str, str]] = []

    def command(self, prompt: str) -> bool:
        """Handle a /command; return True when the prompt was consumed."""
        name, _, argument = prompt.partition(" ")
        argument = argument.strip().lower()
        if name == "/status":
            print(
                f"mode={self.mode} apply={self.options.apply} repo={self.options.repo} "
                f"model={self.options.model} auto_route={self.options.auto_route} "
                f"history_turns={len(self.history) // 2}"
            )
        elif name == "/route":
            self._route(argument)
        elif name == "/mode":
            self._switch_mode(argument)
        else:
            return False
        return True

    def _route(self, argument: str) -> None:
        if argument not in {"on", "off"}:
            print("Usage: /route on|off")
            return
        self.options = replace(self.options, auto_route=argument == "on")
        print(f"Automatic model routing {'enabled' if self.options.auto_route else 'disabled'}.")

    def _switch_mode(self, argument: str) -> None:
        if argument not in {"ask", "plan", "agent"}:
            print("Usage: /mode ask|plan|agent")
            return
        self.mode = argument
        self.history = []
        print(f"Switched to {self.mode} mode. Conversation context cleared.")

    def ask(self, prompt: str) -> None:
        self.history = _compact(self.history, self.options.model, self.options.url)
        result = run_agent(self.mode, prompt, self.options, self.history)
        answer = finish_run(result, self.mode, self.options.repo, self.options.apply)
        self.history.extend(
            [{"role": "user", "content": prompt}, {"role": "assistant", "content": answer}]
        )


def interactive(mode: str, options: RunOptions) -> int:
    """Keep a short conversation and allow mode changes without restarting."""
    session = Session(mode, options)
    print("Interactive local agent. Commands: /mode ask|plan|agent, /route on|off, /status, /quit")
    while True:
        try:
            prompt = input(f"{session.mode}> ").strip()
        except EOFError, KeyboardInterrupt:
            print()
            return 0
        if not prompt:
            continue
        if prompt in {"/quit", "/exit"}:
            return 0
        if session.command(prompt):
            continue
        try:
            session.ask(prompt)
        except KeyboardInterrupt:
            print("\nInterrupted.", file=sys.stderr)
        except Exception as exc:
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
    options = RunOptions(repo, args.model, args.url, args.apply, args.stream, args.auto_route)
    prompt = " ".join(args.prompt).strip()
    if not prompt:
        if args.plan_first:
            parser.error("--plan-first needs a task on the command line")
        return interactive(args.mode, options)
    try:
        if args.plan_first:
            result = run_planned(prompt, options, args.split_models)
        else:
            result = run_agent(args.mode, prompt, options)
        finish_run(result, args.mode, repo, args.apply)
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"agent error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    return 0
