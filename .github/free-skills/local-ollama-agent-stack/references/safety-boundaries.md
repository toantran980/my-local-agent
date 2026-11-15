# Safety boundaries

Apply these safety principles when configuring or modifying a local agent stack. Check the user's project for its exact permissions and limits.

## Network exposure

- Ollama's API has no authentication by default. Keep Ollama and MCP bridge services on localhost unless the user explicitly requests a reviewed, authenticated network deployment.
- Use only endpoints and tool servers that the user has configured. Do not silently add remote APIs or transmit repository content off-device.

## Files and writes

- Preserve the project's path traversal checks, sensitive-path denials, and size limits. Never read or print `.env`, private keys, certificates, or credentials.
- Grant tools only the file access they need. Prefer read-only mounts for project, configuration, and log files; keep writable directories explicitly scoped.
- Keep RAG source files read-only unless the user explicitly requests otherwise. Store indexes, run memory, and caches in their configured local locations, and exclude private runtime data from distributable packages.
- Use read-only MCP tools for diagnosis whenever possible. Before any write, confirm the user explicitly requested it and verify the exact target and content; use a preview or dry run when available.
- If a write may have succeeded but its response is unclear, verify the result before retrying to avoid duplicate actions.

## Configuration and reporting

- Inspect documented example configuration for variable names; do not open `.env` to discover values. Ask the user to provide only non-secret settings needed for troubleshooting.
- Avoid printing environment dumps, tokens, credentials, or full sensitive config.
- Report errors and failed checks as failures. Do not silently claim a degraded fallback or unverified operation succeeded.
- Before changing a safety boundary, identify the exact impact and get explicit user approval.

The linked reference project has additional implementation-specific limits; do not assume they apply to another stack. Always verify the actual implementation before relying on a particular sandbox boundary.
