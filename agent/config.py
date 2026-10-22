"""Environment-driven settings and limits shared by the agent modules."""

from __future__ import annotations

import os
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

DEFAULT_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
DEFAULT_MODEL = os.environ.get("AGENT_MODEL", "qwen3:8b")
RAG_URL = os.environ.get("RAG_URL", "http://localhost:8000/rag_ops")

PLANNER_MODEL = os.environ.get("AGENT_PLANNER_MODEL", "qwen3:14b")
EXECUTOR_MODEL = os.environ.get("AGENT_EXECUTOR_MODEL", "qwen3.5:4b")
DEFAULT_EASY_MODEL = os.environ.get("AGENT_EASY_MODEL", "qwen3.5:4b")
DEFAULT_HARD_MODEL = os.environ.get("AGENT_HARD_MODEL", "qwen3:14b")

MAX_TOOL_STEPS = 10
MAX_FILE_BYTES = 32_000
MAX_SEARCH_RESULTS = 80
MAX_WRITE_SIZE = 1_000_000
MAX_WRITE_RETRIES = 2
MAX_REFLECTIONS = 1
MAX_CITATION_RETRIES = 1
HTTP_NOT_FOUND = 404

# Request timeouts in seconds.
TIMEOUT_CHAT = 300
TIMEOUT_PLAN = 180
TIMEOUT_SUMMARY = 120
TIMEOUT_EMBED = 30
TIMEOUT_TAGS = 10

MEMORY_ENABLED = os.environ.get("AGENT_MEMORY", "1") != "0"
MEMORY_RETENTION_DAYS = 30
MEMORY_MAX_ENTRIES = 100
MEMORY_ENTRY_CHARS = 800
# Lands under ./workspace, which is gitignored and visible to rag_ops via the /repo mount.
MEMORY_DIR = Path(os.environ.get("AGENT_MEMORY_DIR", REPO_ROOT / "workspace" / "memory"))

ANSWER_CACHE_ENABLED = os.environ.get("AGENT_SEMANTIC_CACHE", "0") == "1"
ANSWER_CACHE_TTL_SECONDS = 86_400
ANSWER_CACHE_THRESHOLD = 0.96
ANSWER_CACHE_MAX_ENTRIES = 100
ANSWER_CACHE_EMBED_MODEL = os.environ.get("AGENT_CACHE_EMBED_MODEL", "nomic-embed-text")

HISTORY_TOKEN_BUDGET = int(os.environ.get("AGENT_HISTORY_TOKEN_BUDGET", "5000"))
RECENT_HISTORY_MESSAGES = 4
CHARS_PER_TOKEN_ESTIMATE = 4

LONG_PROMPT_WORD_COUNT = 45
MIN_ROUTING_SIGNALS = 2
MIN_TECHNICAL_TERMS = 2

SOURCE_LINE = re.compile(r"\[\d+\.\d+\] (\S+) \(chunk \d+\)")
CITATION = re.compile(r"\[([\w.\\/-]+\.\w+)\]")

# Deliberately broken eval fixtures must not show up in the agent's own test runs.
PYTEST_IGNORES = ("--ignore=eval/fixtures",)
EXCLUDED_DIRS = {".agent", ".git", ".venv", "__pycache__", "node_modules"}
SENSITIVE_FILE_NAMES = {".env", ".npmrc", ".pypirc", "id_rsa", "id_ed25519"}
