# Agent memory

## Storage

After every run the agent appends a short summary to a dated Markdown file under workspace/memory.
Secrets are redacted before anything is written.

## Disabling

Set AGENT_MEMORY=0 to stop the agent from recording runs.
