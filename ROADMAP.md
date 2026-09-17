# Roadmap

## Product goal

Build a local-first autonomous triage platform that turns signals such as
telemetry, configuration drift, and failing checks into evidence-backed,
human-approved changes. The agent may propose and verify a change, but a human
approves every merge.

```text
signals/configs -> triage agent -> scoped tools -> audit trail
                                      |
                                      v
                             tests and verification
                                      |
                                      v
                         draft PR -> human approval -> metrics
```

## Guiding principles

- Local Ollama is the default inference route; cloud fallback is explicit.
- Start read-only and grant narrowly scoped write capabilities only after
  evaluation proves they are reliable.
- Every agent action must have structured, durable audit data.
- A passing verification suite and a draft PR are required before a proposed
  change can reach human review.
- Optimize inference infrastructure only after outcome metrics identify a
  bottleneck.

## Milestone 1 — Production agent harness

**Goal:** make one safe, repeatable agent execution path.

Build:

- A task schema: ID, source signal, repository/workspace, policy, model route,
  lifecycle state, and correlation ID.
- A tool registry with explicit capability classes: read, write, shell, git,
  network, and PR creation.
- Per-task permissions, path allowlists, command allowlists, output-size caps,
  and request timeouts.
- JSONL audit events for prompts, model decisions, tool calls, outputs,
  retries, verification, and approval decisions. Never log secrets.
- Bounded retries with exponential backoff and clear terminal states
  (`succeeded`, `needs_review`, `failed`, `blocked`).
- A draft-PR gate: create a patch only on a dedicated branch; run verification;
  open a draft PR; never merge automatically.

**Definition of done:** a known failing fixture can be inspected, patched in a
separate branch/worktree, verified, recorded in an audit log, and proposed as a
draft PR for human approval.

## Milestone 2 — Evaluation and reliability

**Goal:** prove when the harness is safe enough to expand.

Build on `eval/cases/` and `eval/history.jsonl`:

- Separate detection, diagnosis, patch generation, and verification cases.
- Record model, prompt/tool policy version, latency, retry count, and outcome
  for every run.
- Make failed eval cases return a non-zero process exit code.
- Track detection precision/recall, fix success rate, verification pass rate,
  false-positive rate, rollback rate, and human approval rate.
- Add regression thresholds before changing models, prompts, or permissions.

**Definition of done:** a reproducible report compares current and baseline
performance, and a regression blocks promotion of a changed policy or model.

## Milestone 3 — Sensor triage pipeline

**Goal:** apply the harness to a real operational workload.

Build:

- Versioned input adapters for telemetry snapshots and configuration exports.
- Drift and anomaly rules with configurable thresholds and suppression windows.
- Evidence bundles: source timestamps, affected entities, baseline comparison,
  confidence, and suggested next action.
- Read-only daily reports first; enable draft remediation PRs only for
  allowlisted, reversible configuration fixes.

**Definition of done:** a fixture or real sandbox signal produces an
evidence-backed anomaly report, and a safe config drift produces a verified
draft PR.

## Milestone 4 — Model router and fallback policy

**Goal:** route each task to the right model without weakening safety.

Build:

- A provider-neutral interface for Ollama, vLLM, Bedrock, and OpenRouter.
- Policy-based routing using task class, privacy level, context size, latency,
  cost budget, and provider health.
- Ollama as the default route; cloud providers opt-in per task or policy.
- Fallback only for retryable provider/model failures, with route changes
  captured in the audit record.
- Compatibility tests for structured output and tool calls across providers.

**Definition of done:** the same eval suite can run against each route, and
the selected route plus fallback reason are visible in every task record.

## Milestone 5 — vLLM deployment for RTX 5080

**Goal:** improve local throughput only if measurements justify it.

Build:

- A pinned vLLM image and documented RTX 5080/WSL2 compatibility settings.
- Health, readiness, GPU-residency, latency, and OOM monitoring.
- A benchmark comparing Ollama and vLLM on the harness evaluation workload.
- Router integration behind an explicit feature flag.

**Definition of done:** vLLM demonstrably improves a target metric (such as
concurrent throughput or latency) while preserving evaluation quality and
reliability.

## Architecture decisions to make early

1. Store task records and audit events locally (SQLite is sufficient at first)
   rather than relying only on Markdown reports.
2. Execute write-capable jobs in disposable worktrees or containers, never in
   the user’s active checkout.
