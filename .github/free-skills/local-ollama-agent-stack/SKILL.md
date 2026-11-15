---
name: local-ollama-agent-stack
description: "Use when troubleshooting local Ollama + MCP stacks on Linux/WSL2: distinguish installed from loaded models and VRAM use, resolve mcpo/OpenAPI routes, and verify agent tool calls. Provides read-only diagnostic guidance for different project layouts."
---

# Local Ollama + MCP Stack Troubleshooter

For developers running local Ollama who need an agent to reach MCP tools without routing model prompts through a hosted inference API. The focus is the failure-prone handoff between four distinct layers—Ollama model availability, runtime/VRAM residency, the configured MCP bridge route, and an actual agent tool call—so a healthy endpoint is not mistaken for a working agent. It covers native Linux and Windows/WSL2 and adapts to different project layouts.

This Markdown-only skill guides an agent through read-only service checks without making a model-generation request. It uses the user's configured endpoints and does not include executable scripts.

## The diagnostic loop

1. **Map the runtime.** Identify native Linux or Windows/WSL2, where the agent runs, Ollama's reachable URL, the MCP bridge, and its configured OpenAPI route. Inspect project docs and Compose/config files; do not assume repository-specific filenames. Never open `.env` or credentials.
2. **Separate model states.** Use `/api/tags` or `ollama list` to check whether the requested model is installed. Use `/api/ps` or `ollama ps` while it is loaded to inspect runtime residency and VRAM. Installed does not mean loaded; a successful API response does not prove GPU use.
3. **Resolve the bridge route.** Read the configured bridge/server name and request that server's actual OpenAPI path. A 404 usually means the route or base URL is wrong. A valid schema proves only that tools are advertised.
4. **Test the final handoff.** Inspect the available tool's description and required arguments. If the agent connection is available, make one harmless, read-only call and verify its returned data. Do not test with a write, destructive action, or broad filesystem access.
5. **Report by layer.** Mark model availability, runtime residency, bridge schema, and agent tool call separately as pass, fail, or not checked. Give the next diagnostic step for the first failing layer; use [troubleshooting](./references/troubleshooting.md).

See [workflows](./references/workflows.md) for commands and [safety boundaries](./references/safety-boundaries.md) before changing configuration or permissions.

## Read-only service checks

In a Linux or WSL2 shell, check the configured Ollama API. These examples use its common local default; substitute the actual endpoint when it differs:

```bash
curl -fsS http://localhost:11434/api/tags
curl -fsS http://localhost:11434/api/ps
```

Check the configured mcpo OpenAPI URL separately; inspect its `paths` rather than guessing a server route. A reachable endpoint does not establish GPU use or an end-to-end agent tool call. Report those as separate checks.

## Tool-call rules

- Use only tools and endpoints already configured. Confirm the tool name, purpose, and required arguments; do not guess identifiers or claim a result without checking the response.
- Prefer read-only calls for diagnosis. Run a write only when explicitly requested and after confirming its exact target and content. Use a dry-run or preview if the integration provides one.
- If a write returns an ambiguous result, verify whether it took effect before considering any retry. Do not repeat a possibly applied write.

## Safety boundaries

- Keep Ollama and MCP services local. Ollama's API has no authentication by default; do not expose it to an untrusted network.
- Do not send project content to hosted services or add remote APIs without request.
- Prefer read-only mounts and narrowly scoped write access. Never print secrets or inspect credential files.
- Inspect the current setup before changing it; preserve its sandbox and approval rules.

See the detailed [safety guide](./references/safety-boundaries.md).

## Reference implementation

[my-local-agent](https://github.com/toantran980/my-local-agent) is an optional reference implementation. Its setup and naming are specific to that repository and are not prerequisites for using this skill.

## Troubleshooting guides

- [Workflows](./references/workflows.md): service checks, MCP integration, and optional RAG.
- [Troubleshooting](./references/troubleshooting.md): common connectivity, model, GPU, and RAG symptoms.
