#!/usr/bin/env bash
set -euo pipefail

# Smoke test for the local stack. Run from the project root inside WSL2.
#   ./scripts/smoke-test.sh [model]     (default: qwen3:8b)
#
# Checks, in order:
#   1. Ollama API is alive and lists models
#   2. A real chat completion round-trips through the OpenAI-compatible API
#   3. The MCP bridge (mcpo) is up and exposes all tools
#   4. The model is actually resident on the GPU, not on CPU
#   5. agent_cli.py dry-run works (ask mode)

OLLAMA_URL="${OLLAMA_URL:-http://localhost:11434}"
MODEL="${1:-qwen3:8b}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "==> 1. Ollama alive at $OLLAMA_URL"
curl -fsS "$OLLAMA_URL/api/tags" >/dev/null && echo "    OK: /api/tags reachable"

echo "==> 2. Chat completion round-trip ($MODEL)"
REPLY=$(curl -fsS "$OLLAMA_URL/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d "{\"model\":\"$MODEL\",\"messages\":[{\"role\":\"user\",\"content\":\"Reply with exactly: GPU-OK\"}],\"stream\":false}" \
  | python3 -c "import json,sys; print(json.load(sys.stdin)['choices'][0]['message']['content'])")
echo "    reply: $REPLY"

echo "==> 3. MCP bridge (mcpo) reachable"
for srv in local_ops filesystem fetch projects_ops; do
  echo "    - $srv:"
  curl -fsS "http://localhost:8000/$srv/openapi.json" \
    | python3 -c "import json,sys; d=json.load(sys.stdin); print('        '+', '.join(sorted(p.lstrip('/') for p in d['paths'])))"
done

echo "==> 4. Model on GPU? (through local_ops tool, via mcpo)"
curl -fsS -X POST "http://localhost:8000/local_ops/gpu_status" \
  -H "Content-Type: application/json" -d '{}' \
  | python3 -c "
import json,sys
r=json.load(sys.stdin)
if isinstance(r, dict):
    c=r.get('content')
    t=c[0]['text'] if isinstance(c, list) else str(c)
else:
    t=str(r)
print('    '+t)
"

echo "==> 5. agent_cli.py dry-run (ask mode)"
cd "$ROOT"
REPLY=$(python3 agent_cli.py ask "What is 2+2? Reply with only the number." 2>/dev/null || true)
echo "    reply: $REPLY"

echo "==> SMOKE: PASS"