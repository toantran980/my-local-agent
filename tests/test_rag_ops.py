import importlib.util
import json
import sys
from pathlib import Path

import pytest

pytest.importorskip("mcp.server.fastmcp")

PYTHON_SYMBOL_CHUNKS = 4
PYTHON_CHUNK_SIZE = 100

spec = importlib.util.spec_from_file_location(
    "rag_ops", Path(__file__).parent.parent / "mcp" / "rag_ops.py")
rag = importlib.util.module_from_spec(spec)
sys.modules["rag_ops"] = rag
spec.loader.exec_module(rag)


def test_chunk_text_overlaps_and_covers_text():
    text = "abcdefghij" * 10
    size = 30
    chunks = rag.chunk_text(text, size, 10)
    assert all(len(c) <= size for c in chunks)
    assert chunks[0][-10:] == chunks[1][:10]
    assert chunks[-1].endswith(text[-5:])


def test_chunk_text_empty_and_bad_size():
    assert rag.chunk_text("   ", 10, 2) == []
    with pytest.raises(ValueError):
        rag.chunk_text("x", 0, 0)


def test_cosine():
    assert rag.cosine([1, 0], [1, 0]) == pytest.approx(1.0)
    assert rag.cosine([1, 0], [0, 1]) == pytest.approx(0.0)
    assert rag.cosine([0, 0], [1, 1]) == 0.0


def test_iter_files_skips_sensitive_and_excluded(tmp_path):
    (tmp_path / "a.py").write_text("x")
    (tmp_path / ".env").write_text("SECRET=1")
    (tmp_path / "server.key").write_text("k")
    (tmp_path / "img.png").write_bytes(b"\x00")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config.txt").write_text("x")
    names = {p.name for p in rag.iter_files(tmp_path, 1000)}
    assert names == {"a.py"}


def test_chunk_markdown_prefixes_heading_path():
    text = "# Top\nintro\n## Sub\nbody text\n```\n# not a heading\n```\n"
    chunks = rag.chunk_markdown(text, 500, 50)
    assert any(c.startswith("Top\n") and "intro" in c for c in chunks)
    assert any(c.startswith("Top > Sub\n") and "# not a heading" in c for c in chunks)


def test_chunk_markdown_splits_long_sections_within_size():
    size = 100
    chunks = rag.chunk_markdown("## Big\n" + "word " * 200, size, 10)
    assert len(chunks) > 1
    assert all(len(c) <= size and c.startswith("Big\n") for c in chunks)


def test_chunk_python_splits_top_level_symbols_and_keeps_context():
    source = '''"""Module docs."""
import pathlib
DEFAULT_SIZE = 10

@decorator
def load_index(path):
    """Load the index from disk."""
    return pathlib.Path(path).read_text()

class Index:
    def search(self, query):
        return query

async def refresh_index():
    return None
'''

    chunks = rag.chunk_python(source, size=500, overlap=40)

    assert len(chunks) == PYTHON_SYMBOL_CHUNKS
    assert "Python module statements" in chunks[0]
    assert "DEFAULT_SIZE = 10" in chunks[0]
    assert "Python function: load_index" in chunks[1]
    assert "@decorator" in chunks[1]
    assert "Load the index from disk" in chunks[1]
    assert "Python class: Index" in chunks[2]
    assert "def search(self, query)" in chunks[2]
    assert "Python async function: refresh_index" in chunks[3]


def test_chunk_python_splits_large_symbols_and_bounds_chunks():
    source = "def work():\n" + "    result = 1\n" * 100

    chunks = rag.chunk_python(source, size=PYTHON_CHUNK_SIZE, overlap=10)

    assert len(chunks) > 1
    assert all(len(chunk) <= PYTHON_CHUNK_SIZE for chunk in chunks)
    assert "Python function: work" in chunks[0]


def test_chunk_python_falls_back_for_incomplete_source():
    source = "def unfinished(:\n" + "x = 1\n" * 20

    assert rag.chunk_python(source, size=20, overlap=5) == rag.chunk_text(
        source, size=20, overlap=5
    )


def test_chunk_file_uses_ast_for_python():
    chunks = rag.chunk_file(Path("sample.py"), "def find_user():\n    return None\n", 100, 10)

    assert len(chunks) == 1
    assert "Python function: find_user" in chunks[0]


def test_keyword_score_ignores_stopwords():
    assert rag.keyword_score("what is the port", "The port is 8000") == pytest.approx(1.0)
    assert rag.keyword_score("port banana", "port 8000") == pytest.approx(0.5)
    assert rag.keyword_score("the of", "anything") == 0.0


def test_hybrid_weight_can_reorder_results(tmp_path, monkeypatch):
    monkeypatch.setenv("RAG_DB", str(tmp_path / "i.db"))
    conn = rag._db()
    rows = [("a.md", 0, "unrelated words", [1.0, 0.0]),
            ("b.md", 0, "rare keyword zebra here", [0.8, 0.6])]
    conn.executemany("INSERT INTO chunks (path, idx, text, vec) VALUES (?,?,?,?)",
                     [(p, i, t, json.dumps(v)) for p, i, t, v in rows])
    qvec = [1.0, 0.0]
    vector_only = rag.search_index(conn, qvec, 1, query="zebra", hybrid_weight=0.0)
    hybrid = rag.search_index(conn, qvec, 1, query="zebra", hybrid_weight=0.5)
    conn.close()
    assert vector_only[0][1] == "a.md"
    assert hybrid[0][1] == "b.md"


