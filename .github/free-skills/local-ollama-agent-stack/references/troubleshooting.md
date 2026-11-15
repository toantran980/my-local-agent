# Troubleshooting

Start with observable evidence: check endpoint reachability from the same environment that runs the client, then inspect relevant service status and logs.

| Symptom | Checks and next step |
| --- | --- |
| `docker: command not found` | On Windows, run Docker commands in WSL2 with Docker Desktop integration enabled. On native Linux, confirm Docker Engine and the Compose plugin are installed and running. |
| Ollama connection refused | Check `http://localhost:11434/api/tags` from the same environment as the client. Confirm Ollama's actual address and that `OLLAMA_URL` points to it. Do not expose the unauthenticated API publicly as a workaround. |
| Compose reports a port conflict | Inspect the configured host/container port mappings and determine which process owns the conflicting port. Avoid running two Ollama instances on the same host port. |
| Model is missing or not using the GPU | Confirm the model is installed and loaded with `ollama list` and `ollama ps`. Check GPU availability in the host and container runtime, allow an initial model download to finish, then recheck. |
| MCP bridge does not expose a tool | Inspect the bridge's actual configuration and logs, then open its configured health or OpenAPI endpoint. Confirm the MCP server starts and that the route matches the configured server name. |
| mcpo OpenAPI check returns 404 or no paths | Confirm the configured base URL and server-specific OpenAPI path, then check that URL. An OpenAPI response alone does not prove that a tool invocation succeeds. |
| Agent cannot access project files | Confirm the intended path is mounted and readable from the agent's environment. Check path translation across Windows, WSL2, containers, and native Linux; prefer read-only mounts when write access is unnecessary. |
| Model request fails or returns empty output | Confirm Ollama is reachable and the requested model appears in `/api/tags`. Check the model's context and memory requirements, then inspect service logs. |
| Local RAG returns no useful results | Confirm the embedding model is available, intended source paths are indexed, exclusions are appropriate, and indexing completed. Run the project's retrieval evaluation, if available. |

Use the user's own project documentation and configuration. Do not guess at fixes when logs or config can establish the cause.
