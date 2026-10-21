"""rag_ops - MCP server for local retrieval-augmented search over project files.

Chunks text files, embeds them with Ollama, and stores vectors in SQLite
(stdlib only; cosine similarity in pure Python, fine for a few thousand chunks).
Read-only on sources: the only thing written is the index database.

Env overrides:
  RAG_SOURCES      os.pathsep-separated dirs to index (default /repo:/projects)
  RAG_DB           index database path    (default /workspace/.rag/index.db)
  OLLAMA_URL       Ollama base URL        (default http://ollama:11434)
  EMBED_MODEL      embedding model        (default nomic-embed-text)
  CHUNK_CHARS      chunk size in chars    (default 1200)
  CHUNK_OVERLAP    overlap in chars       (default 200)
  MAX_FILE_BYTES   skip bigger files      (default 200000)
  HYBRID_WEIGHT    keyword share of the score, 0 = vector only (default 0.3)
  RERANK           1 = have an LLM re-order the top candidates (default 0, adds latency)
  RERANK_MODEL     chat model used for reranking (default qwen3:8b)
  RERANK_CANDIDATES  how many hits to rerank before cutting to k (default 15)
  RERANK_WEIGHT    LLM share of the final score, 0-1 (default 0.3)

Markdown files are split by heading; other files use fixed-size windows.
"""

import hashlib
import json
import math
import os
import re
import sqlite3
import urllib.request
from pathlib import Path

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("rag-ops")

# Bump when chunking changes so existing indexes are re-embedded.
CHUNKER_VERSION = "2-heading-aware"

SENSITIVE_NAMES = {".env", ".npmrc", ".pypirc", "id_rsa", "id_ed25519"}
SENSITIVE_SUFFIXES = (".pem", ".key", ".p12", ".pfx")
EXCLUDED_DIRS = {
    ".git", ".venv", "__pycache__", "node_modules", ".pytest_cache",
    ".mypy_cache", "dist", "build", ".agent", ".rag",
}
TEXT_SUFFIXES = {
    ".py", ".md", ".txt", ".json", ".yml", ".yaml", ".toml", ".sh", ".js",
    ".ts", ".go", ".rs", ".c", ".h", ".cpp", ".java", ".html", ".css", ".sql",
}


def _env(key, default):
    return os.environ.get(key, default)


def _is_sensitive(path: Path) -> bool:
    name = path.name.lower()
    if name in SENSITIVE_NAMES or name.endswith(SENSITIVE_SUFFIXES):
        return True
    return name.startswith(".env") and name != ".env.example"


def iter_files(root: Path, max_bytes: int):
    """Yield indexable text files under root, skipping sensitive and excluded paths."""
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDED_DIRS]
        for fname in filenames:
            p = Path(dirpath) / fname
            if p.suffix.lower() not in TEXT_SUFFIXES or _is_sensitive(p):
                continue
            try:
                if p.stat().st_size <= max_bytes:
                    yield p
            except OSError:
                continue


def chunk_text(text: str, size: int, overlap: int) -> list[str]:
    """Split text into overlapping chunks of at most `size` chars."""
    if size <= 0:
        raise ValueError("size must be positive")
    overlap = max(0, min(overlap, size - 1))
    text = text.strip()
    if not text:
        return []
    step = size - overlap
    return [text[i:i + size] for i in range(0, len(text), step)
            if text[i:i + size].strip()]


def chunk_markdown(text: str, size: int, overlap: int) -> list[str]:
    """Split Markdown by heading; each chunk is prefixed with its heading path so the
    embedding knows which section it came from. Oversized sections fall back to
    fixed-size windows."""
    sections, path, body = [], [], []

    def flush():
        content = "\n".join(body).strip()
        if content:
            sections.append((" > ".join(path), content))
        body.clear()

    in_fence = False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
        match = None if in_fence else re.match(r"(#{1,6})\s+(.*\S)", line)
        if match:
            flush()
            level = len(match.group(1))
            del path[level - 1:]
            path.append(match.group(2))
        else:
            body.append(line)
    flush()
    chunks = []
    for title, content in sections:
        prefix = f"{title}\n" if title else ""
        for piece in chunk_text(content, max(1, size - len(prefix)), overlap):
            chunks.append(prefix + piece)
    return chunks


