#!/usr/bin/env python3
"""Check artifact producer locks and registry concurrency hazards."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import artifact_registry


def now_dt() -> datetime:
    """Return machine-local aware datetime."""
    return datetime.now().astimezone()


def now_iso() -> str:
    """Return machine-local ISO timestamp."""
    return now_dt().isoformat(timespec="seconds")


def parse_datetime(value: Any) -> datetime | None:
    """Parse an ISO timestamp into an aware datetime."""
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.astimezone()
    return parsed


def lock_path_text(path: Path) -> str:
    """Return a stable lock path string."""
    return str(path.resolve())


def read_producer_locks(vault_root: Path) -> list[dict[str, Any]]:
    """Read per-producer lock files."""
    locks: list[dict[str, Any]] = []
    lock_dir = artifact_registry.lock_dir(vault_root)
    if not lock_dir.exists():
        return locks
    for path in sorted(lock_dir.glob("*.lock")):
        if path.name.startswith("_"):
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("lock JSON is not an object")
        except Exception as exc:
            payload = {
                "producer_id": path.stem,
                "holder_agent": "",
                "holder_pid": None,
                "holder_session_id": "",
                "acquired_at": None,
                "lease_expires_at": None,
                "parse_error": str(exc),
            }
        payload.setdefault("producer_id", path.stem)
        payload["lock_path"] = lock_path_text(path)
        locks.append(payload)
    return locks


def stale_lock_record(lock: dict[str, Any], action_taken: str) -> dict[str, Any]:
    """Build a stale lock telemetry record."""
    return {
        "producer_id": str(lock.get("producer_id") or ""),
        "lock_path": str(lock.get("lock_path") or ""),
        "holder_agent": str(lock.get("holder_agent") or ""),
        "lease_expires_at": str(lock.get("lease_expires_at") or ""),
        "action_taken": action_taken,
    }


def orphan_lock_record(lock: dict[str, Any], reason: str) -> dict[str, Any]:
    """Build an orphan lock telemetry record."""
    return {
        "producer_id": str(lock.get("producer_id") or ""),
        "lock_path": str(lock.get("lock_path") or ""),
        "holder_agent": str(lock.get("holder_agent") or ""),
        "acquired_at": lock.get("acquired_at"),
        "reason": reason,
    }


def duplicate_record(producer_id: str, count: int) -> dict[str, Any]:
    """Build a duplicate producer ID record."""
    return {
        "producer_id": producer_id,
        "count": count,
        "reason": "multiple registry entries claim the same producer_id",
    }


def cleanup_lock(lock: dict[str, Any]) -> str:
    """Remove a stale lock file."""
    path = Path(str(lock.get("lock_path") or ""))
    try:
        path.unlink()
        artifact_registry.fsync_parent(path)
        return "removed"
    except FileNotFoundError:
        return "already_missing"
    except OSError as exc:
        return f"cleanup_failed:{exc}"


def check_concurrency(vault_root: Path, cleanup_stale: bool) -> dict[str, Any]:
    """Run producer concurrency checks."""
    registry = artifact_registry.read_registry()
    registered_ids = [str(item.get("producer_id") or "") for item in artifact_registry.producers(registry)]
    registered_set = set(registered_ids)
    id_counts = Counter(registered_ids)
    locks = read_producer_locks(vault_root)

    stale_locks: list[dict[str, Any]] = []
    orphaned_locks: list[dict[str, Any]] = []
    duplicate_registrations = [
        duplicate_record(producer_id, count)
        for producer_id, count in sorted(id_counts.items())
        if producer_id and count > 1
    ]

    current = now_dt()
    for lock in locks:
        producer_id = str(lock.get("producer_id") or "")
        expires_at = parse_datetime(lock.get("lease_expires_at"))
        if expires_at is None:
            orphaned_locks.append(orphan_lock_record(lock, "lock has missing or unparsable lease_expires_at"))
        elif expires_at < current:
            action = cleanup_lock(lock) if cleanup_stale else "none"
            stale_locks.append(stale_lock_record(lock, action))

        if producer_id not in registered_set:
            orphaned_locks.append(orphan_lock_record(lock, f"no registry producer found for producer_id={producer_id}"))

    recommended_actions: list[str] = []
    if stale_locks and not cleanup_stale:
        recommended_actions.append("Run check_artifact_producer_concurrency.py --cleanup-stale")
    for item in orphaned_locks:
        recommended_actions.append(f"Investigate orphaned producer lock for producer_id={item['producer_id']}")
    if duplicate_registrations:
        recommended_actions.append("Manually repair duplicate producer_id entries in vault/config/artifact-producers.md")

    return {
        "checked_at": now_iso(),
        "stale_locks": stale_locks,
        "duplicate_registrations": duplicate_registrations,
        "orphaned_locks": orphaned_locks,
        "recommended_actions": recommended_actions,
    }


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cleanup-stale", action="store_true")
    parser.add_argument("--json-out")
    parser.add_argument("--vault-root")
    return parser.parse_args()


def emit(payload: dict[str, Any], json_out: str | None) -> None:
    """Write report JSON to stdout and optional file."""
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if json_out:
        out_path = Path(json_out).expanduser()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text, encoding="utf-8")
    sys.stdout.write(text)


def main() -> int:
    """Run the producer concurrency checker."""
    args = parse_args()
    if args.vault_root:
        os.environ["ONESHOT_VAULT_ROOT"] = str(Path(args.vault_root).expanduser().resolve())
    try:
        vault_root = artifact_registry.resolve_vault_root()
        payload = check_concurrency(vault_root, args.cleanup_stale)
        emit(payload, args.json_out)
        has_concerns = bool(payload["stale_locks"] or payload["duplicate_registrations"] or payload["orphaned_locks"])
        return 1 if has_concerns else 0
    except Exception as exc:
        emit({"checked_at": now_iso(), "error": str(exc), "ok": False}, args.json_out)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
