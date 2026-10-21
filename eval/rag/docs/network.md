Port reference

The auth proxy listens on 8443 and forwards to Open WebUI. Ollama is on 11434
and mcpo on 8000. All of them bind to 127.0.0.1 only. The Ollama API itself has
no authentication, so it must never be exposed on another interface.
