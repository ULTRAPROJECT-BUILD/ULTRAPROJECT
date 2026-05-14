#!/usr/bin/env python3
"""Probe the vault lock directory and select a safe visual-spec lock backend."""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

SUPPORTED_LOCAL = {"apfs", "ext4", "btrfs", "xfs", "hfs+"}
RECOVERABLE_VIA_SQLITE = {"nfs", "fuse", "smb"}
CACHE_MAX_AGE = timedelta(hours=24)

CLOUD_MARKERS = {
    ".dropbox": "cloud_sync_dropbox",
    ".icloud": "cloud_sync_icloud",
    "iCloudDrive": "cloud_sync_icloud",
    "OneDrive": "cloud_sync_onedrive",
    "Google Drive": "cloud_sync_gdrive",
    "pCloudDrive": "cloud_sync_pcloud",
}


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vault-root", help="Path to the vault directory or repo root containing vault/.")
    parser.add_argument("--force-reprobe", action="store_true", help="Ignore a fresh cached probe result.")
    parser.add_argument("--json-out", help="Optional path to write the JSON probe result.")
    return parser.parse_args()


def now_iso() -> str:
    """Return an explicit UTC ISO timestamp."""
    return datetime.now(timezone.utc).isoformat()


def parse_timestamp(value: str) -> datetime | None:
    """Parse an ISO timestamp, accepting a trailing Z."""
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def resolve_vault_root(raw_path: str | None = None) -> Path:
    """Resolve the OneShot vault root."""
    if raw_path:
        candidate = Path(raw_path).expanduser().resolve()
        if candidate.name == "vault" or (candidate / "locks").exists():
            return candidate
        if (candidate / "vault").is_dir():
            return (candidate / "vault").resolve()
        return candidate

    current = Path.cwd().resolve()
    for candidate in (current, *current.parents):
        if candidate.name == "vault" and (candidate / "locks").exists():
            return candidate
        if (candidate / "vault").is_dir():
            return (candidate / "vault").resolve()
    raise FileNotFoundError("Could not locate a vault/ directory from the current working directory.")


def run_command(args: list[str], timeout: int = 5) -> str:
    """Run a command and return combined stdout/stderr text."""
    completed = subprocess.run(
        args,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
    )
    return f"{completed.stdout}\n{completed.stderr}".strip()


def is_relative_to(path: Path, base: Path) -> bool:
    """Return whether path is inside base, compatible with Python 3.9."""
    try:
        path.relative_to(base)
    except ValueError:
        return False
    return True


def normalize_fs_type(fs_type: str | None) -> str:
    """Normalize platform-specific filesystem labels into policy names."""
    fs = (fs_type or "unknown").strip().lower()
    if fs.startswith("nfs"):
        return "nfs"
    if fs in {"smbfs", "cifs"} or fs.startswith("smb"):
        return "smb"
    if fs.startswith("fuse"):
        return "fuse"
    if fs in {"hfs", "hfsplus", "hfs+"}:
        return "hfs+"
    return fs or "unknown"


def parse_mount_lines(mount_text: str, lock_dir: Path) -> tuple[str, str | None]:
    """Find the longest mount point that covers lock_dir."""
    best_len = -1
    best_fs: str | None = None
    best_line: str | None = None
    resolved_lock_dir = lock_dir.resolve()

    for line in mount_text.splitlines():
        match = re.search(r"\son\s(.+?)\s\(([^,\s)]+)", line)
        if not match:
            continue
        mount_point_text, fs_type = match.group(1), match.group(2)
        try:
            mount_point = Path(mount_point_text).resolve()
        except OSError:
            mount_point = Path(mount_point_text)
        if not is_relative_to(resolved_lock_dir, mount_point):
            continue
        mount_len = len(str(mount_point))
        if mount_len > best_len:
            best_len = mount_len
            best_fs = fs_type
            best_line = line

    return normalize_fs_type(best_fs), best_line


