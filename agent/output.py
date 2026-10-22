"""Terminal output and the confirmed write-back of staged changes."""

from __future__ import annotations

import difflib
import os
import re
import tempfile
from pathlib import Path

from agent.audit import audit
from agent.config import MAX_FILE_BYTES
from agent.result import RunResult


def plain_terminal_text(text: str) -> str:
    """Remove the most distracting Markdown markers from Ask-mode output."""
    text = re.sub(r"\*\*|__|`", "", text)
    return re.sub(r"(?m)^#{1,6}\s+", "", text)


def render_diffs(repo: Path, writes: dict[Path, str]) -> str:
    """Return a bounded unified diff for staged whole-file writes."""
    chunks: list[str] = []
    for path, replacement in writes.items():
        before = (
            path.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
            if path.exists()
            else []
        )
        after = replacement.splitlines(keepends=True)
        relative = path.relative_to(repo)
        chunks.extend(
            difflib.unified_diff(before, after, fromfile=f"a/{relative}", tofile=f"b/{relative}")
        )
    text = "".join(chunks)
    return text[:MAX_FILE_BYTES] or "(no content changes)"


def apply_pending_writes(writes: dict[Path, str]) -> None:
    for path, content in writes.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            delete=False,
            prefix=f".{path.name}.",
            suffix=".tmp",
        ) as temporary:
            temporary.write(content)
            temporary_path = Path(temporary.name)
        os.replace(temporary_path, path)


def finish_run(result: RunResult, mode: str, repo: Path, apply: bool) -> str:
    """Display the outcome and apply staged Agent changes only after approval."""
    if not result.streamed:
        print(result.answer)
    if result.plan_file:
        print(f"\nPlan saved: {result.plan_file.relative_to(repo)}")
    if result.pending_writes:
        print("\nProposed diff:\n")
        print(render_diffs(repo, result.pending_writes))
        if mode == "agent" and apply:
            confirmation = input("\nApply these changes? [y/N] ").strip().lower()
            if confirmation in {"y", "yes"}:
                apply_pending_writes(result.pending_writes)
                audit(
                    result.audit_file,
                    {
                        "event": "writes_applied",
                        "files": [str(path.relative_to(repo)) for path in result.pending_writes],
                    },
                )
                print(f"Applied {len(result.pending_writes)} file change(s).")
            else:
                audit(result.audit_file, {"event": "writes_declined"})
                print("Changes not applied.")
        else:
            print("No files were changed. Re-run Agent mode with --apply to enable confirmation.")
    print(f"Audit log: {result.audit_file.relative_to(repo)}")
    return result.answer
