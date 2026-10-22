"""The tool-calling loop, plan-then-execute orchestration, and run bookkeeping."""

from __future__ import annotations

import datetime as dt
import json
import sqlite3
import sys
import urllib.error
from dataclasses import replace
from pathlib import Path
from typing import Any

from agent.audit import audit
from agent.cache import cached_answer, store_cached_answer
from agent.config import (
    ANSWER_CACHE_ENABLED,
    CITATION,
    EXECUTOR_MODEL,
    MAX_CITATION_RETRIES,
    MAX_REFLECTIONS,
    MAX_TOOL_STEPS,
    MAX_WRITE_RETRIES,
    PLANNER_MODEL,
)
from agent.memory import remember
from agent.ollama import post, post_stream
from agent.options import RunOptions
from agent.output import plain_terminal_text
from agent.planning import structured_plan
from agent.prompts import executor_prompt, system_prompt
from agent.result import RunResult
from agent.routing import choose_model, installed_models, prompt_complexity, routed_model
from agent.tools import (
    LocalTools,
    is_write_refusal,
    tool_definitions,
    validate_arguments,
)


def verification_failure(tools: LocalTools, mode: str, audit_file: Path) -> str | None:
    """Run tests for any untested staged write; return the output if they fail."""
    if mode != "agent" or not tools.pending_writes:
        return None
    if tools.tests_dirty:
        result = tools.call("run_tests", {})
        audit(audit_file, {"event": "auto_verification", "result": result})
    if tools.last_test_passed() is False and tools.caused_by_staged_changes():
        return tools.test_results[-1]
    return None


