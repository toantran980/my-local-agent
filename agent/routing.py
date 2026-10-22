"""Opt-in routing of easy prompts to a small model and hard ones to a larger one."""

from __future__ import annotations

import json
import re
import urllib.request

from agent.config import (
    DEFAULT_EASY_MODEL,
    DEFAULT_HARD_MODEL,
    LONG_PROMPT_WORD_COUNT,
    MIN_ROUTING_SIGNALS,
    MIN_TECHNICAL_TERMS,
    TIMEOUT_TAGS,
)

TECHNICAL_TERMS = {
    "api", "database", "security", "authentication", "concurrency",
    "performance", "test", "tests", "pipeline", "architecture", "multiple",
}  # fmt: skip


def prompt_complexity(prompt: str) -> int:
    """Score explicit complexity signals for opt-in small/large model routing."""
    lowered = prompt.lower()
    words = re.findall(r"\b[\w-]+\b", lowered)
    score = int(len(words) >= LONG_PROMPT_WORD_COUNT)
    score += int(
        bool(
            re.search(
                r"\b(fix|refactor|debug|troubleshoot|migrate|architect|optimize|integrate|"
                r"investigate|design)\b",
                lowered,
            )
        )
    )
    score += int(len(set(words) & TECHNICAL_TERMS) >= MIN_TECHNICAL_TERMS)
    score += int(bool(re.search(r"\b(across files|end.to.end|multiple steps|and also)\b", lowered)))
    return score


def routed_model(
    prompt: str, easy_model: str = DEFAULT_EASY_MODEL, hard_model: str = DEFAULT_HARD_MODEL
) -> str:
    """Select the larger model only when a prompt has multiple complexity signals."""
    return hard_model if prompt_complexity(prompt) >= MIN_ROUTING_SIGNALS else easy_model


def _installed_models(url: str) -> set[str]:
    request = urllib.request.Request(url.rstrip("/") + "/api/tags")
    with urllib.request.urlopen(request, timeout=TIMEOUT_TAGS) as response:  # noqa: S310
        data = json.load(response)
    return {str(model.get("name", "")) for model in data.get("models", [])}


def choose_model(prompt: str, fallback_model: str, url: str) -> tuple[str, str | None]:
    """Route to the requested model, visibly falling back if it is not installed."""
    target = routed_model(prompt)
    installed = _installed_models(url)
    if target in installed:
        return target, None
    message = (
        f"Routed model '{target}' is not installed; using '{fallback_model}'. "
        f"Install it with `ollama pull {target}` to enable this route."
    )
    return fallback_model, message
