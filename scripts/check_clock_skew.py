#!/usr/bin/env python3
"""Detect clock skew risks for multi-host visual-spec lock deployments."""

from __future__ import annotations

import argparse
import json
import platform
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_MAX_SKEW_SECONDS = 5


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json-out", help="Optional path to write the JSON skew report.")
    return parser.parse_args()


def now_iso() -> str:
    """Return the current UTC timestamp as ISO text."""
    return datetime.now(timezone.utc).isoformat()


def resolve_vault_root() -> Path:
    """Resolve the vault root from script location or cwd."""
    script_candidate = SCRIPT_DIR.parent / "vault"
    if script_candidate.is_dir():
        return script_candidate.resolve()
    current = Path.cwd().resolve()
    for candidate in (current, *current.parents):
        if candidate.name == "vault" and (candidate / "locks").exists():
            return candidate
        if (candidate / "vault").is_dir():
            return (candidate / "vault").resolve()
    raise FileNotFoundError("Could not locate vault root.")


def read_platform_max_skew(vault_root: Path) -> int:
    """Read visual_spec_clock_skew_max_seconds from platform.md."""
    platform_path = vault_root / "config" / "platform.md"
    if not platform_path.exists():
        return DEFAULT_MAX_SKEW_SECONDS
    try:
        text = platform_path.read_text(encoding="utf-8")
    except OSError:
        return DEFAULT_MAX_SKEW_SECONDS
    match = re.search(r"visual_spec_clock_skew_max_seconds:\s*(\d+)", text)
    return int(match.group(1)) if match else DEFAULT_MAX_SKEW_SECONDS


def read_backend_config(vault_root: Path) -> dict[str, Any]:
    """Read lock-backend.json when present."""
    path = vault_root / "config" / "lock-backend.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def run_command(args: list[str], timeout: int = 8) -> tuple[int, str]:
    """Run a command and return returncode plus combined output."""
    try:
        completed = subprocess.run(
            args,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return 127, str(exc)
    return completed.returncode, f"{completed.stdout}\n{completed.stderr}".strip()


def parse_offset(text: str) -> float | None:
    """Parse an NTP offset from common sntp output variants."""
    patterns = [
        r"offset\s+([+-]?\d+(?:\.\d+)?)",
        r"clock offset is\s+([+-]?\d+(?:\.\d+)?)",
        r"([+-]\d+(?:\.\d+)?)\s*\+/-",
    ]
    for pattern_text in patterns:
        match = re.search(pattern_text, text, re.IGNORECASE)
        if match:
            return abs(float(match.group(1)))
    return None


def check_darwin() -> tuple[bool, float | None, str]:
    """Check NTP skew on macOS using sntp."""
    commands = (["sntp", "-t", "5", "time.apple.com"], ["sntp", "-t", "5", "pool.ntp.org"])
    last_output = ""
    for command in commands:
        code, output = run_command(command)
        last_output = output
        skew = parse_offset(output)
        if code == 0:
            return True, skew if skew is not None else 0.0, output
        if skew is not None:
            return True, skew, output
    return False, None, last_output


def check_linux() -> tuple[bool, float | None, str, str | None]:
    """Check clock sync status on Linux using timedatectl."""
    code, output = run_command(["timedatectl", "status"])
    timezone_match = re.search(r"Time zone:\s*([^\n]+)", output)
    synced_match = re.search(r"System clock synchronized:\s*(yes|no)", output, re.IGNORECASE)
    ntp_synced = code == 0 and bool(synced_match and synced_match.group(1).lower() == "yes")
    skew = 0.0 if ntp_synced else None
    return ntp_synced, skew, output, timezone_match.group(1).strip() if timezone_match else None


def is_multi_host(backend_config: dict[str, Any]) -> bool:
    """Heuristically detect multi-host vault lock usage."""
    filesystem = str(backend_config.get("filesystem", "")).lower()
    backend = str(backend_config.get("backend", "")).lower()
    category = str(backend_config.get("category", "")).lower()
    return backend == "sqlite" or category == "recoverable_via_sqlite" or filesystem in {"nfs", "smb", "fuse"}


def write_json(path: Path, payload: dict[str, Any]) -> None:
    """Write JSON output to a file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def emit(payload: dict[str, Any], json_out: str | None = None) -> None:
    """Emit JSON report output."""
    if json_out:
        write_json(Path(json_out).expanduser(), payload)
    print(json.dumps(payload, indent=2, sort_keys=True))


def main() -> int:
    """Run the clock skew check."""
    args = parse_args()
    vault_root = resolve_vault_root()
    backend_config = read_backend_config(vault_root)
    system_name = platform.system()
    max_allowed = read_platform_max_skew(vault_root)
    timezone_text = None

    if system_name == "Darwin":
        ntp_synced, skew_seconds, raw_output = check_darwin()
    elif system_name == "Linux":
        ntp_synced, skew_seconds, raw_output, timezone_text = check_linux()
    else:
        ntp_synced, skew_seconds, raw_output = False, None, f"unsupported platform: {system_name}"

    multi_host = is_multi_host(backend_config)
    skew_within_bounds = skew_seconds is None or skew_seconds <= max_allowed
    report: dict[str, Any] = {
        "checked_at": now_iso(),
        "platform": system_name,
        "ntp_synced": ntp_synced,
        "skew_seconds": skew_seconds,
        "multi_host_detected": multi_host,
        "skew_within_bounds": skew_within_bounds,
        "max_allowed_seconds": max_allowed,
    }
    if timezone_text:
        report["time_zone"] = timezone_text
    if raw_output:
        report["source_output"] = raw_output[-1000:]

    emit(report, args.json_out)
    if multi_host and not ntp_synced:
        print("NTP is not synchronized on a likely multi-host vault. Aborting.", file=sys.stderr)
        return 1
    if multi_host and skew_seconds is not None and skew_seconds > max_allowed:
        print(
            f"Clock skew ({skew_seconds:.3f}s) exceeds max allowed ({max_allowed}s) on a likely multi-host vault.",
            file=sys.stderr,
        )
        return 1
    if skew_seconds is not None and skew_seconds > 1:
        print(f"Warning: measured clock skew is {skew_seconds:.3f}s.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
