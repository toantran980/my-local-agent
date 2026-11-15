# Workflows

Use the commands that match the user's operating system and project. The stack may run natively on Linux or on Windows through WSL2 and Docker Desktop. Verify installed tools and configured endpoints rather than assuming a specific repository layout.

## Verify Ollama

Check Ollama's installed models, currently loaded models, and local API:

```bash
ollama list
ollama ps
curl http://localhost:11434/api/tags
```

If the API is unreachable, confirm Ollama's actual bind address and the endpoint configured for the client. Check the reachable URL from the client's environment. Do not expose the unauthenticated API to an untrusted network.

If a model is installed but inference is slow or GPU use is unexpected, inspect `ollama ps` while a model is loaded and compare its reported processor/VRAM residency with the machine's available resources. Distinguish an installed model (`/api/tags`) from a loaded model (`/api/ps`). Do not infer GPU use merely from successful API responses.

## Start and verify the MCP bridge

Inspect the user's Compose file or service configuration, then follow that project's documented startup command. Verify the configured MCP server using its health endpoint or OpenAPI URL. mcpo commonly exposes an OpenAPI document under a server-specific path; use the actual path from the user's configuration rather than assuming a particular server name.

Check the configured OpenAPI URL with a read-only request. The following is an example path, not a default to assume:

```bash
curl -fsS http://localhost:8000/your-server/openapi.json
```

Replace the example URL with the configured local bridge URL and server route. Inspect the returned `paths`; a successful OpenAPI request does not prove that every tool works.

To verify a tool through the agent:

1. Inspect the tool's description and required arguments; use a known, harmless value rather than guessing identifiers.
2. Prefer a read-only operation and check that its response contains the expected result.
3. If only a write operation can verify the integration, do not use it as a connectivity probe. Run it only when explicitly requested, confirm its exact target and content, and use a preview if available.
4. If a write's outcome is unclear, check whether it succeeded before retrying.

## Run project-specific checks

When a project uses Docker Compose, inspect the compose file and run the project's documented commands from the correct environment. On Windows, use WSL2 with Docker Desktop integration if Docker commands are unavailable in PowerShell. On native Linux, use the installed Docker Engine and Compose plugin.

Run relevant tests or smoke checks after the basic service checks pass. Use the user's own project scripts; this skill does not assume that any particular script or test framework exists.

## Optional local RAG

If the user's stack includes local RAG, confirm its embedding model, indexed source locations, exclusions, and index storage path from the project configuration. Keep source files read-only unless the user explicitly requests otherwise. Re-run the project's retrieval evaluation after changes, if available.
