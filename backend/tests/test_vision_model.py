import json
from pathlib import Path

from app import vision_model


def test_vision_returns_clear_unconfigured_state(monkeypatch, tmp_path: Path):
    monkeypatch.delenv("FLEXY_AI_API_KEY", raising=False)
    result = vision_model.describe_scene(tmp_path / "unused.jpg")
    assert result["available"] is False
    assert result["description"] is None
    assert "not configured" in result["notice"]


def test_vision_parses_openai_compatible_response(monkeypatch, tmp_path: Path):
    frame = tmp_path / "frame.jpg"
    frame.write_bytes(b"fake-jpeg")
    monkeypatch.setenv("FLEXY_AI_API_KEY", "test-key")
    monkeypatch.setenv("FLEXY_AI_BASE_URL", "https://vision.example/v1")
    monkeypatch.setenv("FLEXY_VISION_MODEL", "vision-test")

    class FakeResponse:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def read(self):
            content = {"description": "A person standing beside a bicycle.",
                       "objects": ["person", "bicycle"], "actions": ["standing"],
                       "editing_notes": ["Potential establishing shot"], "confidence": 0.87}
            return json.dumps({"choices": [{"message": {"content": json.dumps(content)}}]}).encode()

    captured = {}
    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        captured["body"] = json.loads(request.data)
        return FakeResponse()

    monkeypatch.setattr(vision_model.urllib.request, "urlopen", fake_urlopen)
    result = vision_model.describe_scene(frame)
    assert result["available"] is True
    assert result["model"] == "vision-test"
    assert result["objects"] == ["person", "bicycle"]
    assert result["confidence"] == 0.87
    assert captured["url"] == "https://vision.example/v1/chat/completions"
    assert captured["body"]["messages"][1]["content"][1]["type"] == "image_url"
