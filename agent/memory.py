"""Verified-only run memory under workspace/memory, indexed by rag_ops."""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

from agent.audit import redact
from agent.config import (
    MEMORY_DIR,
    MEMORY_ENABLED,
    MEMORY_ENTRY_CHARS,
    MEMORY_MAX_ENTRIES,
    MEMORY_RETENTION_DAYS,
)

VERIFIED_MARKER = "Verified: tests passed"


def _verified_entries(path: Path) -> list[str]:
    entries = re.split(r"(?=^## )", path.read_text(encoding="utf-8"), flags=re.MULTILINE)
    return [entry for entry in entries if VERIFIED_MARKER in entry]


def _rewrite(path: Path, entries: list[str]) -> None:
    if entries:
        path.write_text("".join(entries), encoding="utf-8")
    else:
        path.unlink()


def consolidate_memory(now: dt.datetime | None = None) -> None:
    """Keep only explicitly verified, recent generated memory entries."""
    now = now or dt.datetime.now(dt.UTC)
    cutoff = now.date() - dt.timedelta(days=MEMORY_RETENTION_DAYS)
    files = sorted(MEMORY_DIR.glob("????-??-??.md"), reverse=True)
    kept = 0
    for path in files:
        try:
            date = dt.date.fromisoformat(path.stem)
        except ValueError:
            continue
        if date < cutoff:
            path.unlink()
            continue
        verified = _verified_entries(path)
        kept += len(verified)
        _rewrite(path, verified)
    while kept > MEMORY_MAX_ENTRIES and files:
        path = files.pop()
        if not path.exists():
            continue
        verified = _verified_entries(path)
        remove_count = min(kept - MEMORY_MAX_ENTRIES, len(verified))
        kept -= remove_count
        _rewrite(path, verified[remove_count:])


def remember(mode: str, model: str, prompt: str, answer: str, verified: bool = False) -> None:
    """Append only verified Agent outcomes to memory indexed by rag_ops."""
    if not MEMORY_ENABLED or mode != "agent" or not verified:
        return
    now = dt.datetime.now(dt.UTC)
    consolidate_memory(now)
    entry = redact(
        f"## {now:%H:%M:%S}Z {mode} ({model})\n"
        f"Task: {prompt[:MEMORY_ENTRY_CHARS]}\n"
        f"Outcome: {answer[:MEMORY_ENTRY_CHARS]}\n"
        f"{VERIFIED_MARKER}\n\n"
    )
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    with (MEMORY_DIR / f"{now.date().isoformat()}.md").open("a", encoding="utf-8") as handle:
        handle.write(entry)