class _AgentRun:
    """State and steps of a single tool-calling run."""

    def __init__(
        self,
        mode: str,
        prompt: str,
        options: RunOptions,
        history: list[dict[str, str]],
        seed_writes: dict[Path, str] | None,
    ) -> None:
        self.mode = mode
        self.prompt = prompt
        self.repo = options.repo
        self.model = options.model
        self.url = options.url
        self.apply = options.apply
        self.stream = options.stream
        self.history = history
        self.tools = LocalTools(self.repo, self.apply, seed_writes)
        day = dt.datetime.now(dt.UTC).date().isoformat()
        self.audit_file = self.repo / ".agent" / "audit" / f"{day}.jsonl"
        self.messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt(mode, self.apply)},
            *history,
            {"role": "user", "content": prompt},
        ]
        self.refusals: dict[tuple[str, str], int] = {}
        self.reflections = 0
        self.citation_retries = 0
        self.tool_call_count = 0

    def route_model(self) -> None:
        requested_model = routed_model(self.prompt)
        self.model, warning = choose_model(self.prompt, self.model, self.url)
        audit(
            self.audit_file,
            {
                "event": "model_routed",
                "requested_model": requested_model,
                "selected_model": self.model,
                "fallback": warning,
                "complexity_score": prompt_complexity(self.prompt),
            },
        )
        print(warning or f"Model routing selected {self.model}.", file=sys.stderr)

    def run(self) -> RunResult:
        audit(
            self.audit_file,
            {
                "event": "run_started",
                "mode": self.mode,
                "model": self.model,
                "apply": self.apply,
                "prompt": self.prompt,
                "history_summarized": any(
                    item.get("content", "").startswith("Earlier conversation summary")
                    for item in self.history
                ),
            },
        )
        if cached := self._cache_hit():
            return cached
        send = post_stream if self.stream and self.mode != "plan" else post
        for _ in range(MAX_TOOL_STEPS):
            response = send(
                self.url,
                {
                    "model": self.model,
                    "messages": self.messages,
                    "tools": tool_definitions(self.mode),
                    "stream": False,
                },
            )
            message = response["choices"][0]["message"]
            self.messages.append(message)
            calls = message.get("tool_calls") or []
            result = self._run_tool_calls(calls) if calls else self._final_answer(message)
            if result is not None:
                return result
        audit(self.audit_file, {"event": "run_stopped", "reason": "tool_step_limit"})
        return RunResult(
            f"Stopped after {MAX_TOOL_STEPS} tool steps.",
            self.tools.pending_writes,
            self.audit_file,
            tests_passed=self.tools.last_test_passed(),
            test_output=self._last_test_output(),
        )

    def _last_test_output(self) -> str:
        return self.tools.test_results[-1] if self.tools.test_results else ""

    def _cache_hit(self) -> RunResult | None:
        if self.mode != "ask" or not ANSWER_CACHE_ENABLED:
            return None
        try:
            answer = cached_answer(self.repo, self.prompt, self.url)
        except (OSError, ValueError, sqlite3.Error) as exc:
            print(f"Semantic cache unavailable; asking the model: {exc}", file=sys.stderr)
            return None
        if answer is None:
            return None
        audit(self.audit_file, {"event": "semantic_cache_hit"})
        return RunResult(answer, {}, self.audit_file)

    def _final_answer(self, message: dict[str, Any]) -> RunResult | None:
        """Return the finished result, or None after queueing a corrective user message."""
        failure = verification_failure(self.tools, self.mode, self.audit_file)
        if failure and self.reflections < MAX_REFLECTIONS:
            self.reflections += 1
            audit(self.audit_file, {"event": "reflection", "attempt": self.reflections})
            self.messages.append(
                {
                    "role": "user",
                    "content": (
                        "Verification of your staged changes FAILED:\n"
                        f"{failure}\n\nFix the cause with write_file, then run_tests again."
                    ),
                }
            )
            return None
        answer = message.get("content") or "(model returned no answer)"
        if self.mode == "plan":
            evidence = [
                {"tool_result": item.get("content", "")}
                for item in self.messages
                if item.get("role") == "tool"
            ]
            answer = structured_plan(self.prompt, evidence, self.model, self.url)
        bad = self.tools.unsupported_citations(answer)
        if bad and self.citation_retries < MAX_CITATION_RETRIES:
            self.citation_retries += 1
            audit(self.audit_file, {"event": "citation_retry", "unsupported": bad})
            self.messages.append(
                {
                    "role": "user",
                    "content": (
                        f"You cited {', '.join(bad)}, but no tool result showed you "
                        "those files. "
                        "Re-answer using only sources you actually saw, or search first."
                    ),
                }
            )
            return None
        if bad:
            answer += "\n\n(unverified citations: " + ", ".join(bad) + ")"
        return self._finish(answer, streamed=self._was_streamed(message))

    def _was_streamed(self, message: dict[str, Any]) -> bool:
        # Plan mode never streams the model reply; its answer is rendered by structured_plan.
        return self.stream and self.mode != "plan" and bool(message.get("content"))

    def _finish(self, answer: str, streamed: bool) -> RunResult:
        tests_passed = self.tools.verified_outcome()
        self._persist(answer, tests_passed)
        audit(self.audit_file, {"event": "run_finished", "mode": self.mode, "answer": answer})
        outcome = {
            "tests_passed": tests_passed,
            "test_output": self._last_test_output(),
            "streamed": streamed,
        }
        if self.mode == "ask" and not streamed:
            answer = plain_terminal_text(answer)
        plan_file = None
        if self.mode == "plan":
            timestamp = dt.datetime.now(dt.UTC).strftime("%Y%m%dT%H%M%S")
            plan_file = self.repo / ".agent" / "plans" / f"{timestamp}.md"
            plan_file.parent.mkdir(parents=True, exist_ok=True)
            plan_file.write_text(answer + "\n", encoding="utf-8")
        return RunResult(answer, self.tools.pending_writes, self.audit_file, plan_file, **outcome)

    def _persist(self, answer: str, tests_passed: bool | None) -> None:
        """Save verified Agent memory and tool-free Ask answers; failures are non-fatal."""
        if self.mode == "agent" and tests_passed is True:
            try:
                remember(self.mode, self.model, self.prompt, answer, verified=True)
            except OSError as exc:
                print(f"Could not update verified memory: {exc}", file=sys.stderr)
        if (
            self.mode == "ask"
            and ANSWER_CACHE_ENABLED
            and self.tool_call_count == 0
            and not CITATION.search(answer)
        ):
            try:
                store_cached_answer(self.repo, self.prompt, answer, self.url)
            except (OSError, ValueError, sqlite3.Error) as exc:
                print(f"Could not store semantic cache answer: {exc}", file=sys.stderr)

    def _run_tool_calls(self, calls: list[dict[str, Any]]) -> RunResult | None:
        for call in calls:
            self.tool_call_count += 1
            function = call.get("function", {})
            try:
                arguments = json.loads(function.get("arguments") or "{}")
            except json.JSONDecodeError:
                arguments = None
            name = function.get("name", "")
            invalid = validate_arguments(name, arguments, self.mode)
            result = invalid or self.tools.call(name, arguments)
            audit(
                self.audit_file,
                {
                    "event": "tool_called",
                    "mode": self.mode,
                    "tool": name,
                    "arguments": arguments,
                    "result": result,
                },
            )
            self.messages.append(
                {"role": "tool", "tool_call_id": call.get("id", ""), "content": result}
            )
            if stop := self._stop_on_repeated_refusal(name, result):
                return stop
        return None

    def _stop_on_repeated_refusal(self, name: str, result: str) -> RunResult | None:
        if not is_write_refusal(result):
            return None
        key = (name, result)
        self.refusals[key] = self.refusals.get(key, 0) + 1
        if self.refusals[key] < MAX_WRITE_RETRIES:
            return None
        question = (
            f"You tried to write via `{name}` twice and got the same "
            f"refusal both times:\n\n  {result}\n\n"
            "That suggests the target path isn't writable from the "
            "selected repository, so I stopped and am asking instead of "
            "spinning. Want me to target a path under the repo root "
            "(e.g. `reports/<date>.md`), or skip writing entirely?"
        )
        audit(
            self.audit_file,
            {"event": "asked_for_input", "reason": "repeated_write_refusal", "tool": name},
        )
        return RunResult(question, self.tools.pending_writes, self.audit_file)


