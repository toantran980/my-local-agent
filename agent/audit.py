"""Credential redaction and the per-run JSONL audit trail."""

from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path
from typing import Any


def redact(value: Any) -> Any:
    """Keep common credential formats out of durable local audit logs."""
    if isinstance(value, dict):
        return {key: redact(item) for key, item in value.items()}
    if isinstance(value, list):
        return [redact(item) for item in value]
    if not isinstance(value, str):
        return value
    value = re.sub(
        r"(?i)(api[_-]?key|token|secret|password)\s*([=:])\s*[^\s,;]+", r"\1\2[REDACTED]", value
    )
    return re.sub(r"(?i)bearer\s+[A-Za-z0-9._~+/=-]+", "******", value)


def audit(path: Path, event: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    event["ts"] = dt.datetime.now(dt.UTC).isoformat()
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(redact(event), ensure_ascii=False) + "\n")
