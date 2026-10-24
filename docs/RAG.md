# Local retrieval

The `rag_ops` MCP server indexes local project files and provides semantic
search through mcpo. It reads from `/repo` and, when enabled, `/projects`.
Source files are never modified; the SQLite index is stored in
`/workspace/.rag/index.db`.

## Use

The first search indexes eligible sources. You can also refresh the index
explicitly:

```bash
curl -X POST http://localhost:8000/rag_ops/index_sources
curl -X POST http://localhost:8000/rag_ops/semantic_search \
  -H "Content-Type: application/json" \
  -d '{"query":"how is VRAM budgeted?","k":5}'
```

The indexer skips sensitive files and excluded build/runtime directories. It
chunks Markdown by heading, Python by top-level functions and classes, and
other supported text files into overlapping windows. Changed chunking behavior
requires re-indexing.

The `nomic-embed-text` model is used for embeddings:

```bash
ollama pull nomic-embed-text
python3 scripts/eval-rag.py
```

The retrieval evaluation reports hit@1 for vector-only and hybrid search. See
[QUICKSTART.md](../QUICKSTART.md#5-evaluation) for the full evaluation commands.

## Retrieval settings

| Setting | Default | Effect |
| --- | --- | --- |
| `HYBRID_WEIGHT` | `0.3` | Blends keyword overlap with vector similarity; `0` uses vector-only ranking |
| `QUERY_REWRITE` | disabled | Rewrites a query with the local chat model, then merges rewritten-query results with the original results |
| `QUERY_REWRITE_MODEL` | `qwen3:8b` | Local model used when query rewriting is enabled |

Set these in the `rag_ops` environment in [`mcpo/config.json`](../mcpo/config.json),
then restart mcpo. The original query is always searched. Rewrite failures are
reported and fall back to the original-query results; rewriting adds a local
model request per search.

The CLI's `semantic_search` tool refreshes the index once per run before
searching. It uses `RAG_URL` (default `http://localhost:8000/rag_ops`) to reach
mcpo.
