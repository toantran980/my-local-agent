# Safety boundaries

Treat these as invariants when configuring or modifying a local agent stack.

## Network exposure

- Ollama's API has no authentication. In this repository, service ports bind to `127.0.0.1`; preserve that binding.
- Do not expose Ollama, mcpo, Open WebUI, or other local services to an untrusted network. A LAN-facing authenticated proxy is a separate, deliberate deployment change and must be configured and reviewed explicitly.
- Use only endpoints and tool servers that the user has configured. Do not silently add remote APIs or transmit repository content off-device.

## Files and writes

- `agent_cli.py` writes only under the selected `--repo`, only in Agent mode with `--apply`, and only after explicit confirmation.
- Preserve path traversal checks, sensitive path denials, and existing size limits. Never read or print `.env`, private keys, certificates, or credentials.
- Keep project/config/log mounts read-only. `projects_ops` is read-only; only the designated `workspace/` mount is writable to MCP tools.
- RAG reads source files and writes only its local index under `workspace/.rag`; do not change this into source-writing behavior.
- Keep run memory and caches local, redacted, and in their configured workspace locations. Do not move them into source mounts or include them in a distributable package.

## Configuration and reporting

- Inspect `.env.example` for variable names; do not open `.env` to discover values. Ask the user to provide only non-secret settings needed for troubleshooting.
- Avoid printing environment dumps, tokens, credentials, or full sensitive config.
- Report errors and failed checks as failures. Do not silently claim a degraded fallback or unverified operation succeeded.
- Before changing a safety boundary, identify the exact impact and get explicit user approval.

## Repository-specific limits

In the documented implementation, agent tools cap reads at 32 KB, writes at 1 MB, and tool steps at 10 per run. Sensitive names and runtime directories are blocked. Verify the current implementation rather than weakening these limits or assuming they apply unchanged to another project.
