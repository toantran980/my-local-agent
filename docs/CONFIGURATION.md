# Configuration

The stack reads optional settings from the environment. Copy `.env.example` to
`.env` for Docker Compose settings. The CLI and scripts also read their
respective variables from the process environment.

## Agent and services

| Variable | Default | Purpose |
| --- | --- | --- |
| `MY_LOCAL_AGENT_ROOT` | Current directory | Repository root as a WSL path |
| `OLLAMA_URL` | `http://localhost:11434` | Ollama inference endpoint |
| `AGENT_MODEL` | `qwen3:8b` | Default CLI model |
| `AGENT_EASY_MODEL` / `AGENT_HARD_MODEL` | `qwen3.5:4b` / `qwen3:14b` | Models used by opt-in `--auto-route` |
| `AGENT_PLANNER_MODEL` / `AGENT_EXECUTOR_MODEL` | `qwen3:14b` / `qwen3.5:4b` | Models used by `--plan-first --split-models` |
| `AGENT_HISTORY_TOKEN_BUDGET` | `5000` | Approximate history threshold for interactive summarization |
| `AGENT_MEMORY` | Enabled | Set to `0` to disable verified run memory |
| `AGENT_MEMORY_DIR` | `workspace/memory/` | Location of verified run memory |
| `AGENT_SEMANTIC_CACHE` | Disabled | Set to `1` to enable the local Ask answer cache |
| `AGENT_CACHE_EMBED_MODEL` | `nomic-embed-text` | Embedding model for the semantic answer cache |
| `RAG_URL` | `http://localhost:8000/rag_ops` | mcpo endpoint used by the CLI's RAG tool |
| `NIGHTLY_MODEL` | `qwen3:8b` | Model used by nightly triage |
| `CRON_HOUR` / `CRON_MIN` | `17` / `0` | Nightly triage schedule |
| `DRAFT_PR` / `GH_REPO` | `0` / unset | Enable draft PR creation and select its repository |
| `ADMIN_USER` / `ADMIN_PASSWORD` | `admin` / `changeme` | Auth proxy credentials; change before enabling the profile |
| `OLLAMA_CONTEXT_LENGTH` | `16384` | Ollama context length configured by Compose |

RAG-specific settings (`HYBRID_WEIGHT`, `QUERY_REWRITE`, and
`QUERY_REWRITE_MODEL`) are documented in [RAG.md](RAG.md).

## GPU memory guidance

The default deployment targets a 16 GB GPU:

| Model | Approximate weights + KV at 16k context | Guidance |
| --- | --- | --- |
| `qwen3:8b` | 7 GB | Default model |
| `qwen3:14b` | 11 GB | Fits with the configured context |
| `qwen3:30b` | — | Exceeds the available budget |

Keep model weights, KV cache, and at least 1 GB of headroom below roughly
14.5 GB total. Actual use varies with quantization and runtime settings. See
[QUICKSTART.md](../QUICKSTART.md) for starting the stack and checking GPU
residency.
