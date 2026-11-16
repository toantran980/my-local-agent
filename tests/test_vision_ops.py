import base64
import importlib.util
import io
import json
import sys
from pathlib import Path

import pytest

pytest.importorskip("mcp.server.fastmcp")

spec = importlib.util.spec_from_file_location(
    "vision_ops", Path(__file__).parent.parent / "mcp" / "vision_ops.py"
)
vision = importlib.util.module_from_spec(spec)
sys.modules["vision_ops"] = vision
spec.loader.exec_module(vision)


def test_ask_about_image_sends_local_image_to_configured_ollama(tmp_path, monkeypatch):
    image = tmp_path / "sample.png"
    image.write_bytes(b"test-image-bytes")
    monkeypatch.setenv("VISION_IMAGE_DIRS", str(tmp_path))
    monkeypatch.setenv("VISION_MODEL", "qwen2.5vl:7b")
    monkeypatch.setenv("OLLAMA_URL", "http://ollama.local:11434")
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["payload"] = json.loads(request.data)
        return io.BytesIO(json.dumps({"message": {"content": "A test image."}}).encode())

    monkeypatch.setattr(vision.urllib.request, "urlopen", fake_urlopen)

    result = vision.ask_about_image("sample.png", "Describe the image.")

    assert result == "A test image."
    assert captured["url"] == "http://ollama.local:11434/api/chat"
    assert captured["payload"]["model"] == "qwen2.5vl:7b"
    assert captured["payload"]["messages"][0]["content"] == "Describe the image."
    assert captured["payload"]["messages"][0]["images"] == [
        base64.b64encode(b"test-image-bytes").decode("ascii")
    ]


def test_ask_about_image_rejects_paths_outside_allowed_roots(tmp_path, monkeypatch):
    allowed = tmp_path / "allowed"
    outside = tmp_path / "outside.png"
    allowed.mkdir()
    outside.write_bytes(b"image")
    monkeypatch.setenv("VISION_IMAGE_DIRS", str(allowed))

    result = vision.ask_about_image(str(outside), "Describe it.")

    assert "inside a configured VISION_IMAGE_DIRS" in result


def test_ask_about_image_rejects_oversized_files(tmp_path, monkeypatch):
    image = tmp_path / "large.png"
    image.write_bytes(b"12345")
    monkeypatch.setenv("VISION_IMAGE_DIRS", str(tmp_path))
    monkeypatch.setenv("VISION_MAX_IMAGE_BYTES", "4")

    result = vision.ask_about_image("large.png", "Describe it.")

    assert "exceeds the configured 4-byte size limit" in result
