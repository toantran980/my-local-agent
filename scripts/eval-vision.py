#!/usr/bin/env python3
"""Evaluate the local vision model on synthetic OCR, chart, and object images.

  OLLAMA_URL   (default http://localhost:11434)
  VISION_MODEL (default qwen2.5vl:7b)
"""

import argparse
import base64
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EVAL_DIR = ROOT / "eval" / "vision"
SUPPORTED_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
MAX_IMAGE_BYTES = 10 * 1024 * 1024


def matches_expected_groups(answer: str, expected_groups: list[list[str]]) -> bool:
    normalized = re.sub(r"\s+", " ", answer.casefold())
    return all(
        any(
            re.search(rf"(?<!\w){re.escape(phrase.casefold())}(?!\w)", normalized)
            for phrase in group
        )
        for group in expected_groups
    )


def ask_ollama(image_path: Path, question: str, model: str, ollama_url: str, timeout: int) -> str:
    image_bytes = image_path.read_bytes()
    if not image_bytes or len(image_bytes) > MAX_IMAGE_BYTES:
        raise ValueError(f"{image_path.name} must be between 1 byte and 10 MiB")
    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": question,
                "images": [base64.b64encode(image_bytes).decode("ascii")],
            }
        ],
        "stream": False,
        "options": {"temperature": 0, "num_predict": 256},
    }
    request = urllib.request.Request(
        f"{ollama_url.rstrip('/')}/api/chat",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            result = json.load(response)
    except urllib.error.HTTPError as exc:
        detail = exc.read(1000).decode("utf-8", "replace")
        raise RuntimeError(f"Ollama returned HTTP {exc.code}: {detail or exc.reason}") from exc
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Ollama request failed: {exc}") from exc

    message = result.get("message") if isinstance(result, dict) else None
    answer = message.get("content") if isinstance(message, dict) else None
    if not isinstance(answer, str) or not answer.strip():
        raise RuntimeError("Ollama returned no vision response")
    return answer.strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default=os.environ.get("VISION_MODEL", "qwen2.5vl:7b"))
    parser.add_argument(
        "--ollama-url", default=os.environ.get("OLLAMA_URL", "http://localhost:11434")
    )
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--threshold", type=float, default=1.0)
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error("--timeout must be positive")
    if not 0 <= args.threshold <= 1:
        parser.error("--threshold must be between 0 and 1")

    cases = json.loads((EVAL_DIR / "cases.json").read_text(encoding="utf-8"))
    passed = 0
    failures = 0
    print(f"Vision eval: model={args.model}, cases={len(cases)}")
    for case in cases:
        image_path = (EVAL_DIR / case["image"]).resolve()
        if not image_path.is_relative_to(EVAL_DIR.resolve()):
            print(f"ERROR {case['id']}: image path escapes evaluation directory")
            failures += 1
            continue
        if image_path.suffix.lower() not in SUPPORTED_IMAGE_SUFFIXES:
            print(f"ERROR {case['id']}: unsupported image format {image_path.suffix}")
            failures += 1
            continue
        try:
            answer = ask_ollama(
                image_path,
                case["question"],
                args.model,
                args.ollama_url,
                args.timeout,
            )
        except (OSError, ValueError, RuntimeError) as exc:
            print(f"ERROR {case['id']}: {exc}")
            failures += 1
            continue
        matched = matches_expected_groups(answer, case["expected_groups"])
        passed += matched
        print(f"{'PASS' if matched else 'FAIL'} [{case['category']}] {case['id']}: {answer}")

    rate = passed / len(cases) if cases else 0.0
    print(f"Score: {passed}/{len(cases)} = {rate:.0%}; threshold={args.threshold:.0%}")
    if failures:
        return 2
    return 0 if rate >= args.threshold else 1


if __name__ == "__main__":
    sys.exit(main())
