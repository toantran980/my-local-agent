Timeouts

Chat requests to Ollama wait up to 300 seconds. Embedding requests wait 120 seconds and test runs 120 seconds. A request that exceeds its limit is reported to the model as an error instead of crashing the run.
