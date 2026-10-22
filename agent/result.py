"""Result of one agent run."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class RunResult:
    answer: str
    pending_writes: dict[Path, str]
    audit_file: Path
    plan_file: Path | None = None
    tests_passed: bool | None = None
    test_output: str = ""
    streamed: bool = False
