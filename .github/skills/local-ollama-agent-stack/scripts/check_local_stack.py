"""Check local Ollama and mcpo health without sending prompts or changing state."""

from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request
from typing import Any


def get_json(url: str, timeout: float) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.load(response)
    if not isinstance(payload, dict):
        raise ValueError(f"{url} returned JSON that is not an object")
    return payload


def report_model_residency(base_url: str, timeout: float) -> None:
    try:
        running = get_json(f"{base_url}/api/ps", timeout).get("models", [])
        if not isinstance(running, list):
            raise ValueError("/api/ps returned an invalid models list")
    except (OSError, ValueError, urllib.error.URLError, json.JSONDecodeError) as exc:
        print(f"  WARN: could not read model residency from /api/ps: {exc}")
        return

    if not running:
        print("  INFO: no model is currently loaded")
        return
    print("  Loaded models:")
    for item in running:
        if not isinstance(item, dict):
            continue
        name = item.get("name") or item.get("model") or "(unknown)"
        vram = item.get("size_vram", 0)
        if isinstance(vram, int | float) and not isinstance(vram, bool):
            print(f"    - {name}: {vram / 1_000_000_000:.2f} GB VRAM")
        else:
            print(f"    - {name}: VRAM usage unavailable")


def check_ollama(base_url: str, timeout: float, expected_model: str | None) -> bool:
    print(f"Ollama: {base_url}")
    try:
        tags = get_json(f"{base_url}/api/tags", timeout)
    except (OSError, ValueError, urllib.error.URLError, json.JSONDecodeError) as exc:
        print(f"  FAIL: could not read /api/tags: {exc}")
        return False

    models = tags.get("models", [])
    if not isinstance(models, list):
        print("  FAIL: /api/tags returned an invalid models list")
        return False
    names = [item.get("name", "") for item in models if isinstance(item, dict)]
    names = [name for name in names if isinstance(name, str) and name]
    print(f"  OK: /api/tags reachable; {len(names)} model(s) installed")
    for name in names:
        print(f"    - {name}")

    model_ok = True
    if expected_model:
        model_ok = expected_model in names
        if model_ok:
            print(f"  OK: requested model {expected_model!r} is installed")
        else:
            print(f"  FAIL: requested model {expected_model!r} is not installed")

    report_model_residency(base_url, timeout)
    return model_ok


def check_mcpo(base_url: str, timeout: float) -> bool:
    url = f"{base_url}/local_ops/openapi.json"
    print(f"mcpo: {base_url}")
    try:
        specification = get_json(url, timeout)
    except (OSError, ValueError, urllib.error.URLError, json.JSONDecodeError) as exc:
        print(f"  FAIL: could not read local_ops OpenAPI document: {exc}")
        return False

    paths = specification.get("paths")
    if not isinstance(paths, dict) or not paths:
        print("  FAIL: OpenAPI document has no tool paths")
        return False
    print(f"  OK: local_ops is reachable; {len(paths)} endpoint(s) advertised")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--ollama-url",
        default=os.environ.get("OLLAMA_URL", "http://localhost:11434"),
        help="Ollama base URL (default: OLLAMA_URL or http://localhost:11434)",
    )
    parser.add_argument(
        "--mcpo-url",
        default=os.environ.get("MCPO_URL", "http://localhost:8000"),
        help="mcpo base URL (default: MCPO_URL or http://localhost:8000)",
    )
    parser.add_argument(
        "--model",
        help="also fail if this model is not installed in Ollama",
    )
    parser.add_argument("--timeout", type=float, default=5.0, help="request timeout in seconds")
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error("--timeout must be greater than zero")

    ollama_url = args.ollama_url.rstrip("/")
    mcpo_url = args.mcpo_url.rstrip("/")
    ollama_ok = check_ollama(ollama_url, args.timeout, args.model)
    mcpo_ok = check_mcpo(mcpo_url, args.timeout)
    if ollama_ok and mcpo_ok:
        print("STACK CHECK: PASS")
        return 0
    print("STACK CHECK: FAIL")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
