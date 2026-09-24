#!/usr/bin/env bash
set -eu

# Golden-prompt eval harness -> the reliability number (see scripts/eval-summary.py).
#
# Model is queried through Ollama's OpenAI-compatible endpoint directly
# (http://localhost:11434/v1/chat/completions) -- the SAME path scripts/smoke-test.sh
# proves working. This deliberately does NOT shell out to `opencode run`:
# on this machine the `opencode` on PATH is the Desktop app binary
# (@opencode-aidesktop/OpenCode.exe, OPENCODE_CLIENT=desktop), which emits no
# stdout when invoked from a headless shell, so `opencode run ... | grep expected`
# would always fail. The harness is CLI-free and MCP-free by design.
#
# Case files live in eval/cases/*.json and fixtures in eval/fixtures/:
#   { "prompt": "...", "expected": "...", "dir": "optional/relative/dir" }
# Fixture contents are embedded into the prompt so the run is cwd-independent.
#
#   ./scripts/run-eval.sh [model]        (default: ollama/qwen3:8b)

MODEL="${1:-ollama/qwen3:8b}"
OLLAMA_URL="${OLLAMA_URL:-http://localhost:11434}"
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
cd "$ROOT"

mkdir -p eval
[ -f eval/history.jsonl ] || : > eval/history.jsonl

# pipe fixture contents (if the case has a "dir") into the prompt
build_prompt() { # $1 = case file
  local casefile="$1" basedir
  basedir="$(python3 -c "import json,sys; print(json.load(open('$casefile')).get('dir',''))" 2>/dev/null || true)"
  if [ -z "$basedir" ] || [ ! -d "$basedir" ]; then
    python3 -c "import json,sys; print(json.load(open('$casefile'))['prompt'])" > "$TMP"
    return
  fi
  {
    python3 -c "import json,sys; print(json.load(open('$casefile'))['prompt'])"
    echo
    echo "--- files in $basedir ---"
    for f in "$basedir"/*; do
      [ -f "$f" ] || continue
      echo "--- $f ---"
      cat "$f"
      echo
    done
  } > "$TMP"
}

ask_model() { # $1 = prompt file; echoes the reply text
  python3 - "$OLLAMA_URL" "$MODEL" "$1" <<'PY'
import json, sys, urllib.request

url, model, prompt_file = sys.argv[1], sys.argv[2], sys.argv[3]
model = model.split("/", 1)[-1]  # Ollama wants the bare name: qwen3:8b, NOT ollama/qwen3:8b
prompt = open(prompt_file).read()
body = json.dumps({
    "model": model,
    "messages": [{"role": "user", "content": prompt}],
    "stream": False,
    "options": {"temperature": 0, "num_predict": 2048, "num_ctx": 8192},
}).encode()
req = urllib.request.Request(f"{url}/v1/chat/completions", data=body,
                             headers={"Content-Type": "application/json"})
with urllib.request.urlopen(req, timeout=300) as resp:
    data = json.load(resp)
print(data["choices"][0]["message"]["content"])
PY
}

TMP="$(mktemp)"
trap 'rm -f "$TMP"' EXIT

passed=0
total=0
failures=()
for casefile in eval/cases/*.json; do
  name="$(basename "$casefile" .json)"
  build_prompt "$casefile"
  reply="$(ask_model "$TMP" 2>/dev/null || true)"
  expected="$(python3 -c "import json,sys; print(json.load(open('$casefile'))['expected'])")"
  total=$((total + 1))
  if printf '%s' "$reply" | grep -qiF "$expected"; then
    passed=$((passed + 1))
    echo "PASS  $name"
  else
    echo "FAIL  $name"
    echo "      expected substring: $expected"
    echo "      reply head: $(printf '%s' "$reply" | head -c 120)"
    failures+=("$name")
  fi
done

TS="$(python3 -c 'import datetime; print(datetime.datetime.now(datetime.timezone.utc).isoformat())')"
python3 - "$TS" "$MODEL" "$passed" "$total" <<'PY'
import json, sys
ts, model, p, t = sys.argv[1:]
with open("eval/history.jsonl", "a") as fh:
    fh.write(json.dumps({"ts": ts, "model": model,
                         "passed": int(p), "total": int(t)}) + "\n")
PY

echo "----"
echo "RESULT: $passed/$total passed ($MODEL)"
[ ${#failures[@]} -eq 0 ] || echo "failures: ${failures[*]}"
