"""Single HTTP transport for Ollama: OpenAI-style chat, native JSON, and streaming."""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from typing import Any

from agent.config import HTTP_NOT_FOUND, TIMEOUT_CHAT


def _open_chat(request: urllib.request.Request, model: str):
    """urlopen with Ollama HTTP errors turned into messages a user can act on."""
    try:
        return urllib.request.urlopen(request, timeout=TIMEOUT_CHAT)  # noqa: S310
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:300]
        if exc.code == HTTP_NOT_FOUND:
            raise RuntimeError(
                f"model '{model}' not found in Ollama. Check the name with `ollama list` "
                f"(e.g. qwen3:8b) or fetch it with `ollama pull {model}`."
            ) from exc
        raise RuntimeError(f"Ollama returned HTTP {exc.code}: {detail}") from exc


def _with_sampling(payload: dict[str, Any]) -> dict[str, Any]:
    """Ollama's /v1 endpoint ignores "options"; sampling fields must be top-level."""
    return {"temperature": 0, "seed": 0, "max_tokens": 2048, **payload}


def _request(url: str, path: str, payload: dict[str, Any]) -> urllib.request.Request:
    return urllib.request.Request(
        url.rstrip("/") + path,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )


def native_json(url: str, path: str, payload: dict[str, Any], timeout: int) -> dict[str, Any]:
    """POST to a native Ollama endpoint such as /api/chat or /api/embed."""
    with urllib.request.urlopen(_request(url, path, payload), timeout=timeout) as response:  # noqa: S310
        return json.load(response)


def structured_chat(url: str, payload: dict[str, Any], timeout: int) -> dict[str, Any]:
    """Run /api/chat with a JSON-schema ``format`` and return the parsed message content."""
    body = {
        "stream": False,
        "think": False,
        "options": {"temperature": 0, "seed": 0},
        **payload,
    }
    return json.loads(native_json(url, "/api/chat", body, timeout)["message"]["content"])


def post(url: str, payload: dict[str, Any]) -> dict[str, Any]:
    payload = _with_sampling(payload)
    request = _request(url, "/v1/chat/completions", payload)
    with _open_chat(request, str(payload.get("model", ""))) as response:
        return json.load(response)


def post_stream(url: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Like post(), but prints answer tokens as they arrive; returns the same shape."""
    payload = _with_sampling({**payload, "stream": True})
    request = _request(url, "/v1/chat/completions", payload)
    content: list[str] = []
    calls: dict[int, dict[str, Any]] = {}
    thinking_notice = False
    with _open_chat(request, str(payload.get("model", ""))) as response:
        for raw in response:
            line = raw.decode("utf-8").strip()
            if not line.startswith("data:"):
                continue
            data = line.removeprefix("data:").strip()
            if data == "[DONE]":
                break
            delta = json.loads(data)["choices"][0].get("delta", {})
            if delta.get("reasoning") and not thinking_notice:
                print("(thinking...)", file=sys.stderr, flush=True)
                thinking_notice = True
            if delta.get("content"):
                print(delta["content"], end="", flush=True)
                content.append(delta["content"])
            for call in delta.get("tool_calls") or []:
                _merge_tool_call(calls, call)
    if content:
        print()
    message: dict[str, Any] = {"role": "assistant", "content": "".join(content)}
    if calls:
        message["tool_calls"] = [calls[index] for index in sorted(calls)]
    return {"choices": [{"message": message}]}


def _merge_tool_call(calls: dict[int, dict[str, Any]], call: dict[str, Any]) -> None:
    """Accumulate one streamed tool-call fragment into its slot."""
    slot = calls.setdefault(
        call.get("index", 0),
        {"id": "", "type": "function", "function": {"name": "", "arguments": ""}},
    )
    slot["id"] = call.get("id") or slot["id"]
    function = call.get("function", {})
    slot["function"]["name"] += function.get("name") or ""
    arguments = function.get("arguments") or ""
    if isinstance(arguments, dict):
        arguments = json.dumps(arguments)
    slot["function"]["arguments"] += arguments
