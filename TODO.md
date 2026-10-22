# TODO

Next steps, best fit first. Check items off as they land.

## Applied AI (agent and RAG quality)

- [x] **Reranking**: opt-in LLM rerank (`RERANK=1`, `RERANK_MODEL`, `RERANK_CANDIDATES`) with fallback on failure. On the earlier 28-query / 18-doc set: vector 75%, hybrid 89%, reranked 93% (LLM grade blended at weight 0.3 with file names shown; weights 0.5 and 0.7 did worse). Reranking stays opt-in; next: remeasure against the expanded code-aware set.
- [x] **Tool-use eval (LLM-as-judge)**: `scripts/eval-tool-use.py` locally scores recent audited runs for tool choice, efficiency, and completion; also reports errors and duplicate calls.
- [x] **Guardrails**: tool arguments are validated against their schema and errors go back to the model; sampling (temperature/seed/max_tokens) is now actually applied on `/v1`.
- [x] **Query rewriting**: opt-in local rewrite (`QUERY_REWRITE=1`); original search is preserved and rewrite results are merged. On the earlier 28-query set it matched hybrid at 25/28 (89%), so it remains off by default.
- [x] **Model routing**: opt-in `--auto-route` / `/route on` selects `qwen3.5:4b` or `qwen3:14b` from prompt complexity; unavailable models visibly fall back to `--model`. The 14B model is not installed here yet.
- [x] **Conversation summarization**: interactive history is summarized above an estimated 5k-token budget, retaining the latest two turns. Failed summaries keep the original history and report the error.
- [x] **Citation verification**: cited files must appear in this run's tool results; one retry, then flagged as unverified.
- [x] **Code-aware RAG**: Python files are split by top-level function/class via `ast`; invalid or incomplete source falls back to windows. Chunker version bump rebuilds existing indexes.
- [x] **Native structured outputs**: plan mode uses Ollama's JSON-schema `format`, validates every required field, and formats the validated plan; the eval judge already uses schema-constrained scores.
- [x] **Memory consolidation**: persist only redacted Agent outcomes with passing verification; remove unverified entries, expire entries older than 30 days, and cap retained entries.
- [x] **Semantic cache**: opt-in (`AGENT_SEMANTIC_CACHE=1`) local SQLite cache for redacted, tool-free Ask answers, using Ollama embeddings, a 0.96 cosine threshold, 24-hour expiry, and a 100-entry cap.
- [x] **Planner/executor split**: `agent --plan-first --split-models` uses `AGENT_PLANNER_MODEL` (`qwen3:14b`) and `AGENT_EXECUTOR_MODEL` (`qwen3.5:4b`); missing models visibly fall back to `--model`. The 14B path is covered by mocks because that model is not installed here.
- [x] **Nightly anomaly detection**: append duration and parsed per-model VRAM to gitignored `reports/telemetry.jsonl`; report robust median/MAD upper outliers after a five-sample baseline.

## Topic coverage

- [ ] **vision (biggest gap)**: `mcp/vision_ops.py` MCP server with a multimodal model
  (`llava` / `qwen2.5-vl`) or `torchvision` for classification, OCR/digits and detection.
  Optional: tiny MNIST CNN served as a tool.
- [ ] **speech**: Whisper (`faster-whisper`) voice input and Piper voice output.
- [ ] **NLP**: sentiment / text-classification tool; LoRA fine-tune of a small model
  on audit trails.
- [ ] **generative AI**: local image generation (Stable Diffusion / ComfyUI) tool and a
  story-generation mode.
- [ ] **HPC**: benchmark script for tokens/sec and VRAM across `qwen3` 4b / 8b / 14b.

## Housekeeping

- [ ] Check `PROJECTS.md` and `docs/` for stale references.
- [ ] Run the reflection and planner paths against a live model on more than one prompt.

## What next

1. `vision_ops` to cover the CNN / computer-vision weeks.
2. Whisper voice input.
3. Install and evaluate `qwen3:14b` routing on representative hard prompts.
