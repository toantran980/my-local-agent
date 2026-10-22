"""Small code examples used to check code-aware RAG chunking."""

LARGE_PROMPT_THRESHOLD = 3


def calculate_vram_budget(model_weights_gb, kv_cache_gb, headroom_gb=1):
    """Calculate remaining GPU memory after model, cache, and safety headroom."""
    return 16 - model_weights_gb - kv_cache_gb - headroom_gb


def redact_bearer_token(log_line):
    """Mask a bearer credential before writing a line to an audit log."""
    return log_line.replace("Bearer secret-token", "Bearer [REDACTED]")


class ModelRouter:
    """Choose an inference model based on task complexity."""

    def choose_model(self, complexity):
        """Use a larger model for difficult prompts."""
        return "qwen3:14b" if complexity > LARGE_PROMPT_THRESHOLD else "qwen3.5:4b"