def test_index_and_search_roundtrip(tmp_path, monkeypatch):
    src = tmp_path / "src"
    src.mkdir()
    (src / "gpu.md").write_text("The GPU is an RTX 5080.")
    (src / "cook.md").write_text("Pasta needs salted water.")
    monkeypatch.setenv("RAG_SOURCES", str(src))
    monkeypatch.setenv("RAG_DB", str(tmp_path / "idx" / "i.db"))

    def fake_embed(texts):
        return [[1.0, 0.0] if ("GPU" in t or "graphics" in t) else [0.0, 1.0] for t in texts]

    monkeypatch.setattr(rag, "embed", fake_embed)
    assert "2 changed file(s)" in rag.index_sources()
    assert "0 changed file(s)" in rag.index_sources()
    out = rag.semantic_search("which graphics card?", k=1)
    assert "gpu.md" in out and "cook.md" not in out

    (src / "cook.md").unlink()
    assert "removed 1 stale" in rag.index_sources()


def test_rerank_orders_by_score_and_keeps_ties_stable():
    hits = [(0.9, "a", 0, "A"), (0.8, "b", 0, "B"), (0.7, "c", 0, "C")]
    out = rag.rerank("q", hits, grade=lambda q, texts: [3, 9, 3])
    assert [h[1] for h in out] == ["b", "a", "c"]


def test_rerank_falls_back_on_errors_and_bad_output():
    hits = [(0.9, "a", 0, "A"), (0.8, "b", 0, "B")]

    def boom(q, texts):
        raise OSError("down")

    assert rag.rerank("q", hits, grade=boom) == hits
    assert rag.rerank("q", hits, grade=lambda q, t: [1]) == hits
    assert rag.rerank("q", hits, grade=lambda q, t: ["x", "y"]) == hits
    assert rag.rerank("q", hits[:1], grade=boom) == hits[:1]


def test_rewrite_query_uses_local_ollama_and_validates_result(monkeypatch):
    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self):
            return json.dumps({"message": {"content": json.dumps(
                {"query": "GPU memory budget RTX 5080"}
            )}}).encode()

    captured = {}

    def open_request(request, timeout):
        captured["url"] = request.full_url
        captured["payload"] = json.loads(request.data)
        captured["timeout"] = timeout
        return Response()

    monkeypatch.setattr(rag.urllib.request, "urlopen", open_request)
    rewritten = rag.rewrite_query("How much room is left for a bigger model?")

    assert rewritten == "GPU memory budget RTX 5080"
    assert captured["url"].endswith("/api/chat")
    assert captured["payload"]["format"]["required"] == ["query"]
    assert captured["payload"]["options"]["temperature"] == 0


def test_rewrite_query_rejects_invalid_response(monkeypatch):
    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self):
            return json.dumps({"message": {"content": '{"query": "  "}'}}).encode()

    monkeypatch.setattr(rag.urllib.request, "urlopen", lambda *_args, **_kwargs: Response())
    with pytest.raises(ValueError, match="empty or invalid"):
        rag.rewrite_query("vague query")


def test_merge_search_results_keeps_union_and_best_score():
    primary = [(0.8, "a.md", 0, "A"), (0.5, "b.md", 1, "B")]
    secondary = [(0.9, "b.md", 1, "B"), (0.7, "c.md", 0, "C")]

    assert [hit[1] for hit in rag.merge_search_results(primary, secondary, 3)] == [
        "b.md", "a.md", "c.md"
    ]


def test_semantic_search_rewrite_expands_candidates_and_preserves_original(tmp_path, monkeypatch):
    monkeypatch.setenv("RAG_DB", str(tmp_path / "index.db"))
    monkeypatch.setenv("QUERY_REWRITE", "1")
    monkeypatch.setenv("RERANK", "0")
    conn = rag._db()
    conn.execute(
        "INSERT INTO chunks (path, idx, text, vec) VALUES (?,?,?,?)",
        ("memory.md", 0, "RTX 5080 has 16 GB of VRAM", json.dumps([1.0, 0.0])),
    )
    conn.execute(
        "INSERT INTO chunks (path, idx, text, vec) VALUES (?,?,?,?)",
        ("unrelated.md", 0, "A separate topic", json.dumps([0.6, 0.8])),
    )
    conn.commit()
    conn.close()
    monkeypatch.setattr(rag, "rewrite_query", lambda _query: "GPU VRAM memory budget")
    monkeypatch.setattr(
        rag, "embed",
        lambda texts: [[1.0, 0.0] if "GPU VRAM" in text else [0.0, 1.0] for text in texts],
    )

    result = rag.semantic_search("How much room is left?", k=1)

    assert "memory.md" in result
    assert "16 GB of VRAM" in result
    assert "unrelated.md" not in result


def test_semantic_search_reports_rewrite_fallback(tmp_path, monkeypatch):
    monkeypatch.setenv("RAG_DB", str(tmp_path / "index.db"))
    monkeypatch.setenv("QUERY_REWRITE", "1")
    monkeypatch.setenv("RERANK", "0")
    conn = rag._db()
    conn.execute(
        "INSERT INTO chunks (path, idx, text, vec) VALUES (?,?,?,?)",
        ("memory.md", 0, "Original query match", json.dumps([1.0, 0.0])),
    )
    conn.commit()
    conn.close()
    monkeypatch.setattr(rag, "rewrite_query", lambda _query: (_ for _ in ()).throw(OSError("down")))
    monkeypatch.setattr(rag, "embed", lambda _texts: [[1.0, 0.0]])

    result = rag.semantic_search("original query", k=1)

    assert "Query rewrite unavailable" in result
    assert "memory.md" in result