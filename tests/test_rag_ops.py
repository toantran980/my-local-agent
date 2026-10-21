import importlib.util
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
