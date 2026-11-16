# TODO

Next steps, best fit first. Check items off as they land.

## Topic coverage

- [x] **vision (biggest gap)**: `mcp/vision_ops.py` MCP server with a multimodal
  Ollama model for read-only image question answering. See `docs/VISION.md`.
  - [ ] Add a small, non-sensitive image evaluation set for OCR, charts, and object questions.
  - [ ] Compare `qwen2.5vl:7b` with `qwen3-vl:8b` for answer quality, latency, and VRAM; update the default only if results justify it.
- [ ] **speech**: Whisper (`faster-whisper`) voice input and Piper voice output.
  - [ ] Add a local audio transcription tool with supported-format, file-size, and workspace-path limits.
  - [ ] Add optional local text-to-speech that writes output only under the workspace.
- [ ] **NLP**: sentiment / text-classification tool; LoRA fine-tune of a small model
  on audit trails.
  - [ ] Define a small labeled evaluation set before selecting a classifier or fine-tuning data.
  - [ ] Keep audit-trail training data redacted and opt-in.
- [ ] **generative AI**: local image generation (Stable Diffusion / ComfyUI) tool and a
  story-generation mode.
  - [ ] Prototype a local ComfyUI integration with generated files confined to the workspace.
  - [ ] Add an opt-in story-generation mode with bounded output and a regression prompt set.
- [ ] **HPC**: benchmark script for tokens/sec and VRAM across `qwen3` 4b / 8b / 14b.
  - [ ] Record model, hardware, context length, warm-up, tokens/sec, and peak VRAM per run.
  - [ ] Save machine-readable results so runs can be compared over time.

## Housekeeping

- [x] Check `PROJECTS.md` and `docs/` for stale references.
- [ ] Run the reflection and planner paths against a live model on more than one prompt.

## What next

1. Whisper voice input and Piper voice output.
2. Install and evaluate `qwen3:14b` routing on representative hard prompts.
3. Run the reflection and planner paths against a live model on more than one prompt.
