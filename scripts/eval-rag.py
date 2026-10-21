"""Retrieval eval: does semantic_search surface the right file in its top-k?

Indexes eval/rag/docs into a throwaway database and checks every case in
eval/rag/cases.json ({"query": ..., "expected": "file name"}). Needs Ollama
with the embedding model pulled. Prints hit@k and exits non-zero below THRESHOLD.

  OLLAMA_URL   (default http://localhost:11434)
  EMBED_MODEL  (default nomic-embed-text)
  TOP_K        (default 1)
  THRESHOLD    minimum hit rate 0-1 (default 0.8)
"""

import importlib.util
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAG_DIR = ROOT / "eval" / "rag"


def load_rag():
    spec = importlib.util.spec_from_file_location("rag_ops", ROOT / "mcp" / "rag_ops.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    os.environ.setdefault("OLLAMA_URL", "http://localhost:11434")
    top_k = int(os.environ.get("TOP_K", "1"))
    threshold = float(os.environ.get("THRESHOLD", "0.8"))
    cases = json.loads((RAG_DIR / "cases.json").read_text(encoding="utf-8"))

    with tempfile.TemporaryDirectory() as tmp:
        os.environ["RAG_SOURCES"] = str(RAG_DIR / "docs")
        os.environ["RAG_DB"] = str(Path(tmp) / "index.db")
        rag = load_rag()
        print(rag.index_sources())
        conn = rag._db()
        hits = 0
        for case in cases:
            qvec = rag.embed([case["query"]])[0]
            found = [Path(path).name for _, path, _, _ in rag.search_index(conn, qvec, top_k)]
            ok = case["expected"] in found
            hits += ok
            print(f"{'PASS' if ok else 'FAIL'}  {case['query']!r} -> {found}")
        conn.close()

    rate = hits / len(cases)
    print(f"hit@{top_k}: {hits}/{len(cases)} = {rate:.0%} (threshold {threshold:.0%})")
    return 0 if rate >= threshold else 1


if __name__ == "__main__":
    sys.exit(main())
