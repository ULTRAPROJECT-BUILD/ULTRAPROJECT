from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import check_operator_waiver_rate

NOW = datetime(2026, 5, 10, 12, 0, tzinfo=timezone.utc)
OPERATOR_ID = "op-test"


class FixedDatetime(datetime):
    @classmethod
    def now(cls, tz=None):  # type: ignore[override]
        return NOW.astimezone(tz) if tz else NOW.replace(tzinfo=None)


def freeze_now(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(check_operator_waiver_rate, "datetime", FixedDatetime)
    monkeypatch.setattr(check_operator_waiver_rate, "utc_now_iso", lambda: NOW.isoformat(timespec="seconds"))


def iso_days_ago(days: int) -> str:
    return (NOW.replace(hour=9) - check_operator_waiver_rate.timedelta(days=days)).isoformat()


def write_project_log(path: Path, total: int, *, days_ago: int) -> None:
    rows = [{"project": f"project-{index}", "operator": OPERATOR_ID, "timestamp": iso_days_ago(days_ago)} for index in range(total)]
    path.write_text(json.dumps({"projects": rows}, indent=2) + "\n", encoding="utf-8")


def write_waiver_log(path: Path, count: int, *, days_ago: int) -> None:
    lines = [
        "| Date | Project | Reason category | Operator | Outcome |",
        "| --- | --- | --- | --- | --- |",
    ]
    for index in range(count):
        lines.append(f"| {iso_days_ago(days_ago)} | project-{index} | accessibility | {OPERATOR_ID} | waived |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def payload_for(tmp_path: Path, *, waivers: int, total: int, days_ago: int) -> dict[str, object]:
    waiver_log = tmp_path / "waivers.md"
    project_log = tmp_path / "projects.json"
    write_waiver_log(waiver_log, waivers, days_ago=days_ago)
    write_project_log(project_log, total, days_ago=days_ago)
    args = SimpleNamespace(waivers_log=str(waiver_log), operator_id=OPERATOR_ID, total_projects_log=str(project_log), json_out=None)
    return check_operator_waiver_rate.build_payload(args)


def test_twenty_five_percent_has_no_alert(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    freeze_now(monkeypatch)
    payload = payload_for(tmp_path, waivers=5, total=20, days_ago=5)

    assert payload["verdict"] == "ok"
    assert payload["windows"]["30d"]["rate_pct"] == 25.0
    assert payload["windows"]["30d"]["alert_level"] == "none"
    assert payload["requires_second_review"] is False
    assert payload["requires_cooling_off"] is False


def test_thirty_five_percent_is_yellow(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    freeze_now(monkeypatch)
    payload = payload_for(tmp_path, waivers=7, total=20, days_ago=5)

    assert payload["verdict"] == "yellow"
    assert payload["windows"]["30d"]["rate_pct"] == 35.0
    assert payload["windows"]["30d"]["alert_level"] == "yellow"
    assert payload["requires_second_review"] is False
    assert payload["requires_cooling_off"] is False


def test_fifty_five_percent_is_red_in_30d(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    freeze_now(monkeypatch)
    payload = payload_for(tmp_path, waivers=11, total=20, days_ago=5)

    assert payload["verdict"] == "red"
    assert payload["windows"]["30d"]["rate_pct"] == 55.0
    assert payload["windows"]["30d"]["alert_level"] == "red"
    assert payload["requires_second_review"] is True
    assert payload["requires_cooling_off"] is True
    assert payload["cooling_off_hours"] == 24


def test_forty_five_percent_is_red_in_90d(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    freeze_now(monkeypatch)
    payload = payload_for(tmp_path, waivers=45, total=100, days_ago=60)

    assert payload["verdict"] == "red"
    assert payload["windows"]["30d"]["rate_pct"] == 0.0
    assert payload["windows"]["30d"]["alert_level"] == "none"
    assert payload["windows"]["90d"]["rate_pct"] == 45.0
    assert payload["windows"]["90d"]["alert_level"] == "red"
    assert payload["requires_second_review"] is True
    assert payload["requires_cooling_off"] is True
