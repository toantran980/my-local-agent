#!/usr/bin/env python3
"""One-time viewer: render today's agent audit trail as plain text so the
user can see — with zero quoting drama — what the agent actually did in its
10-step real-task run before the safety cap stopped it.

Usage: python3 scripts/tail-audit.py [path-to-jsonl]
"""
import json
import pathlib
import sys

ROOT = pathlib.Path(r"C:\Users\toant\Desktop\my-local-agent")
candidates = sorted(ROOT.glob(".agent/audit/2026-09-16*.jsonl"), reverse=True)
default = candidates[0] if candidates else None
path = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else default
if path is None or not path.exists():
    print("no audit trail found")
    raise SystemExit(1)

print(f"== {path.name} ==")
for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
    if not line.strip():
        continue
    try:
        r = json.loads(line)
    except BaseException:  # noqa: BLE001
        print("  !! unparseable line")
        continue
    tool = r.get("tool") or r.get("name") or "?"
    step = r.get("seq") or r.get("step") or "?"
    ts = r.get("ts") or ""
    args = r.get("args") or r.get("input") or r.get("request") or {}
    if isinstance(args, dict):
        args = " ".join(f"{k}={v}" for k, v in args.items())
    print(f"#{step}  [{tool}]  {ts}")
    print(f"    in : {str(args)[:140]}")
    out = r.get("out") or r.get("result") or r.get("reply") or ""
    print(f"    out: {str(out)[:140]}")
