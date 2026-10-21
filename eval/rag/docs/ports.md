# Port map

## Services

The tool bridge listens on port 8000 and the Open WebUI chat site on port 3000.
Every port is published on 127.0.0.1 only, never on all interfaces.

## Conflicts

If a Windows Ollama install already owns 11434, the containerised Ollama cannot start.
Point the services at host.docker.internal instead.
