"""Settings shared by every step of a run."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RunOptions:
    repo: Path
    model: str
    url: str
    apply: bool = False
    stream: bool = False
    auto_route: bool = False