def run_agent(
    mode: str,
    prompt: str,
    options: RunOptions,
    history: list[dict[str, str]] | None = None,
    seed_writes: dict[Path, str] | None = None,
) -> RunResult:
    run = _AgentRun(mode, prompt, options, history or [], seed_writes)
    if options.auto_route:
        run.route_model()
    return run.run()


def _resolve_split_models(model: str, url: str) -> tuple[str, str]:
    """Planner and executor models, visibly falling back to `model` when not installed."""
    try:
        installed = installed_models(url)
    except (OSError, ValueError, urllib.error.URLError) as exc:
        print(f"Could not check split models; using {model}: {exc}", file=sys.stderr)
        return model, model
    chosen = []
    for role, wanted in (("Planner", PLANNER_MODEL), ("Executor", EXECUTOR_MODEL)):
        if wanted in installed:
            chosen.append(wanted)
        else:
            print(f"{role} model '{wanted}' unavailable; using '{model}'.", file=sys.stderr)
            chosen.append(model)
    return chosen[0], chosen[1]


def run_planned(prompt: str, options: RunOptions, split_models: bool = False) -> RunResult:
    """Plan first (read-only), execute the plan, and replan once if verification fails."""
    model, url = options.model, options.url
    planner, executor = _resolve_split_models(model, url) if split_models else (model, model)
    route = options.auto_route and not split_models

    def step(mode: str, task: str, step_model: str, **extra: Any) -> RunResult:
        step_options = replace(options, model=step_model, auto_route=route)
        return run_agent(mode, task, step_options, **extra)

    plan = step("plan", prompt, planner)
    if not plan.streamed:
        print(f"== Plan ==\n{plan.answer}\n")
    result = step("agent", executor_prompt(prompt, plan.answer), executor)
    if result.tests_passed is False:
        audit(result.audit_file, {"event": "replan", "reason": "verification_failed"})
        print("== Verification failed; replanning once ==")
        replan = step(
            "plan",
            f"{prompt}\n\nA previous attempt failed verification:\n{result.test_output}\n"
            "Propose a corrected plan that builds on the staged changes.",
            planner,
        )
        result = step(
            "agent",
            executor_prompt(prompt, replan.answer),
            executor,
            seed_writes=result.pending_writes,
        )
    return result
