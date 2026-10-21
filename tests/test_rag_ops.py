import importlib.util
import json
import sys
from pathlib import Path

import pytest

pytest.importorskip("mcp.server.fastmcp")

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
