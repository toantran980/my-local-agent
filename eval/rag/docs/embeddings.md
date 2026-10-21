# Embeddings

## Model

Retrieval uses the nomic-embed-text model, served by Ollama through the /api/embed endpoint.
Vectors have 768 dimensions and are stored as JSON text in SQLite.

## Chunking

Markdown files are split at headings so each chunk keeps its section title.
Other files use 1200 character windows with 200 characters of overlap.