def chunk_file(path: Path, text: str, size: int, overlap: int) -> list[str]:
    if path.suffix.lower() == ".md":
        return chunk_markdown(text, size, overlap)
    return chunk_text(text, size, overlap)


STOPWORDS = {
    "the", "a", "an", "is", "are", "of", "to", "in", "on", "for", "and", "or", "do", "does",
    "how", "what", "which", "when", "where", "who", "my", "i", "it", "be", "can", "will",
    "that", "this", "with", "at", "by", "from", "as", "you",
}


def _tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9_]+", text.lower()) if t not in STOPWORDS}


def keyword_score(query: str, text: str) -> float:
    """Fraction of distinct query terms that appear in the text (0..1)."""
    terms = _tokens(query)
    return len(terms & _tokens(text)) / len(terms) if terms else 0.0


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def embed(texts: list[str]) -> list[list[float]]:
    body = json.dumps({"model": _env("EMBED_MODEL", "nomic-embed-text"),
                       "input": texts}).encode()
    req = urllib.request.Request(
        f"{_env('OLLAMA_URL', 'http://ollama:11434')}/api/embed", data=body,
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.load(resp)["embeddings"]


def _db() -> sqlite3.Connection:
    path = Path(_env("RAG_DB", "/workspace/.rag/index.db"))
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE IF NOT EXISTS files "
                 "(path TEXT PRIMARY KEY, sha TEXT NOT NULL)")
    conn.execute("CREATE TABLE IF NOT EXISTS chunks "
                 "(id INTEGER PRIMARY KEY, path TEXT NOT NULL, idx INTEGER NOT NULL, "
                 "text TEXT NOT NULL, vec TEXT NOT NULL)")
    conn.execute("CREATE INDEX IF NOT EXISTS chunks_path ON chunks(path)")
    return conn


def search_index(conn: sqlite3.Connection, qvec: list[float], k: int,
                 query: str | None = None, hybrid_weight: float | None = None):
    """Return the top-k (score, path, idx, text) rows.

    Pure cosine similarity, or, when `query` is given and the weight is above zero,
    a hybrid of cosine and keyword overlap: (1 - w) * cosine + w * keyword.
    """
    if hybrid_weight is None:
        hybrid_weight = float(_env("HYBRID_WEIGHT", "0.3"))
    use_keywords = bool(query) and hybrid_weight > 0

    def score(vec, text):
        sim = cosine(qvec, json.loads(vec))
        if not use_keywords:
            return sim
        return (1 - hybrid_weight) * sim + hybrid_weight * keyword_score(query, text)

    scored = [(score(vec, text), path, idx, text)
              for path, idx, text, vec in
              conn.execute("SELECT path, idx, text, vec FROM chunks")]
    scored.sort(key=lambda r: r[0], reverse=True)
    return scored[:k]


