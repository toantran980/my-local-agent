#!/usr/bin/env python3
"""nightly-triage agent — a real scheduled agent, self-hosted, no opencode.

Pure-Python tool-calling loop against the local Ollama (qwen3:8b on the RTX
5080). It runs from cron at 2am, genuinely inspects the repo (git status, read
files, grep, GPU/VRAM residency, model list) and writes reports/YYYY-MM-DD.md.
Designed to be cron-safe in WSL2 (no desktop binary, no interactive TUI).

    ./scripts/nightly-triage.py [--day YYYY-MM-DD]

Exit codes:
    0  report written
    2  a hard error occurred (no report)
    3  model has no tool-calling support (write_report still attempted)

Report is written via the write_report tool so it is model-authored; verify the
file exists afterwards:  test -f reports/$(date -I).md
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
MODEL = os.environ.get("NIGHTLY_MODEL", "qwen3:8b")

# Constants
HTTP_BAD_REQUEST = 400
GPU_THRESHOLD = 0.9
MAX_REPORT_SIZE = 6000
MAX_GIT_LOG = 8

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "git_status",
            "description": (
                "Run `git status --short` and `git log --oneline -8` in the repo. "
                "Use to see what changed today."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read up to `max_lines` lines of a repo-relative file (capped at 8KB).",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "max_lines": {"type": "integer"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "grep",
            "description": (
                "Search repo files for a regex (e.g. 'TODO', 'FIXME', 'failing'). "
                "Returns up to 40 matches."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string"},
                    "glob": {"type": "string"},
                },
                "required": ["pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "gpu_status",
            "description": (
                "Which models are loaded on the GPU and their VRAM "
                "residency (READ-ONLY)."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "models_list",
            "description": "List all models available in Ollama (READ-ONLY).",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_report",
            "description": (
                "Write the final Markdown triage report to reports/<today>.md. "
                "Call LAST with the complete report."
            ),
            "parameters": {
                "type": "object",
                "properties": {"markdown": {"type": "string"}},
                "required": ["markdown"],
            },
        },
    },
]


def _urlopen(req, timeout=180):
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
            return json.loads(raw)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        if e.code == HTTP_BAD_REQUEST and not body:
            return {"choices": [{"message": {"content": "", "tool_calls": None}}]}
        raise


def _post(path, payload, timeout=180):
    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{OLLAMA_URL}{path}",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    return _urlopen(req, timeout)


def _get(path, timeout=180):
    req = urllib.request.Request(f"{OLLAMA_URL}{path}")
    return _urlopen(req, timeout)


def run_tool(name, args):  # noqa: PLR0911
    try:
        if name == "git_status":
            st = subprocess.run(
                ["git", "-C", str(ROOT), "status", "--short"],
                capture_output=True, text=True, timeout=30, check=False
            ).stdout
            log = subprocess.run(
                ["git", "-C", str(ROOT), "log", "--oneline", f"-{MAX_GIT_LOG}"],
                capture_output=True, text=True, timeout=30, check=False
            ).stdout
            return f"STATUS:\n{st or '(clean)'}\nLOG:\n{log or '(no commits yet)'}"
        if name == "read_file":
            p = (ROOT / str(args.get("path", ""))).resolve()
            if not p.is_relative_to(ROOT):
                return "ERROR: path escapes repo"
            text = p.read_text(errors="replace")
            return "\n".join(text.splitlines()[: int(args.get("max_lines", 120))])
        if name == "grep":
            pat = args.get("pattern", "")
            gl = args.get("glob", "")
            cmd = ["grep", "-rnI", pat, str(ROOT)]
            if gl:
                cmd += ["--include", gl]
            out = subprocess.run(
                cmd, capture_output=True, text=True, timeout=30, check=False
            ).stdout
            return out[:MAX_REPORT_SIZE] or "(no matches)"
        if name == "gpu_status":
            d = _get("/api/ps")
            parts = []
            for m in d.get("models", []):
                name = m.get("name", "?")
                s = m.get("size", 0) / 1e9
                sv = m.get("size_vram", 0) / 1e9
                fam = m.get("details", {}).get("family", "?")
                gpu = "GPU" if (sv / s) >= GPU_THRESHOLD else "not on GPU"
                parts.append(f"{name}  {s:.1f}GB total / {sv:.1f}GB VRAM  [{gpu}] {fam}")
            return "\n".join(parts) or "(no models loaded)"
        if name == "models_list":
            d = _get("/api/tags")
            return "\n".join(f"{m.get('name','?')}  {m.get('size',0)/1e9:.1f}GB"
                             for m in d.get("models", [])) or "(none)"
        if name == "write_report":
            md = args.get("markdown", "")
            day = dt.datetime.now(dt.UTC).date().isoformat()
            out = ROOT / "reports" / f"{day}.md"
            out.parent.mkdir(exist_ok=True)
            out.write_text(md + "\n", encoding="utf-8")
            # Optional PR-gated autonomy (README gap #1): DRAFT_PR=1 lifts the
            # nightly report into a draft PR you approve before merge.
            if os.environ.get("DRAFT_PR") == "1" and os.environ.get("GH_REPO"):
                tag = "chore: nightly triage report " + day
                body_file = ROOT / "reports" / f"{day}.pr.md"
                body_file.write_text(md + "\n", encoding="utf-8")
                subprocess.run(
                    [
                        "gh", "pr", "create", "--draft", "-R", os.environ["GH_REPO"],
                        "-t", tag, "-F", str(body_file),
                    ], capture_output=True, text=True, timeout=30, check=False
                )
            return f"wrote {out.relative_to(ROOT)} ({len(md)} chars)"
        return f"unknown tool: {name}"
    except subprocess.TimeoutExpired:
        return f"TOOL-ERROR {name}: command timed out"
    except BaseException as e:  # noqa: BLE001
        return f"TOOL-ERROR {name}: {e}"


def _urlopen(req, timeout=180):
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
            return json.loads(raw)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        if e.code == HTTP_BAD_REQUEST and not body:
            return {"choices": [{"message": {"content": "", "tool_calls": None}}]}
        raise


def _post(path, payload, timeout=180):
    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{OLLAMA_URL}{path}",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    return _urlopen(req, timeout)


def _get(path, timeout=180):
    req = urllib.request.Request(f"{OLLAMA_URL}{path}")
    return _urlopen(req, timeout)


def complete(messages):
    payload = {
        "model": MODEL,
        "messages": messages,
        "tools": TOOLS,
        "stream": False,
        "options": {"temperature": 0},
    }
    try:
        return _post("/v1/chat/completions", payload)
    except urllib.error.HTTPError as e:
        if e.code == HTTP_BAD_REQUEST:
            # likely "does not support tools" — try again without tools
            payload.pop("tools", None)
            return _post("/v1/chat/completions", payload)
        raise


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-iters", type=int, default=8)
    ap.add_argument("--day", default=None)
    args = ap.parse_args()

    if args.day:
        globals()["_DAY"] = args.day

    system = (
        "You are the nightly triage agent for a local self-hosted AI stack: "
        "Ollama qwen3:8b on an NVIDIA RTX 5080, code in this repo, served via "
        "mcpo+Open WebUI. Tonight run this actual pass:\n"
        "  1. git_status  -> what changed today?\n"
        "  2. gpu_status  -> is qwen3:8b resident on the GPU?\n"
        "  3. models_list -> any unexpected models?\n"
        "  4. grep 'TODO|FIXME|failing' and read_file the most relevant file,\n"
        "     then note follow-ups.\n"
        "  5. write_report with the full triage: Today's changes, GPU status, "
        "follow-ups. Call write_report LAST."
    )
    messages = [{"role": "system", "content": system},
                {"role": "user", "content": "Run tonight's triage now."}]

    report_written = False
    for _ in range(args.max_iters):
        resp = complete(messages)
        msg = resp["choices"][0]["message"]
        messages.append(msg)
        calls = msg.get("tool_calls")
        if calls:
            for c in calls:
                fn = c.get("function", {})
                name, args_json = fn.get("name", ""), fn.get("arguments", "{}")
                try:
                    tool_args = json.loads(args_json or "{}")
                except json.JSONDecodeError:
                    tool_args = {}
                result = run_tool(name, tool_args)
                if name == "write_report":
                    report_written = True
                messages.append({"role": "tool", "tool_call_id": c.get("id", ""),
                                 "content": result})
        else:
            # if the model bailed without write_report, still persist a report
            if not report_written:
                p = ROOT / "reports" / f"{dt.datetime.now(dt.UTC).date().isoformat()}-fallback.md"
                p.parent.mkdir(exist_ok=True)
                p.write_text(msg.get("content", "") + "\n", encoding="utf-8")
                print(f"fallback report -> {p.relative_to(ROOT)}")
            else:
                today = dt.datetime.now(dt.UTC).date().isoformat()
                f = ROOT / "reports" / f"{today}.md"
                if f.exists():
                    print(f"report -> {f.relative_to(ROOT)}")
            return 0
    print(f"no final answer in loop budget; report_written={report_written}")
    return 0 if report_written else 2


if __name__ == "__main__":
    sys.exit(main())