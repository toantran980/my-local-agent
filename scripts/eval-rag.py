"""Retrieval eval: does semantic_search surface the right file in its top-k?

Indexes eval/rag/docs into a throwaway database and checks every case in
eval/rag/cases.json ({"query": ..., "expected": "file name"}). Needs Ollama
with the embedding model pulled. Prints hit@k and exits non-zero below THRESHOLD.

  OLLAMA_URL   (default http://localhost:11434)
  EMBED_MODEL  (default nomic-embed-text)
  TOP_K        (default 1)
  HYBRID_WEIGHT keyword share for the hybrid run (default 0.3)
  QUERY_REWRITE=1 also evaluates original + rewritten query retrieval
  THRESHOLD    minimum hybrid hit rate 0-1 (default 0.8)
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
        qvecs = [rag.embed([case["query"]])[0] for case in cases]
        weight = float(os.environ.get("HYBRID_WEIGHT", "0.3"))
        rates = {}
        modes = [("vector", 0.0), ("hybrid", weight)]
        if os.environ.get("QUERY_REWRITE") == "1":
            modes.append(("rewrite", weight))
        if os.environ.get("RERANK") == "1":
            modes.append(("reranked", weight))
        for label, w in modes:
            hits = 0
            for case, qvec in zip(cases, qvecs, strict=True):
                pool = max(top_k, 15) if label == "reranked" else top_k
                ranked = rag.search_index(conn, qvec, pool, query=case["query"], hybrid_weight=w)
                if label == "rewrite":
                    rewritten = rag.rewrite_query(case["query"])
                    if rewritten.casefold() != case["query"].casefold():
                        rewritten_vec = rag.embed([rewritten])[0]
                        rewritten_hits = rag.search_index(
                            conn, rewritten_vec, pool, query=case["query"], hybrid_weight=w
                        )
                        ranked = rag.merge_search_results(ranked, rewritten_hits, pool)
                if label == "reranked":
                    ranked = rag.rerank(case["query"], ranked)[:top_k]
                found = [Path(path).name for _, path, _, _ in ranked]
                ok = case["expected"] in found
                hits += ok
                if label in ("hybrid", "rewrite") or not ok:
                    print(f"{'PASS' if ok else 'FAIL'}  [{label}] {case['query']!r} -> {found}")
            rates[label] = hits / len(cases)
            print(f"hit@{top_k} {label}: {hits}/{len(cases)} = {rates[label]:.0%}")
        conn.close()

    rate = rates["hybrid"]
    print(f"gate (hybrid): {rate:.0%} vs threshold {threshold:.0%}")
    return 0 if rate >= threshold else 1


if __name__ == "__main__":
    sys.exit(main())
