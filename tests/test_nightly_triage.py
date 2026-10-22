import importlib.util
import json
from pathlib import Path

EXPECTED_ALERT_COUNT = 2
EXPECTED_VRAM_GB = 9.0

spec = importlib.util.spec_from_file_location(
    "nightly_triage", Path(__file__).parent.parent / "scripts" / "nightly-triage.py"
)
nightly = importlib.util.module_from_spec(spec)
spec.loader.exec_module(nightly)


def test_telemetry_anomalies_wait_for_minimum_baseline():
    history = [{"duration_seconds": 10.0, "models": []} for _ in range(4)]

    assert nightly.detect_telemetry_anomalies(
        {"duration_seconds": 100.0, "models": []}, history
    ) == []


def test_telemetry_detects_high_duration_and_vram():
    history = [
        {"duration_seconds": 10.0, "models": [{"name": "qwen3:8b", "vram_gb": 5.0}]}
        for _ in range(5)
    ]
    current = {
        "duration_seconds": 30.0,
        "models": [{"name": "qwen3:8b", "vram_gb": 9.0}],
    }

    alerts = nightly.detect_telemetry_anomalies(current, history)

    assert len(alerts) == EXPECTED_ALERT_COUNT
    assert any("duration_seconds" in alert for alert in alerts)
    assert any("qwen3:8b" in alert for alert in alerts)


def test_record_telemetry_parses_gpu_report_and_appends_check(tmp_path):
    telemetry = tmp_path / "telemetry.jsonl"
    report_root = tmp_path / "reports"
    for _ in range(5):
        telemetry.parent.mkdir(parents=True, exist_ok=True)
        with telemetry.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({
                "date": "2026-10-15",
                "duration_seconds": 10.0,
                "models": [{"name": "qwen3:8b", "total_gb": 6.0, "vram_gb": 5.0}],
            }) + "\n")

    alerts = nightly.record_telemetry(
        40.0,
        "qwen3:8b  6.0GB total / 9.0GB VRAM  [GPU] qwen",
        day="2026-10-21",
        telemetry_path=telemetry,
        report_root=report_root,
    )

    assert len(alerts) == EXPECTED_ALERT_COUNT
    samples = [json.loads(line) for line in telemetry.read_text(encoding="utf-8").splitlines()]
    assert samples[-1]["models"][0]["vram_gb"] == EXPECTED_VRAM_GB
    report = (report_root / "2026-10-21.md").read_text(encoding="utf-8")
    assert "Telemetry anomaly check" in report
    assert "unusually high" in report
