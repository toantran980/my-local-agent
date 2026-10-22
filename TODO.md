# TODO

Next steps, best fit first. Check items off as they land.

## Applied AI (agent and RAG quality)

- [x] **Reranking**: opt-in LLM rerank (`RERANK=1`, `RERANK_MODEL`, `RERANK_CANDIDATES`) with fallback on failure. Harder retrieval eval (28 queries, 18 docs) now separates the modes: vector 75%, hybrid 89%, reranked 93% (LLM grade blended at weight 0.3 with file names shown; weights 0.5 and 0.7 did worse). Reranking stays opt-in; next: try a larger reranker model.
- [x] **Tool-use eval (LLM-as-judge)**: `scripts/eval-tool-use.py` locally scores recent audited runs for tool choice, efficiency, and completion; also reports errors and duplicate calls.
- [x] **Guardrails**: tool arguments are validated against their schema and errors go back to the model; sampling (temperature/seed/max_tokens) is now actually applied on `/v1`.
- [x] **Query rewriting**: opt-in local rewrite (`QUERY_REWRITE=1`); original search is preserved and rewrite results are merged. Retrieval eval: 25/28 (89%), same as hybrid alone, so it remains off by default.
- [ ] **Model routing / self-consistency**: easy prompts to the 4B model, hard ones to `qwen3:14b`,
  or majority vote over several samples.
- [ ] **Conversation summarization**: compress old turns to stay inside the 16k context.
- [x] **Citation verification**: cited files must appear in this run's tool results; one retry, then flagged as unverified.
- [ ] **Code-aware RAG**: chunk `.py` files by function/class with `ast` instead of by markdown heading.
- [ ] **Native structured outputs**: use Ollama's `format` JSON schema (e.g. for plans and judge scores) so output can't be malformed.
- [ ] **Memory consolidation**: merge/expire `workspace/memory/` entries and keep only runs with a verified outcome.
- [ ] **Semantic cache**: reuse an answer when a new prompt is very close to an earlier one (existing embeddings).
- [ ] **Planner/executor split**: `qwen3:14b` writes the plan, `qwen3.5:4b` runs the steps.
- [ ] **Nightly anomaly detection**: statistical checks on GPU, VRAM and latency trends.

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
3. Code-aware RAG to improve search over Python source.
