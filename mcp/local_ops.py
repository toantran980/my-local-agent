"""local_ops - a self-authored MCP server for the local agent.

Gives the agent visibility into THIS setup's own operational state:
nightly reports, eval history, the file sandbox, git state of a working
repo, which model Ollama has loaded in VRAM, and project directory access.

Everything reads local files or localhost services - no external APIs.

Runs as a stdio MCP server; the mcpo container exposes it to Open WebUI as
an OpenAPI tool server at http://mcpo:8000/local_ops.

Env overrides (defaults match the compose mounts):
  REPO_DIR       git tools        (default /repo)
  REPORTS_DIR    nightly          (default /data/agent-reports)
  EVAL_FILE      history jsonl    (default /data/eval/history.jsonl)
  WORKSPACE      sandbox          (default /workspace)
  PROJECTS_DIR   project dirs     (default /projects)
  CONFIGS_DIR    config files     (default /configs)
  OLLAMA_URL     ollama API       (default http://ollama:11434)
"""

import json
import os
import shutil
import subprocess
import urllib.request
from pathlib import Path

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("local-ops")


def _env(key, default):
    return os.environ.get(key, default)


def _run(cmd, cwd=None):
    try:
        r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=30, check=False)
        return (r.stdout or r.stderr).strip() or "(no output)"
    except FileNotFoundError:
        return "required binary not available in this container"
    except subprocess.TimeoutExpired:
        return "error: command timed out"
    except BaseException as e:  # noqa: BLE001
        return f"error: {e}"


@mcp.tool()
def git_state(repo_dir: str | None = None) -> str:
    """Show git state of a repo: last 5 commits and working-tree changes."""
    path = repo_dir or _env("REPO_DIR", "/repo")
    inside = subprocess.run(
        ["git", "-C", path, "rev-parse", "--is-inside-work-tree"],
        capture_output=True,
        check=False
    ).returncode == 0
    if not inside:
        return f"{path} is not a git repository (nothing to show)."
    commits = _run(["git", "-C", path, "-c", f"safe.directory={path}", "log", "-5", "--oneline"])
    changes = _run(["git", "-C", path, "-c", f"safe.directory={path}", "status", "--short"])
    return f"repo: {path}\nlast commits:\n{commits}\nchanges:\n{changes or '(clean)'}"


@mcp.tool()
def latest_nightly_report(max_chars: int = 4000) -> str:
    """Return the most recent nightly triage report from agent-reports/."""
    d = Path(_env("REPORTS_DIR", "/data/agent-reports"))
    files = sorted(d.glob("*.md")) if d.is_dir() else []
    if not files:
        return "No nightly reports yet. Run scripts/nightly-triage.sh first."
    p = files[-1]
    return f"== {p.name} ==\n" + p.read_text(errors="replace")[:max_chars]


@mcp.tool()
def eval_history(runs: int = 10) -> str:
    """Summarize the last N eval runs (the reliability trend)."""
    f = Path(_env("EVAL_FILE", "/data/eval/history.jsonl"))
    rows = []
    if f.is_file():
        lines = f.read_text(errors="replace").splitlines()
        rows = [json.loads(line) for line in lines if line.strip()]
    rows = rows[-runs:]
    if not rows:
        return "No eval history yet. Run scripts/run-eval.sh first."
    return "\n".join(
        f"{i}. {r.get('ts', '?')}  {r.get('model', '?')}: {r.get('passed')}/{r.get('total')}"
        for i, r in enumerate(rows, 1)
    )


@mcp.tool()
def sandbox_files(top: int = 20) -> str:
    """List the files the agent has created in the workspace sandbox."""
    d = Path(_env("WORKSPACE", "/workspace"))
    if not d.is_dir():
        return f"{d} does not exist"
    items = sorted(p for p in d.rglob("*") if p.is_file())[:top]
    if not items:
        return f"{d} is empty"
    return "\n".join(f"{p}  ({p.stat().st_size} bytes)" for p in items)


@mcp.tool()
def gpu_status() -> str:
    """Report which model Ollama has loaded and how much VRAM it uses."""
    url = _env("OLLAMA_URL", "http://ollama:11434") + "/api/ps"
    try:
        with urllib.request.urlopen(url, timeout=5) as r:
            data = json.load(r)
    except Exception as e:  # noqa: BLE001
        return f"cannot reach Ollama at {url}: {e}"
    if not data.get("models"):
        return "no model currently loaded"
    lines = []
    for m in data["models"]:
        vram = m.get("size_vram") or 0
        size = m.get("size") or 0
        lines.append(
            f"{m.get('model') or m.get('name')}  {vram / 1e9:.1f} GB VRAM "
            f"({size / 1e9:.1f} GB total)  family={m.get('details', {}).get('family', '?')}"
        )
    return "\n".join(lines)


@mcp.tool()
def projects_overview(base_dir: str = "/projects") -> str:
    """Show overview of available project directories."""
    d = Path(base_dir)
    if not d.is_dir():
        return f"Projects directory not found: {base_dir}"
    
    projects = []
    for item in d.iterdir():
        if item.is_dir() and not item.name.startswith('.'):
            # Count files and get size
            file_count = sum(1 for _ in item.rglob("*") if _.is_file())
            size = sum(f.stat().st_size for f in item.rglob("*") if f.is_file())
            projects.append(f"{item.name}: {file_count} files, {size / 1024 / 1024:.1f} MB")
    
    if not projects:
        return f"No projects found in {base_dir}"
    
    return "Available projects:\n" + "\n".join(sorted(projects))


@mcp.tool()
def configs_overview(base_dir: str = "/configs") -> str:
    """Show overview of available configuration files."""
    d = Path(base_dir)
    if not d.is_dir():
        return f"Configs directory not found: {base_dir}"
    
    configs = []
    for item in d.iterdir():
        if item.is_file() and not item.name.startswith('.'):
            size = item.stat().st_size
            configs.append(f"{item.name}: {size} bytes")
    
    if not configs:
        return f"No config files found in {base_dir}"
    
    return "Available config files:\n" + "\n".join(sorted(configs))


@mcp.tool()
def system_status() -> str:
    """Show overall system status: disk, memory, and services."""
    
    status = []
    
    # Disk usage
    disk = shutil.disk_usage("/")
    used_gb = disk.used / 1024 / 1024 / 1024
    total_gb = disk.total / 1024 / 1024 / 1024
    status.append(f"Disk: {used_gb:.1f} GB used / {total_gb:.1f} GB total")
    
    # Docker services
    try:
        result = _run(["docker", "compose", "ps"])
        status.append(f"Docker services:\n{result}")
    except BaseException as e:  # noqa: BLE001
        status.append(f"Docker status check failed: {e}")
    
    # GPU status
    status.append(f"GPU Status:\n{gpu_status()}")
    
    return "\n\n".join(status)


if __name__ == "__main__":
    mcp.run()