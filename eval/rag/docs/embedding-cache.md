Embedding cache

Chunks are only re-embedded when the file hash changes, so repeated indexing is fast. The index lives in workspace/.rag and can be deleted to force a full rebuild. This is unrelated to the Ollama model cache.