3. Keep secrets outside prompts and tool output; pass them only through
   narrowly scoped runtime credentials when unavoidable.
4. Version prompts, tool schemas, permission policies, and evaluation cases.
5. Keep scheduled triage read-only until Milestones 1 and 2 meet their
   reliability thresholds.

## Immediate next slice

Implement the production harness around one controlled workflow:

> Given a known failing test or configuration drift, collect evidence, propose
> the smallest safe patch in an isolated worktree, run verification, write an
> audit trail, and open a draft PR for human approval.

This is the smallest end-to-end proof of the platform. It also gives the
evaluation, sensor pipeline, model router, and vLLM work a stable foundation.


## Next Steps (merged from NEXT-STEPS.md)

# Next Steps: Enable Project Access ✅ COMPLETED

## What We Just Did

✅ Created Windows filesystem directories (`C:\Users\toant\projects`, `configs`, `logs`)
✅ Updated docker-compose.yml with Windows filesystem mounts
✅ Added config volume mount to mcpo container
✅ Recreated mcpo container to pick up new configuration
✅ Verified projects_ops MCP server is working
✅ Tested file access via CLI

## Current Status: WORKING ✅

- ✅ Directories created on Windows filesystem
- ✅ Docker volumes mounted correctly
- ✅ MCP config file properly mounted
- ✅ projects_ops server connected and functional
- ✅ File access verified via CLI

## How to Test (CLI)

```bash
# Read the sample README.md file
curl -X POST http://localhost:8000/projects_ops/read_project_file \
  -H "Content-Type: application/json" \
  -d '{"project": "", "file_path": "README.md", "base_dir": "/projects"}'

# Create a sample project
mkdir /mnt/c/Users/toant/projects/sample-project
echo "# Sample Project" > /mnt/c/Users/toant/projects/sample-project/README.md
echo "print('hello')" > /mnt/c/Users/toant/projects/sample-project/main.py

# List projects
curl -X POST http://localhost:8000/projects_ops/list_projects \
  -H "Content-Type: application/json" \
  -d '{"base_dir": "/projects"}'

# Get project structure
curl -X POST http://localhost:8000/projects_ops/get_project_structure \
  -H "Content-Type: application/json" \
  -d '{"project": "sample-project", "base_dir": "/projects"}'
```

## Add to Open WebUI

1. Open http://localhost:3000
2. Go to **Admin Panel → Settings → Integrations → External Tool Servers**
3. Add new OpenAPI server:
   - Name: `projects_ops`
   - URL: `http://mcpo:8000/projects_ops`
4. Enable the tool in chat sessions (top-right tools icon)

## Available Tools

Your agent can now:
- **List projects**: `list_projects()` - See available project directories
- **Read project files**: `read_project_file()` - Read files from specific projects
- **Search projects**: `search_projects()` - Search across all project files
- **List project files**: `list_project_files()` - See files in a specific project
- **Get project structure**: `get_project_structure()` - Tree view of project layout

## Security Features Active

✅ Path traversal protection
✅ Sensitive file filtering (.env, keys, certs)
✅ File size limits (32KB)
✅ Directory exclusion (.git, node_modules, etc.)
✅ Read-only access (no write capabilities)

## Next Steps

1. **Populate your projects directory** with actual code
2. **Add projects_ops to Open WebUI** for agent usage
3. **Test with real projects** using the agent interface
4. **Consider enabling vLLM** for higher throughput (optional)
5. **Set up authentication** when ready for network access (optional)

## Important Notes

- **Windows Filesystem**: Using `/mnt/c/Users/toant/` paths for compatibility
- **API Structure**: Tools are at `/projects_ops/{tool_name}`, not `/projects_ops/tools/{tool_name}`
- **Container Recreate**: Required mcpo container recreation to pick up config changes
- **File Access**: Works with both individual files and project directories

## Troubleshooting

### If tools don't appear in Open WebUI
```bash
# Verify mcpo is running
docker ps | grep mcpo

# Check config is mounted
docker exec mcpo cat /config/config.json

# Restart if needed
docker compose restart mcpo
```

### If file access fails
```bash
# Check mount points
docker exec mcpo ls -la /projects

# Verify files exist on host
ls -la /mnt/c/Users/toant/projects/

# Check logs
docker logs mcpo --tail 20
```

## Setup Complete! ✅

Your homelab now has safe, controlled project access via the projects_ops MCP server. The agent can read and analyze your project directories with full security protections.
