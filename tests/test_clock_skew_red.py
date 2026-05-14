from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import check_clock_skew


def write_backend(vault: Path, payload: dict[str, object]) -> None:
    (vault / "config").mkdir(parents=True)
    (vault / "config" / "lock-backend.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def run_clock(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    backend: dict[str, object],
    ntp_synced: bool,
    skew_seconds: float | None,
) -> int:
    vault = tmp_path / "vault"
    write_backend(vault, backend)
    monkeypatch.setattr(check_clock_skew, "parse_args", lambda: SimpleNamespace(json_out=None))
    monkeypatch.setattr(check_clock_skew, "resolve_vault_root", lambda: vault)
    monkeypatch.setattr(check_clock_skew.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(check_clock_skew, "check_darwin", lambda: (ntp_synced, skew_seconds, f"offset {skew_seconds}"))
    return check_clock_skew.main()


def test_synced_single_host_passes(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    rc = run_clock(
        monkeypatch,
        tmp_path,
        backend={"backend": "fcntl_excl", "filesystem": "apfs", "category": "supported_local"},
        ntp_synced=True,
        skew_seconds=0.0,
    )
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert rc == 0
    assert payload["multi_host_detected"] is False
    assert payload["ntp_synced"] is True
    assert payload["skew_within_bounds"] is True
    assert captured.err == ""


def test_three_second_drift_passes_with_warning(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    rc = run_clock(
        monkeypatch,
        tmp_path,
        backend={"backend": "sqlite", "filesystem": "nfs", "category": "recoverable_via_sqlite"},
        ntp_synced=True,
        skew_seconds=3.0,
    )
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert rc == 0
    assert payload["multi_host_detected"] is True
    assert payload["skew_within_bounds"] is True
    assert "Warning: measured clock skew is 3.000s" in captured.err


def test_eight_second_drift_fails_on_multi_host(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    rc = run_clock(
        monkeypatch,
        tmp_path,
        backend={"backend": "sqlite", "filesystem": "nfs", "category": "recoverable_via_sqlite"},
        ntp_synced=True,
        skew_seconds=8.0,
    )
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert rc == 1
    assert payload["multi_host_detected"] is True
    assert payload["skew_within_bounds"] is False
    assert "exceeds max allowed" in captured.err


def test_unsynced_ntp_fails_on_multi_host(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    rc = run_clock(
        monkeypatch,
        tmp_path,
        backend={"backend": "sqlite", "filesystem": "nfs", "category": "recoverable_via_sqlite"},
        ntp_synced=False,
        skew_seconds=None,
    )
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert rc == 1
    assert payload["multi_host_detected"] is True
    assert payload["ntp_synced"] is False
    assert "NTP is not synchronized" in captured.err
