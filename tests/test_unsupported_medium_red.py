from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import check_unsupported_medium_approval_rate

NOW = datetime(2026, 5, 10, 12, 0, tzinfo=timezone.utc)
OPERATOR_ID = "op-test"


class FixedDatetime(datetime):
    @classmethod
    def now(cls, tz=None):  # type: ignore[override]
        return NOW.astimezone(tz) if tz else NOW.replace(tzinfo=None)


def freeze_now(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(check_unsupported_medium_approval_rate, "datetime", FixedDatetime)
    monkeypatch.setattr(check_unsupported_medium_approval_rate, "utc_now_iso", lambda: NOW.isoformat(timespec="seconds"))


def write_proposal(path: Path, *, index: int, operator_id: str = OPERATOR_ID) -> None:
    created = (NOW - check_unsupported_medium_approval_rate.timedelta(days=10 + index)).isoformat()
    path.write_text(
        "\n".join(
            [
                "---",
                "type: preset-update-proposal",
                "operator_decision: approved",
                f"operator_id: {operator_id}",
                f"created: {created}",
                "regression_check:",
                "  status: operator_review_required",
                "---",
                f"# Proposal {index}",
                "",
            ]
        ),
        encoding="utf-8",
    )


def payload_for(tmp_path: Path, count: int) -> dict[str, object]:
    proposals = tmp_path / "proposals"
    proposals.mkdir()
    for index in range(count):
        write_proposal(proposals / f"proposal-{index}.md", index=index)
    args = SimpleNamespace(proposals_dir=str(proposals), operator_id=OPERATOR_ID, json_out=None)
    return check_unsupported_medium_approval_rate.build_payload(args)


@pytest.mark.parametrize("count", [1, 2])
def test_one_or_two_approvals_stay_below_red(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, count: int) -> None:
    freeze_now(monkeypatch)
    payload = payload_for(tmp_path, count)

    assert payload["verdict"] == "ok"
    assert payload["windows"]["90d"]["approvals"] == count
    assert payload["windows"]["90d"]["alert_level"] == "none"
    assert payload["requires_second_review"] is False
    assert payload["requires_cooling_off"] is False


def test_four_approvals_is_red(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    freeze_now(monkeypatch)
    payload = payload_for(tmp_path, 4)

    assert payload["verdict"] == "red"
    assert payload["windows"]["90d"]["approvals"] == 4
    assert payload["windows"]["90d"]["threshold_count"] == 3
    assert payload["windows"]["90d"]["alert_level"] == "red"
    assert payload["requires_second_review"] is True
    assert payload["requires_cooling_off"] is True
    assert payload["cooling_off_hours"] == 48
