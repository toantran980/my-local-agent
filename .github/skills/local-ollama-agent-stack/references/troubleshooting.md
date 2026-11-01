# Troubleshooting

Start with observable evidence: run the smoke test, inspect relevant container status/logs, and check endpoint reachability from the same environment that runs the client.

| Symptom | Checks and next step |
| --- | --- |
| `docker: command not found` in Windows shell | Run Docker commands in WSL2 with Docker Desktop running. |
| Ollama connection refused on `:11434` | Check `http://localhost:11434/api/tags` from WSL2. Confirm which Ollama instance owns the port and that `OLLAMA_URL` points to a reachable endpoint. Do not solve this by exposing the unauthenticated API publicly. |
| Compose reports a port conflict | The documented default uses host Ollama; the optional Ollama container also needs port `11434`. Stop one instance or choose a deliberate alternative configuration. |
| Model absent or no GPU row in smoke test | Confirm the model is installed and loaded; inspect Ollama's model list/status and GPU telemetry. Allow the initial model pull to finish, then rerun the smoke test. |
| mcpo does not expose a tool | Check `mcpo/config.json`, service logs, and `http://localhost:8000/openapi.json`; restart mcpo after an intentional config change. |
| Project files are not visible | Confirm the host directory exists, the Compose volume path matches its location (WSL Linux filesystem vs Windows-mounted path), and mcpo was recreated after enabling the read-only mounts. Follow `PROJECTS.md`. |
| Empty evaluation responses | Confirm Ollama is reachable from the eval process and the requested model appears in `/api/tags`; rerun only after both checks pass. |
| Web UI at `:3000` is unavailable | Confirm the optional profile/service is enabled and healthy. A first startup may take about a minute; inspect logs before changing configuration. |
| Nightly report is missing | Run `python3 scripts/nightly-triage.py` manually to surface the failure. In WSL2, confirm cron is running and the installed schedule matches the configured time. |
| RAG returns no useful results | Confirm `nomic-embed-text` is available, source mounts are present, index refresh succeeded, and the query is covered by the indexed files. Run `python3 scripts/eval-rag.py` after changes. |

Use the full project guidance in `QUICKSTART.md`, `docs/CONFIGURATION.md`, `docs/RAG.md`, and `PROJECTS.md`. Do not guess at fixes when logs or config can establish the cause.
