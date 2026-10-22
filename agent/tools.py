"""Sandboxed repository tools, their schemas, and argument validation."""

from __future__ import annotations

import contextlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any

from agent.config import (
    CITATION,
    EXCLUDED_DIRS,
    MAX_FILE_BYTES,
    MAX_SEARCH_RESULTS,
    MAX_WRITE_SIZE,
    PYTEST_IGNORES,
    RAG_URL,
    SENSITIVE_FILE_NAMES,
    SOURCE_LINE,
)


def resolve_repo_path(repo: Path, candidate: str) -> Path:
    """Resolve a user/model path and ensure it remains in the selected repo."""
    path = (repo / candidate).resolve()
    if path != repo and repo not in path.parents:
        raise ValueError("path escapes the selected repository")
    return path


def is_sensitive_path(repo: Path, path: Path) -> bool:
    """Prevent model tools from reading or changing credentials and runtime state."""
    relative = path.relative_to(repo)
    if any(part in EXCLUDED_DIRS for part in relative.parts):
        return True
    name = path.name.lower()
    if name in SENSITIVE_FILE_NAMES or (name.startswith(".env") and name != ".env.example"):
        return True
    return name.endswith((".pem", ".key", ".p12", ".pfx"))


class LocalTools:
    def __init__(self, repo: Path, apply: bool, seed_writes: dict[Path, str] | None = None) -> None:
        self.repo = repo
        self.apply = apply
        self.pending_writes: dict[Path, str] = dict(seed_writes or {})
        self.test_results: list[str] = []
        self.tests_dirty = bool(self.pending_writes)
        self.indexed = False
        self.sources: set[str] = set()

    def unsupported_citations(self, answer: str) -> list[str]:
        """Cited files that no tool result in this run actually showed the model."""
        seen = {Path(s.replace("\\", "/")).name for s in self.sources}
        cited = dict.fromkeys(CITATION.findall(answer))
        return [c for c in cited if Path(c.replace("\\", "/")).name not in seen]

    def last_test_passed(self) -> bool | None:
        """True/False from the most recent test run, None if tests never ran."""
        if not self.test_results:
            return None
        match = re.search(r"exit=(-?\d+)", self.test_results[-1])
        return match is not None and match.group(1) == "0"

    def verified_outcome(self) -> bool | None:
        """Last test result, ignoring failures the agent's own changes didn't cause."""
        passed = self.last_test_passed()
        return None if passed is False and not self.caused_by_staged_changes() else passed

    def caused_by_staged_changes(self) -> bool:
        """True when the last failing test output mentions a file the agent staged.

        Failures in untouched files (e.g. an intentionally broken fixture) are not
        the agent's to fix.
        """
        if not self.test_results:
            return False
        output = self.test_results[-1].replace("\\", "/")
        return any(path.relative_to(self.repo).as_posix() in output for path in self.pending_writes)

    def call(self, name: str, args: dict[str, Any]) -> str:
        handlers: dict[str, Callable[[dict[str, Any]], str]] = {
            "git_status": lambda _: self._run(["git", "status", "--short", "--branch"]),
            "read_file": self._read_file,
            "search": lambda a: self._search(str(a["pattern"]), str(a.get("glob", ""))),
            "semantic_search": lambda a: self._semantic_search(str(a["query"]), int(a.get("k", 5))),
            "write_file": lambda a: self._write_file(str(a["path"]), str(a["content"])),
            "run_tests": lambda _: self._run_tests(),
        }
        handler = handlers.get(name)
        if handler is None:
            return f"ERROR: unavailable tool {name}"
        try:
            return handler(args)
        except (KeyError, TypeError, ValueError) as exc:
            return f"ERROR: invalid tool arguments: {exc}"
        except Exception as exc:  # Tool failures should return to the model.
            return f"ERROR: {type(exc).__name__}: {exc}"

    def _read_file(self, args: dict[str, Any]) -> str:
        path = resolve_repo_path(self.repo, str(args["path"]))
        if is_sensitive_path(self.repo, path):
            return "ERROR: access to sensitive or runtime files is denied"
        if not path.is_file():
            return f"ERROR: not a file: {args['path']}"
        data = path.read_text(encoding="utf-8", errors="replace")
        self.sources.add(str(args["path"]))
        return data[:MAX_FILE_BYTES]

    def _run_tests(self) -> str:
        if self.pending_writes:
            result = self._run_staged_tests()
        else:
            result = self._run(
                [*self._python_command(), "-m", "pytest", "-q", *PYTEST_IGNORES], timeout=120
            )
        self.test_results.append(result)
        self.tests_dirty = False
        return result

    def _run(self, command: list[str], timeout: int = 30) -> str:
        result = subprocess.run(
            command, cwd=self.repo, capture_output=True, text=True, timeout=timeout, check=False
        )
        output = (result.stdout + result.stderr).strip() or "(no output)"
        return f"exit={result.returncode}\n{output[:MAX_FILE_BYTES]}"

    def _run_staged_tests(self) -> str:
        """Verify proposed edits in an isolated copy, never the active checkout."""
        with tempfile.TemporaryDirectory(prefix="local-agent-verify-") as temp:
            candidate = Path(temp) / "repo"
            shutil.copytree(
                self.repo,
                candidate,
                ignore=shutil.ignore_patterns(
                    *EXCLUDED_DIRS, ".env", ".env.*", "*.pem", "*.key", "*.p12", "*.pfx"
                ),
            )
            for source_path, content in self.pending_writes.items():
                target = candidate / source_path.relative_to(self.repo)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding="utf-8")
            result = subprocess.run(
                [*self._python_command(), "-m", "pytest", "-q", *PYTEST_IGNORES],
                cwd=candidate,
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )
            output = (result.stdout + result.stderr).strip() or "(no output)"
            return f"verification=staged-copy\nexit={result.returncode}\n{output[:MAX_FILE_BYTES]}"

    def _python_command(self) -> list[str]:
        """Prefer the selected repository's Linux virtual environment for checks."""
        for name in (".agent-venv", ".venv"):
            candidate = self.repo / name / "bin" / "python"
            if candidate.is_file():
                return [str(candidate)]
        return [sys.executable]

    def _search(self, pattern: str, glob: str) -> str:
        # Use Python regex rather than a model-controlled shell command.
        regex = re.compile(pattern, re.IGNORECASE)
        suffix = glob.removeprefix("*") if glob.startswith("*") else ""
        matches: list[str] = []
        for path in self.repo.rglob("*"):
            if not path.is_file() or is_sensitive_path(self.repo, path):
                continue
            if suffix and not path.name.endswith(suffix):
                continue
            try:
                for number, line in enumerate(
                    path.read_text(encoding="utf-8", errors="replace").splitlines(), 1
                ):
                    if regex.search(line):
                        matches.append(f"{path.relative_to(self.repo)}:{number}: {line}")
                        if len(matches) >= MAX_SEARCH_RESULTS:
                            return "\n".join(matches)
            except OSError:
                continue
        return "\n".join(matches) or "(no matches)"

    @staticmethod
    def _rag_post(tool: str, payload: dict[str, Any], timeout: int) -> str:
        request = urllib.request.Request(
            f"{RAG_URL.rstrip('/')}/{tool}",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            return str(json.load(response))

    def _semantic_search(self, query: str, k: int) -> str:
        """Query the rag_ops MCP server (via mcpo), refreshing its index once per run."""
        try:
            if not self.indexed:
                self.indexed = True
                with contextlib.suppress(OSError):
                    self._rag_post("index_sources", {}, 300)
            payload = {"query": query, "k": max(1, min(k, 10))}
            result = self._rag_post("semantic_search", payload, 60)
        except OSError as exc:
            return f"ERROR: RAG service unavailable ({exc}); use search/read_file instead"
        self.sources.update(SOURCE_LINE.findall(result))
        return result[:MAX_FILE_BYTES]

    def _write_file(self, relative: str, content: str) -> str:
        path = resolve_repo_path(self.repo, relative)
        if is_sensitive_path(self.repo, path):
            return "ERROR: writes to sensitive or runtime files are denied"
        if len(content.encode("utf-8")) > MAX_WRITE_SIZE:
            return "ERROR: proposed file content exceeds the 1 MB safety limit"
        self.pending_writes[path] = content
        self.tests_dirty = True
        if not self.apply:
            return (
                f"STAGED DRY-RUN: {relative} ({len(content)} chars). "
                "It will not be written without --apply and confirmation."
            )
        return (
            f"STAGED: {relative} ({len(content)} chars). "
            "The user must still confirm the diff before it is written."
        )


def _tool(
    name: str,
    description: str,
    properties: dict[str, str] | None = None,
    required: tuple[str, ...] = (),
) -> dict[str, Any]:
    parameters: dict[str, Any] = {
        "type": "object",
        "properties": {key: {"type": kind} for key, kind in (properties or {}).items()},
    }
    if required:
        parameters["required"] = list(required)
    return {
        "type": "function",
        "function": {"name": name, "description": description, "parameters": parameters},
    }


READ_ONLY_TOOLS = [
    _tool("git_status", "Read the current git branch and working tree state."),
    _tool("read_file", "Read a UTF-8 repository-relative file.", {"path": "string"}, ("path",)),
    _tool(
        "search",
        "Search repository text with a regular expression. "
        "Optional glob supports forms such as *.py.",
        {"pattern": "string", "glob": "string"},
        ("pattern",),
    ),
    _tool(
        "semantic_search",
        "Meaning-based search over indexed project docs and code. Use for "
        "conceptual questions where you do not know the exact keywords.",
        {"query": "string", "k": "integer"},
        ("query",),
    ),
]

WRITE_TOOLS = [
    _tool(
        "write_file",
        "Write a complete repository-relative file. "
        "In dry-run mode this only records the proposed write.",
        {"path": "string", "content": "string"},
        ("path", "content"),
    ),
    _tool("run_tests", "Run the fixed command python -m pytest -q in the repository."),
]


def tool_definitions(mode: str) -> list[dict[str, Any]]:
    return [*READ_ONLY_TOOLS, *(WRITE_TOOLS if mode == "agent" else [])]


JSON_TYPES: dict[str, type | tuple[type, ...]] = {
    "string": str,
    "integer": int,
    "number": (int, float),
    "boolean": bool,
}


def validate_arguments(name: str, arguments: Any, mode: str) -> str | None:
    """Check a tool call against its declared schema; return a model-facing error or None."""
    schemas = {t["function"]["name"]: t["function"]["parameters"] for t in tool_definitions(mode)}
    schema = schemas.get(name)
    if schema is None:
        return f"ERROR: unknown tool '{name}'. Available tools: {', '.join(sorted(schemas))}"
    if not isinstance(arguments, dict):
        return f"ERROR: arguments for {name} must be a JSON object; retry with valid JSON"
    missing = [key for key in schema.get("required", []) if key not in arguments]
    if missing:
        return f"ERROR: {name} is missing required argument(s): {', '.join(missing)}"
    for key, value in arguments.items():
        expected = schema["properties"].get(key, {}).get("type")
        wanted = JSON_TYPES.get(expected or "")
        bad_bool = isinstance(value, bool) and expected in ("integer", "number")
        if wanted and (bad_bool or not isinstance(value, wanted)):
            return f"ERROR: argument '{key}' of {name} must be {expected}"
    return None


def is_write_refusal(result: str) -> bool:
    """True only for write_file refusals that a retry cannot fix (path/sensitive)."""
    return result.startswith("ERROR: ") and any(
        marker in result
        for marker in (
            "path escapes the selected repository",
            "writes to sensitive or runtime files are denied",
            "invalid tool arguments: path escapes",
        )
    )
