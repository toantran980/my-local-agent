import importlib.util
import json
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "eval_tool_use", Path(__file__).parent.parent / "scripts" / "eval-tool-use.py"
)
evaluation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evaluation)


def test_load_runs_groups_events_and_ignores_incomplete_run(tmp_path):
    audit = tmp_path / "audit.jsonl"
    events = [
        {"event": "run_started", "prompt": "find it", "mode": "ask", "model": "local",
         "apply": False},
        {"event": "tool_called", "tool": "search", "arguments": {"pattern": "x"},
         "result": "found"},
        {"event": "run_finished", "answer": "done"},
        {"event": "run_started", "prompt": "unfinished", "mode": "agent"},
    ]
    audit.write_text("\n".join(json.dumps(event) for event in events), encoding="utf-8")

    runs = evaluation.load_runs(audit)

    assert len(runs) == 1
    assert runs[0]["prompt"] == "find it"
    assert runs[0]["answer"] == "done"
    assert runs[0]["tools"][0]["tool"] == "search"


def test_load_runs_reports_invalid_json_with_line_number(tmp_path):
    audit = tmp_path / "audit.jsonl"
    audit.write_text("{}\nnope\n", encoding="utf-8")

    with pytest.raises(ValueError, match=r"audit.jsonl:2: invalid JSON"):
        evaluation.load_runs(audit)


def test_summarize_tools_counts_errors_and_repeated_calls():
    run = {"tools": [
        {"tool": "search", "arguments": {"pattern": "x"}, "result": "found"},
        {"tool": "search", "arguments": {"pattern": "x"}, "result": "ERROR: timeout"},
        {"tool": "read_file", "arguments": {"path": "a.py"}, "result": "contents"},
    ]}

    assert evaluation.summarize_tools(run) == {
        "calls": 3,
        "errors": 1,
        "repeated_calls": 1,
        "tool_names": ["search", "search", "read_file"],
    }


def test_judge_run_uses_local_chat_endpoint_and_validates_scores(monkeypatch):
    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self):
            return json.dumps({"message": {"content": json.dumps({
                "tool_choice": 4, "efficiency": 5, "completion": 4, "evidence": "Relevant."
            })}}).encode()

    captured = {}

    def open_request(request, timeout):
        captured["url"] = request.full_url
        captured["payload"] = json.loads(request.data)
        captured["timeout"] = timeout
        return Response()

    monkeypatch.setattr(evaluation.urllib.request, "urlopen", open_request)
    result = evaluation.judge_run(
        {"mode": "ask", "prompt": "question", "tools": [], "answer": "answer", "apply": False},
        "qwen3:8b",
        "http://localhost:11434",
    )

    assert result["completion"] > 0
    assert captured["url"] == "http://localhost:11434/api/chat"
    assert captured["payload"]["format"] == evaluation.JUDGE_SCHEMA


def test_latest_audit_file_uses_newest_iso_date(tmp_path):
    (tmp_path / "2026-09-30.jsonl").touch()
    latest = tmp_path / "2026-10-21.jsonl"
    latest.touch()

    assert evaluation.latest_audit_file(tmp_path) == latest