def parse_proc_mounts(lock_dir: Path) -> tuple[str, str | None]:
    """Parse /proc/mounts for Linux fallback filesystem detection."""
    proc_mounts = Path("/proc/mounts")
    if not proc_mounts.exists():
        return "unknown", None
    best_len = -1
    best_fs: str | None = None
    best_line: str | None = None
    resolved_lock_dir = lock_dir.resolve()
    for line in proc_mounts.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.split()
        if len(parts) < 3:
            continue
        mount_point_text = parts[1].replace("\\040", " ")
        fs_type = parts[2]
        mount_point = Path(mount_point_text)
        if not is_relative_to(resolved_lock_dir, mount_point):
            continue
        mount_len = len(str(mount_point))
        if mount_len > best_len:
            best_len = mount_len
            best_fs = fs_type
            best_line = line
    return normalize_fs_type(best_fs), best_line


def detect_filesystem(lock_dir: Path, system_name: str) -> tuple[str, str, str | None]:
    """Detect filesystem type and return normalized fs, mount text, and matched line."""
    if system_name == "Darwin":
        mount_text = run_command(["mount"])
        fs_type, mount_line = parse_mount_lines(mount_text, lock_dir)
        if fs_type == "unknown":
            try:
                fs_type = normalize_fs_type(run_command(["stat", "-f", "%T", str(lock_dir)]).splitlines()[0])
            except (IndexError, OSError, subprocess.SubprocessError):
                pass
        return fs_type, mount_text, mount_line

    if system_name == "Linux":
        mount_text = ""
        try:
            os.statvfs(lock_dir)
        except OSError:
            pass
        try:
            mount_text = Path("/proc/mounts").read_text(encoding="utf-8", errors="replace")
        except OSError:
            pass
        try:
            findmnt = run_command(["findmnt", "-no", "FSTYPE", "--target", str(lock_dir)])
            if findmnt:
                return normalize_fs_type(findmnt.splitlines()[0]), mount_text, None
        except (OSError, subprocess.SubprocessError):
            pass
        fs_type, mount_line = parse_proc_mounts(lock_dir)
        return fs_type, mount_text, mount_line

    return "unknown", "", None


def classify_cloud_text(text: str) -> str | None:
    """Classify cloud-sync indicators from path or mount text."""
    lowered = text.lower()
    if "dropbox" in lowered:
        return "cloud_sync_dropbox"
    if "icloud" in lowered or "mobile documents" in lowered or "clouddocs" in lowered:
        return "cloud_sync_icloud"
    if "onedrive" in lowered:
        return "cloud_sync_onedrive"
    if "google drive" in lowered or "googledrive" in lowered or "gdrive" in lowered:
        return "cloud_sync_gdrive"
    if "pclouddrive" in lowered or "pcloud" in lowered:
        return "cloud_sync_pcloud"
    return None


def detect_cloud_sync(vault_root: Path, mount_text: str) -> tuple[bool, str | None]:
    """Detect cloud-sync folders from path ancestors and mount metadata."""
    path_hit = classify_cloud_text(str(vault_root))
    if path_hit:
        return True, path_hit

    for ancestor in (vault_root, *vault_root.parents):
        for marker, cloud_type in CLOUD_MARKERS.items():
            if (ancestor / marker).exists():
                return True, cloud_type

    mount_hit = classify_cloud_text(mount_text)
    if mount_hit:
        return True, mount_hit
    return False, None


