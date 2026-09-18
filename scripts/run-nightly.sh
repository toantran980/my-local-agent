#!/usr/bin/env bash
set -euo pipefail

# Allow override via env; default to repo root (parent of this script's dir)
ROOT="${MY_LOCAL_AGENT_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
LOG="$ROOT/logs/nightly-triage.log"
SCRIPT="$ROOT/scripts/nightly-triage.py"
DAY="${1:-$(date -I)}"

mkdir -p "$ROOT/logs" "$ROOT/reports"

# Wait for Ollama API (max 5 minutes)
echo "[$(date)] Waiting for Ollama at http://localhost:11434..." | tee -a "$LOG"
for i in {1..60}; do
    if curl -sf http://localhost:11434/api/tags >/dev/null 2>&1; then
        echo "[$(date)] Ollama ready" | tee -a "$LOG"
        break
    fi
    sleep 5
    if (( i == 60 )); then
        echo "[$(date)] ERROR: Ollama not ready after 5 minutes" | tee -a "$LOG"
        exit 1
    fi
done

echo "[$(date)] Starting nightly triage for $DAY" | tee -a "$LOG"
/usr/bin/python3 "$SCRIPT" --day "$DAY" >> "$LOG" 2>&1
EXIT=$?
echo "[$(date)] Finished with exit=$EXIT" | tee -a "$LOG"
exit $EXIT