def llm_scores(query: str, texts: list[str]) -> list[int]:
    """Ask a chat model to grade each passage 0-10 for relevance to the query."""
    listing = "\n\n".join(f"[{i}] {t[:500]}" for i, t in enumerate(texts))
    prompt = (f"Query: {query}\n\nRate how well each passage answers the query, 0 (irrelevant) "
              f"to 10 (directly answers). Return one integer per passage, in order.\n\n{listing}")
    body = json.dumps({
        "model": _env("RERANK_MODEL", "qwen3:8b"),
        "messages": [{"role": "user", "content": prompt}],
        "stream": False, "think": False,
        "format": {"type": "object", "required": ["scores"], "properties": {
            "scores": {"type": "array", "items": {"type": "integer"}}}},
        "options": {"temperature": 0, "seed": 0},
    }).encode()
    req = urllib.request.Request(
        f"{_env('OLLAMA_URL', 'http://ollama:11434')}/api/chat", data=body,
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(json.load(resp)["message"]["content"])["scores"]


def rerank(query: str, hits: list, grade=llm_scores) -> list:
    """Re-order hits by LLM grade blended with the retrieval score; falls back on any failure.

    The LLM share (RERANK_WEIGHT, default 0.3) is a 0-1 grade, so a strong retrieval match
    can only be overturned by a clearly better passage, not by LLM noise.
    """
    if not hits[1:]:
        return hits
    try:
        scores = grade(query, [f"({Path(h[1]).name}) {h[3]}" for h in hits])
    except (OSError, ValueError, KeyError, TypeError):
        return hits
    if len(scores) != len(hits) or not all(isinstance(s, int | float) for s in scores):
        return hits
    weight = float(_env("RERANK_WEIGHT", "0.3"))
    blended = [(1 - weight) * hits[i][0] + weight * min(max(scores[i], 0), 10) / 10
               for i in range(len(hits))]
    order = sorted(range(len(hits)), key=lambda i: (-blended[i], i))
    return [hits[i] for i in order]

@mcp.tool()
def index_sources() -> str:
    """Build or refresh the search index over the configured source directories.

    Only new or changed files are re-embedded; deleted files are dropped.
    """
    size = int(_env("CHUNK_CHARS", "1200"))
    overlap = int(_env("CHUNK_OVERLAP", "200"))
    max_bytes = int(_env("MAX_FILE_BYTES", "200000"))
    conn = _db()
    seen, updated, chunks_added = set(), 0, 0
    for src in filter(None, _env("RAG_SOURCES", "/repo:/projects").split(os.pathsep)):
        root = Path(src)
        if not root.is_dir():
            continue
        for p in iter_files(root, max_bytes):
            key = str(p)
            seen.add(key)
            try:
                text = p.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            sha = hashlib.sha256(f"{CHUNKER_VERSION}\0{text}".encode()).hexdigest()
            row = conn.execute("SELECT sha FROM files WHERE path=?", (key,)).fetchone()
            if row and row[0] == sha:
                continue
            pieces = chunk_file(p, text, size, overlap)
            vecs = embed(pieces) if pieces else []
            conn.execute("DELETE FROM chunks WHERE path=?", (key,))
            rows = zip(pieces, vecs, strict=True)
            conn.executemany(
                "INSERT INTO chunks (path, idx, text, vec) VALUES (?,?,?,?)",
                [(key, i, t, json.dumps(v)) for i, (t, v) in enumerate(rows)])
            conn.execute("INSERT OR REPLACE INTO files VALUES (?,?)", (key, sha))
            updated += 1
            chunks_added += len(pieces)
    stale = [r[0] for r in conn.execute("SELECT path FROM files") if r[0] not in seen]
    for key in stale:
        conn.execute("DELETE FROM chunks WHERE path=?", (key,))
        conn.execute("DELETE FROM files WHERE path=?", (key,))
    conn.commit()
    total = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    conn.close()
    return (f"Indexed {updated} changed file(s), {chunks_added} new chunk(s), "
            f"removed {len(stale)} stale file(s). Total chunks: {total}.")


@mcp.tool()
def semantic_search(query: str, k: int = 5) -> str:
    """Semantic search over indexed project files. Returns the top-k matching chunks
    with file path, chunk number and similarity score. Run index_sources first."""
    k = max(1, min(k, 20))
    conn = _db()
    try:
        if not conn.execute("SELECT 1 FROM chunks LIMIT 1").fetchone():
            return "Index is empty. Run index_sources first."
        use_rerank = _env("RERANK", "0") == "1"
        pool = max(k, int(_env("RERANK_CANDIDATES", "15"))) if use_rerank else k
        hits = search_index(conn, embed([query])[0], pool, query=query)
        if use_rerank:
            hits = rerank(query, hits)[:k]
    finally:
        conn.close()
    return "\n\n".join(f"[{score:.3f}] {path} (chunk {idx})\n{text}"
                       for score, path, idx, text in hits)


if __name__ == "__main__":
    mcp.run()
