"""MCP tools for read-only image question answering with a local Ollama vision model."""

import base64
import json
import os
import urllib.error
import urllib.request
from pathlib import Path

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("vision-ops")

SUPPORTED_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
DEFAULT_MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_QUESTION_CHARS = 2000
OLLAMA_TIMEOUT_SECONDS = 300


def _image_roots() -> list[Path]:
    configured = os.environ.get("VISION_IMAGE_DIRS", "/workspace")
    roots = [Path(value).expanduser().resolve() for value in configured.split(os.pathsep) if value]
    if not roots:
        raise ValueError("VISION_IMAGE_DIRS must contain at least one directory")
    return roots


def _resolve_image(image_path: str) -> Path:
    if not image_path.strip():
        raise ValueError("image_path must not be empty")

    roots = _image_roots()
    candidate = Path(image_path).expanduser()
    candidates = [candidate] if candidate.is_absolute() else [root / candidate for root in roots]
    for path in candidates:
        try:
            resolved = path.resolve(strict=True)
        except FileNotFoundError:
            continue
        if not any(resolved.is_relative_to(root) for root in roots):
            raise ValueError("image_path must be inside a configured VISION_IMAGE_DIRS directory")
        if not resolved.is_file():
            raise ValueError("image_path must refer to a file")
        if resolved.suffix.lower() not in SUPPORTED_IMAGE_SUFFIXES:
            raise ValueError("image must be a .jpg, .jpeg, .png, or .webp file")
        maximum = int(os.environ.get("VISION_MAX_IMAGE_BYTES", DEFAULT_MAX_IMAGE_BYTES))
        if maximum <= 0:
            raise ValueError("VISION_MAX_IMAGE_BYTES must be positive")
        if resolved.stat().st_size > maximum:
            raise ValueError(f"image exceeds the configured {maximum}-byte size limit")
        return resolved
    raise ValueError("image_path was not found inside a configured VISION_IMAGE_DIRS directory")


@mcp.tool()
def ask_about_image(image_path: str, question: str) -> str:  # noqa: PLR0911
    """Ask the configured local Ollama vision model a question about an allowed image file.

    Only reads images inside VISION_IMAGE_DIRS (default /workspace), and does
    not modify them. The image is sent to the configured Ollama endpoint.
    """
    try:
        image_path = _resolve_image(image_path)
        maximum = int(os.environ.get("VISION_MAX_IMAGE_BYTES", DEFAULT_MAX_IMAGE_BYTES))
        with image_path.open("rb") as image_file:
            image = image_file.read(maximum + 1)
        if len(image) > maximum:
            raise ValueError("image grew beyond the configured size limit while being read")
    except (OSError, ValueError) as exc:
        return f"Image unavailable: {exc}"

    if not question.strip():
        return "Question must not be empty."
    if len(question) > MAX_QUESTION_CHARS:
        return f"Question exceeds the {MAX_QUESTION_CHARS}-character limit."

    payload = {
        "model": os.environ.get("VISION_MODEL", "qwen2.5vl:7b"),
        "messages": [
            {
                "role": "user",
                "content": question,
                "images": [base64.b64encode(image).decode("ascii")],
            }
        ],
        "stream": False,
    }
    request = urllib.request.Request(
        f"{os.environ.get('OLLAMA_URL', 'http://ollama:11434')}/api/chat",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=OLLAMA_TIMEOUT_SECONDS) as response:
            result = json.load(response)
    except urllib.error.HTTPError as exc:
        detail = exc.read(1000).decode("utf-8", "replace")
        return f"Ollama vision request failed (HTTP {exc.code}): {detail or exc.reason}"
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        return f"Ollama vision request failed: {exc}"

    if not isinstance(result, dict) or not isinstance(result.get("message"), dict):
        return "Ollama returned an invalid vision response."
    content = result["message"].get("content")
    if not isinstance(content, str) or not content.strip():
        return "Ollama returned no vision response."
    return content.strip()


if __name__ == "__main__":
    mcp.run()
