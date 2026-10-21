#!/usr/bin/env python3
# noqa: EXE001
"""Render eval history as a pass-rate table.

    python3 scripts/eval-summary.py [history.jsonl]

Reads eval/history.jsonl rows {ts, model, passed, total} and prints a
per-day, per-model table. This is the "how do we measure agent reliability"
artifact: one file that shows the trend across a month of runs.
"""

import json
import sys

path = sys.argv[1] if len(sys.argv) > 1 else "eval/history.jsonl"

rows = []
try:
    with open(path, encoding="utf-8") as f:
        rows = [json.loads(line) for line in f if line.strip()]
except FileNotFoundError:
    print(f"{path}: no history yet (run scripts/run-eval.sh first)")
    sys.exit(0)

print(f"{'date':<11} {'model':<20} {'pass':>5} {'total':>5} {'rate':>6}")
print("-" * 52)

all_p = sum(r["passed"] for r in rows)
all_t = sum(r["total"] for r in rows)

seen = set()
for r in sorted(rows, key=lambda x: x.get("ts", "")):
    key = (r.get("ts", "")[:10], r.get("model", "?"))
    if key in seen:
        continue
    seen.add(key)
    day = key[0]
    model = key[1]
    p = sum(x["passed"] for x in rows if (x.get("ts", "")[:10], x.get("model", "?")) == key)
    t = sum(x["total"] for x in rows if (x.get("ts", "")[:10], x.get("model", "?")) == key)
    rate = (p / t * 100) if t else 0
    print(f"{day:<11} {model:<20} {p:>5} {t:>5} {rate:>5.0f}%")

print("-" * 52)
rate = (all_p / all_t * 100) if all_t else 0
print(f"all-time: {all_p}/{all_t} ({rate:.0f}%) across {len(rows)} runs")

# Side-by-side model comparison. Runs from before latency logging have no "seconds".
by_model = {}
for r in rows:
    by_model.setdefault(r.get("model", "?").removeprefix("ollama/"), []).append(r)

print()
print(f"{'model':<20} {'runs':>4} {'pass':>9} {'rate':>6} {'latest':>7} {'avg s/run':>10}")
print("-" * 62)
for model, runs in sorted(by_model.items()):
    p = sum(x["passed"] for x in runs)
    t = sum(x["total"] for x in runs)
    latest = max(runs, key=lambda x: x.get("ts", ""))
    latest_rate = latest["passed"] / latest["total"] * 100 if latest["total"] else 0
    secs = [x["seconds"] for x in runs if "seconds" in x]
    avg = f"{sum(secs) / len(secs):.0f}" if secs else "-"
    rate = p / t * 100 if t else 0
    row = f"{model:<20} {len(runs):>4} {f'{p}/{t}':>9} {rate:>5.0f}%"
    print(f"{row} {latest_rate:>6.0f}% {avg:>10}")