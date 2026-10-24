# my-local-agent

A local-first AI agent stack built around Ollama, an MCP tool bridge, and a
terminal agent. It is designed for Windows with WSL2 and Docker Desktop, and
uses a local NVIDIA GPU for inference.

**Getting started:** [QUICKSTART.md](QUICKSTART.md) covers setup, common
commands, evaluation, nightly triage, and troubleshooting.

## Architecture

```text
Windows host
└── WSL2
    └── Docker Desktop
        ├── Ollama       :11434  local inference (host service by default)
        ├── Open WebUI   :3000   optional chat interface
        ├── mcpo         :8000   MCP-to-OpenAPI bridge
        ├── auth_proxy   :8443   optional authenticated access
        └── local_vllm   :8001   optional high-throughput serving
```

All service ports bind to `127.0.0.1`. Ollama is unauthenticated, so do not
expose its API to an untrusted network. Optional services are enabled through
Docker Compose profiles.

## Components

| Component | Purpose |
| --- | --- |
| [`agent_cli.py`](agent_cli.py) and [`agent/`](agent) | Stdlib-only terminal agent with Ask, Plan, and Agent modes |
| [`mcp/local_ops.py`](mcp/local_ops.py) | Read-only git, GPU, system, and report tools |
| [`mcp/projects_ops.py`](mcp/projects_ops.py) | Optional read-only access to selected project, config, and log directories |
| [`mcp/rag_ops.py`](mcp/rag_ops.py) | Local indexing and semantic search |
| [`scripts/nightly-triage.py`](scripts/nightly-triage.py) | Scheduled local health and repository report |
| [`eval/`](eval) | Agent and retrieval evaluation cases |

mcpo loads the MCP servers listed in [`mcpo/config.json`](mcpo/config.json).
Open WebUI can connect to each server at `http://mcpo:8000/<server-name>`.

## Agent modes

```bash
python3 agent_cli.py ask "What does this repository do?"
python3 agent_cli.py plan "Add health checks"
python3 agent_cli.py agent "Fix the syntax error"             # dry run
python3 agent_cli.py agent --apply "Fix the syntax error"     # stage writes for confirmation
python3 agent_cli.py agent --plan-first --split-models "Implement a feature"
```

Ask and Plan are read-only. Agent mode stages proposed changes and only applies
them after `--apply` and explicit confirmation. Optional routing, streaming,
history summarization, verified memory, and the semantic answer cache are
described in [QUICKSTART.md](QUICKSTART.md) and configured through environment
variables documented in [docs/CONFIGURATION.md](docs/CONFIGURATION.md).

## Safety and data

- Agent writes stay under `--repo`; writes require `--apply` and confirmation.
- Tool reads are capped at 32 KB; writes are capped at 1 MB.
- Credential files and runtime directories are blocked from tool access.
- Audit records are local JSONL files under `.agent/audit/`; credentials are
  redacted before they are recorded.
- RAG sources are read-only. Its SQLite index is stored under
  `workspace/.rag/`; see [docs/RAG.md](docs/RAG.md).
- Only `workspace/` is the writable MCP mount. Project/config/log mounts, when
  enabled, are read-only.

## Documentation

| Guide | Use it for |
| --- | --- |
| [QUICKSTART.md](QUICKSTART.md) | Setup, everyday commands, smoke test, evaluation, and troubleshooting |
| [docs/CONFIGURATION.md](docs/CONFIGURATION.md) | Environment variables and model/VRAM guidance |
| [docs/RAG.md](docs/RAG.md) | Indexing, retrieval behavior, and RAG settings |
| [PROJECTS.md](PROJECTS.md) | Enabling read-only access to external project directories |
| [AGENTS.md](AGENTS.md) | Repository layout, development commands, and contributor constraints |
| [workspace/README.md](workspace/README.md) | Agent workspace and sandbox |

## Development checks

```bash
python3 -m pytest -q tests
ruff check .
shellcheck scripts/*.sh
```

See [QUICKSTART.md](QUICKSTART.md) for stack operations and evaluation commands.

## License

[MIT](LICENSE). Third-party container images and tools retain their respective
licenses.
