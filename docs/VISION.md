# Local vision tools

`vision_ops` adds an `ask_about_image` MCP tool backed by Ollama's local
multimodal chat endpoint. It reads a user-selected image and asks the configured
vision model a question; it does not edit the image. The mcpo configuration
sends the image to the host Ollama at `http://host.docker.internal:11434`.
Configure `OLLAMA_URL` only for a trusted local Ollama instance if images must
remain local.

## Setup

The default mcpo configuration uses `qwen2.5vl:7b`. Pull it into the Ollama
instance configured for this stack, or change `VISION_MODEL` to an installed
Ollama vision model:

```bash
ollama pull qwen2.5vl:7b
```

Place an image in the mounted `workspace/` directory, then call
`ask_about_image` with its path as seen inside the mcpo container, for example
`/workspace/example.png`, and a specific question. Supported formats are JPG,
JPEG, PNG, and WebP. Images are limited to 10 MiB by default.

## Access and limits

`VISION_IMAGE_DIRS` is an OS-path-separated allowlist of directories the server
can read; the default is `/workspace`. The server resolves symlinks before
checking the allowlist, rejects paths outside it, and does not search for images
or expose directory listings. Set `VISION_MAX_IMAGE_BYTES` to a positive byte
limit if a different limit is needed.

The answer depends on the selected model and image quality. Do not rely on it
for safety-critical interpretation, exact OCR, or guaranteed object detection.
Review the model output before acting on it. Keep the image directories mounted
as narrowly as possible.

## Evaluation

`eval/vision/` contains three generated, non-sensitive PNG fixtures covering
receipt OCR, a labeled bar chart, and colored-shape counting. Regenerate them
with the standard library:

```bash
python3 eval/vision/generate_fixtures.py
```

Run the local model against the cases with:

```bash
python3 scripts/eval-vision.py
# or: make eval-vision
```

The evaluator checks expected answer facts with simple keyword matching; it is
a quick regression signal, not a full measure of image understanding. It uses
`VISION_MODEL` (default `qwen2.5vl:7b`) and `OLLAMA_URL` (default
`http://localhost:11434`) and exits nonzero if any case errors or the default
100% threshold is missed. Override the threshold with `--threshold`, for
example `python3 scripts/eval-vision.py --threshold 0.67`.
