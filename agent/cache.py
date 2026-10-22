"""Opt-in local semantic cache for tool-free Ask answers."""

from __future__ import annotations

import contextlib
import datetime as dt
import json
import math
import sqlite3
from pathlib import Path

from agent.audit import redact
from agent.config import (
    ANSWER_CACHE_EMBED_MODEL,
    ANSWER_CACHE_MAX_ENTRIES,
    ANSWER_CACHE_THRESHOLD,
    ANSWER_CACHE_TTL_SECONDS,
    TIMEOUT_EMBED,
)
from agent.ollama import native_json


def answer_embedding(prompt: str, url: str) -> list[float]:
    data = native_json(
        url, "/api/embed", {"model": ANSWER_CACHE_EMBED_MODEL, "input": [prompt]}, TIMEOUT_EMBED
    )
    embeddings = data.get("embeddings", [])
    if not embeddings or not isinstance(embeddings[0], list):
        raise ValueError("Ollama returned no prompt embedding")
    return embeddings[0]


def vector_similarity(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or not left:
        return 0.0
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    return dot / (left_norm * right_norm) if left_norm and right_norm else 0.0


def answer_cache_path(repo: Path) -> Path:
    return repo / "workspace" / ".agent" / "answer-cache.sqlite3"


def cached_answer(repo: Path, prompt: str, url: str) -> str | None:
    """Return a fresh, sufficiently similar tool-free answer from the local cache."""
    path = answer_cache_path(repo)
    if not path.is_file():
        return None
    embedding = answer_embedding(prompt, url)
    cutoff = dt.datetime.now(dt.UTC).timestamp() - ANSWER_CACHE_TTL_SECONDS
    with contextlib.closing(sqlite3.connect(path)) as connection:
        rows = connection.execute("SELECT answer, embedding, created_at FROM answers").fetchall()
    best: tuple[float, str] | None = None
    for answer, encoded, created_at in rows:
        try:
            if float(created_at) < cutoff:
                continue
            score = vector_similarity(embedding, json.loads(encoded))
        except TypeError, ValueError:  # JSONDecodeError is a ValueError
            continue
        if score >= ANSWER_CACHE_THRESHOLD and (best is None or score > best[0]):
            best = (score, answer)
    return best[1] if best else None


def store_cached_answer(repo: Path, prompt: str, answer: str, url: str) -> None:
    """Store a redacted tool-free Ask answer and trim the cache to its configured bound."""
    path = answer_cache_path(repo)
    path.parent.mkdir(parents=True, exist_ok=True)
    embedding = answer_embedding(prompt, url)
    now = dt.datetime.now(dt.UTC).timestamp()
    with contextlib.closing(sqlite3.connect(path)) as connection, connection:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS answers ("
            "id INTEGER PRIMARY KEY, prompt TEXT NOT NULL, answer TEXT NOT NULL, "
            "embedding TEXT NOT NULL, created_at REAL NOT NULL)"
        )
        connection.execute(
            "INSERT INTO answers(prompt, answer, embedding, created_at) VALUES(?,?,?,?)",
            (str(redact(prompt)), str(redact(answer)), json.dumps(embedding), now),
        )
        connection.execute(
            "DELETE FROM answers WHERE created_at < ?", (now - ANSWER_CACHE_TTL_SECONDS,)
        )
        connection.execute(
            "DELETE FROM answers WHERE id NOT IN "
            "(SELECT id FROM answers ORDER BY created_at DESC LIMIT ?)",
            (ANSWER_CACHE_MAX_ENTRIES,),
        )
