from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import probe_lock_backend


def run_probe(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    fs_type: str,
    cloud_sync: bool = False,
    probe_passed: bool = True,
) -> tuple[int, dict[str, object], str]:
    vault = tmp_path / "vault"
    (vault / "config").mkdir(parents=True)
    monkeypatch.setattr(
        probe_lock_backend,
        "parse_args",
        lambda: SimpleNamespace(vault_root=str(vault), force_reprobe=True, json_out=None),
    )
    monkeypatch.setattr(probe_lock_backend.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(probe_lock_backend, "detect_filesystem", lambda _lock_dir, _system: (fs_type, "", "mock mount"))
    monkeypatch.setattr(
        probe_lock_backend,
        "detect_cloud_sync",
        lambda _vault_root, _mount_text: (cloud_sync, "cloud_sync_gdrive" if cloud_sync else None),
    )
    monkeypatch.setattr(
        probe_lock_backend,
        "probe_o_excl",
        lambda _lock_dir: (probe_passed, None if probe_passed else "broken exclusivity"),
    )

    rc = probe_lock_backend.main()
    payload = json.loads((vault / "config" / "lock-backend.json").read_text(encoding="utf-8"))
    return rc, payload, str(vault)


@pytest.mark.parametrize("fs_type", ["apfs", "ext4"])
def test_supported_local_filesystems_select_fcntl_excl(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, fs_type: str) -> None:
    rc, payload, vault = run_probe(monkeypatch, tmp_path, fs_type=fs_type)

    assert rc == 0
    assert payload["vault_root"] == vault
    assert payload["filesystem"] == fs_type
    assert payload["category"] == "supported_local"
    assert payload["backend"] == "fcntl_excl"
    assert payload["probe_passed"] is True


def test_nfs_selects_sqlite_fallback(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    rc, payload, _vault = run_probe(monkeypatch, tmp_path, fs_type="nfs")

    assert rc == 0
    assert payload["filesystem"] == "nfs"
    assert payload["category"] == "recoverable_via_sqlite"
    assert payload["backend"] == "sqlite"


def test_fuse_cloud_sync_fails_closed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    rc, payload, _vault = run_probe(monkeypatch, tmp_path, fs_type="fuse", cloud_sync=True)
    captured = capsys.readouterr()

    assert rc == 1
    assert payload["filesystem"] == "fuse"
    assert payload["cloud_sync_detected"] is True
    assert payload["category"] == "forbidden"
    assert payload["backend"] is None
    assert "Cloud-sync folder detected" in captured.err
    assert "Move vault to local storage" in captured.err


def test_unknown_filesystem_fails_closed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    rc, payload, _vault = run_probe(monkeypatch, tmp_path, fs_type="unknown")
    captured = capsys.readouterr()

    assert rc == 1
    assert payload["filesystem"] == "unknown"
    assert payload["category"] == "forbidden"
    assert payload["backend"] is None
    assert "Unknown filesystem" in captured.err
    assert "Cannot guarantee lock atomicity" in captured.err


def test_supported_local_probe_failure_fails_closed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    rc, payload, _vault = run_probe(monkeypatch, tmp_path, fs_type="apfs", probe_passed=False)
    captured = capsys.readouterr()

    assert rc == 1
    assert payload["filesystem"] == "apfs"
    assert payload["category"] == "supported_local"
    assert payload["backend"] is None
    assert payload["probe_error"] == "broken exclusivity"
    assert "Refusing to use fcntl_excl backend" in captured.err