def probe_o_excl(lock_dir: Path) -> tuple[bool, str | None]:
    """Verify O_CREAT|O_EXCL behavior with three acquire/release trials."""
    probe_path = lock_dir / "_probe.lock"
    try:
        if probe_path.exists():
            probe_path.unlink()
    except OSError as exc:
        return False, f"could not remove existing probe lock: {exc}"

    for trial in range(1, 4):
        fd: int | None = None
        try:
            fd = os.open(str(probe_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
            os.write(fd, f"probe trial {trial}\n".encode("utf-8"))
            try:
                second_fd = os.open(str(probe_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
            except FileExistsError:
                pass
            else:
                os.close(second_fd)
                return False, "second O_CREAT|O_EXCL open succeeded while probe lock existed"
            os.close(fd)
            fd = None
            probe_path.unlink()
            if probe_path.exists():
                return False, "probe lock still exists after unlink"
        except OSError as exc:
            return False, f"trial {trial} failed: {exc}"
        finally:
            if fd is not None:
                try:
                    os.close(fd)
                except OSError:
                    pass
            try:
                if probe_path.exists():
                    probe_path.unlink()
            except OSError:
                pass
    return True, None


def cached_result(config_path: Path) -> dict[str, Any] | None:
    """Return a fresh cached backend result, if available."""
    if not config_path.exists():
        return None
    try:
        cached = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    detected_at = parse_timestamp(str(cached.get("detected_at", "")))
    if detected_at is None:
        return None
    if datetime.now(timezone.utc) - detected_at <= CACHE_MAX_AGE:
        return cached
    return None


def write_json(path: Path, payload: dict[str, Any]) -> None:
    """Write pretty JSON, creating parent directories."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def emit(payload: dict[str, Any], json_out: str | None = None) -> None:
    """Emit JSON to stdout and optional file."""
    if json_out:
        write_json(Path(json_out).expanduser(), payload)
    print(json.dumps(payload, indent=2, sort_keys=True))


def main() -> int:
    """Run the backend probe."""
    args = parse_args()
    vault_root = resolve_vault_root(args.vault_root)
    lock_dir = vault_root / "locks"
    config_path = vault_root / "config" / "lock-backend.json"

    if not args.force_reprobe:
        cached = cached_result(config_path)
        if cached is not None:
            emit(cached, args.json_out)
            return 0 if cached.get("backend") else 1

    lock_dir.mkdir(parents=True, exist_ok=True)
    system_name = platform.system()
    base_result: dict[str, Any] = {
        "detected_at": now_iso(),
        "vault_root": str(vault_root),
        "filesystem": "unknown",
        "category": "unknown",
        "backend": None,
        "probe_passed": False,
        "cloud_sync_detected": False,
        "platform": system_name,
    }

    if system_name == "Windows":
        result = {**base_result, "category": "windows_not_supported", "status": "windows_not_supported"}
        write_json(config_path, result)
        emit(result, args.json_out)
        print("Windows is not supported for visual-spec vault locks in v6.", file=sys.stderr)
        return 1

    fs_type, mount_text, mount_line = detect_filesystem(lock_dir, system_name)
    cloud_detected, cloud_type = detect_cloud_sync(vault_root, mount_line or "")
    probe_passed, probe_error = probe_o_excl(lock_dir)

    result = {
        **base_result,
        "filesystem": fs_type,
        "probe_passed": probe_passed,
        "cloud_sync_detected": cloud_detected,
        "mount_line": mount_line,
    }
    if probe_error:
        result["probe_error"] = probe_error
    if cloud_type:
        result["cloud_sync_type"] = cloud_type

    if cloud_detected:
        result.update({"category": "forbidden", "backend": None})
        write_json(config_path, result)
        emit(result, args.json_out)
        print(
            f"Cloud-sync folder detected ({cloud_type}). OneShot vault locks are not safe on "
            "cloud-sync filesystems. Move vault to local storage.",
            file=sys.stderr,
        )
        return 1

    if fs_type in SUPPORTED_LOCAL:
        if not probe_passed:
            result.update({"category": "supported_local", "backend": None})
            write_json(config_path, result)
            emit(result, args.json_out)
            print(
                f"Filesystem ({fs_type}) does not honor O_CREAT|O_EXCL atomically. "
                "Refusing to use fcntl_excl backend.",
                file=sys.stderr,
            )
            return 1
        result.update({"category": "supported_local", "backend": "fcntl_excl"})
        write_json(config_path, result)
        emit(result, args.json_out)
        return 0

    if fs_type in RECOVERABLE_VIA_SQLITE:
        result.update({"category": "recoverable_via_sqlite", "backend": "sqlite"})
        write_json(config_path, result)
        emit(result, args.json_out)
        return 0

    result.update({"category": "forbidden", "backend": None})
    write_json(config_path, result)
    emit(result, args.json_out)
    print(f"Unknown filesystem ({fs_type}). Cannot guarantee lock atomicity. Aborting.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
