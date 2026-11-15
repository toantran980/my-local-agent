#!/usr/bin/env bash
set -euo pipefail

# Register the nightly triage agent in cron -> the JD's "scheduled agent work".
# Idempotent: re-running replaces the existing entry; never duplicates.
#
#   ./scripts/install-cron.sh                 # daily 5:00 PM (WSL local time)
#   CRON_HOUR=17 CRON_MIN=0 ./scripts/install-cron.sh
#
# Verifies afterwards with crontab -l. Log: logs/nightly-triage.log (WSL).

CRON_HOUR="${CRON_HOUR:-17}"
CRON_MIN="${CRON_MIN:-0}"
MARKER="my-local-agent-nightly-triage"
ROOT_WSL="$(cd "$(dirname "$0")/.." && pwd)"
LOG="$ROOT_WSL/logs/nightly-triage.log"
RUN_SCRIPT="$ROOT_WSL/scripts/run-nightly.sh"

mkdir -p "$ROOT_WSL/logs" "$ROOT_WSL/reports"

ENTRY="$CRON_MIN $CRON_HOUR * * * /usr/bin/bash $RUN_SCRIPT \$(date -I) >> $LOG 2>&1"

(
  crontab -l 2>/dev/null | grep -v -E "$MARKER|nightly-triage" || true
  echo "# $MARKER -- nightly triage agent (JD: scheduled agent work)"
  echo "$ENTRY"
) | crontab -

echo "installed cron:"
crontab -l | grep -A1 "$MARKER"
echo "-> runs at ${CRON_HOUR}:$(printf %02d "$CRON_MIN") daily; log: $LOG"
echo "verify: crontab -l"
if ! /usr/bin/bash "$RUN_SCRIPT" "$(date -I)"; then
  echo "-> immediate run failed; the scheduled cron entry remains installed" >&2
fi
