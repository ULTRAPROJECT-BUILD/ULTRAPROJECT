#!/usr/bin/env python3
"""Clean up expired visual-spec amendment locks for the active backend."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Report stale locks without renaming/deleting them.")
    parser.add_argument("--json-out", help="Optional path to write the JSON audit list.")
    return parser.parse_args()


def now_dt() -> datetime:
    """Return the current UTC datetime."""
    return datetime.now(timezone.utc)


def parse_datetime(value: str) -> datetime:
    """Parse an explicit ISO timestamp."""
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def resolve_vault_root() -> Path:
    """Resolve the vault root from environment, script location, or cwd."""
    env_root = os.environ.get("ONESHOT_VAULT_ROOT")
    if env_root:
        candidate = Path(env_root).expanduser().resolve()
        if candidate.name == "vault" or (candidate / "locks").exists():
            return candidate
        if (candidate / "vault").is_dir():
            return (candidate / "vault").resolve()
        return candidate

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


def load_backend_config(vault_root: Path) -> dict[str, Any]:
    """Read the lock backend configuration."""
    config_path = vault_root / "config" / "lock-backend.json"
    if not config_path.exists():
        raise FileNotFoundError("vault/config/lock-backend.json is missing; run scripts/probe_lock_backend.py first.")
    return json.loads(config_path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    """Write JSON output to a file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def emit(payload: Any, json_out: str | None = None) -> None:
    """Emit JSON audit output."""
    if json_out:
        write_json(Path(json_out).expanduser(), payload)
    print(json.dumps(payload, indent=2, sort_keys=True))


def stale_target(path: Path, timestamp: str) -> Path:
    """Build a non-colliding stale lock target path."""
    target = path.with_name(f"{path.name}.stale-{timestamp}")
    counter = 1
    while target.exists():
        target = path.with_name(f"{path.name}.stale-{timestamp}-{counter}")
        counter += 1
    return target


def cleanup_fcntl(vault_root: Path, dry_run: bool) -> list[dict[str, Any]]:
    """Rename expired fcntl lock files to stale audit names."""
    current = now_dt()
    stamp = current.strftime("%Y%m%dT%H%M%SZ")
    visual_lock_dir = vault_root / "locks" / "visual-spec"
    results: list[dict[str, Any]] = []

    for path in sorted(visual_lock_dir.glob("*.lock")):
        if path.name.startswith("_"):
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            expires = parse_datetime(str(payload["lease_expires_at"]))
        except Exception as exc:
            results.append(
                {
                    "lock_path": str(path),
                    "action_taken": "operator_review",
                    "error": f"could not parse lock: {exc}",
                    "dry_run": dry_run,
                }
            )
            continue
        if expires >= current:
            continue

        target = stale_target(path, stamp)
        record = {
            "visual_spec_id": payload.get("visual_spec_id"),
            "lock_path": str(path),
            "stale_path": str(target),
            "holder_agent": payload.get("holder_agent"),
            "lease_expires_at": payload.get("lease_expires_at"),
            "action_taken": "dry_run" if dry_run else "renamed_stale",
            "dry_run": dry_run,
        }
        if not dry_run:
            path.rename(target)
        results.append(record)
    return results


def cleanup_sqlite(vault_root: Path, dry_run: bool) -> list[dict[str, Any]]:
    """Clean up stale SQLite locks through the backend module."""
    os.environ["ONESHOT_VAULT_ROOT"] = str(vault_root)
    import sqlite_lock_backend

    current = now_dt().isoformat()
    rows = sqlite_lock_backend.list_stale(current) if dry_run else sqlite_lock_backend.cleanup_stale(current)
    action = "dry_run" if dry_run else "removed"
    return [{**row, "action_taken": action, "dry_run": dry_run} for row in rows]


def main() -> int:
    """Run stale lock cleanup."""
    args = parse_args()
    try:
        vault_root = resolve_vault_root()
        config = load_backend_config(vault_root)
        backend = config.get("backend")
        if backend == "fcntl_excl":
            emit(cleanup_fcntl(vault_root, args.dry_run), args.json_out)
            return 0
        if backend == "sqlite":
            emit(cleanup_sqlite(vault_root, args.dry_run), args.json_out)
            return 0
        raise RuntimeError(f"Unsupported or missing lock backend ({backend}).")
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        emit([{"action_taken": "error", "error": str(exc), "dry_run": args.dry_run}], args.json_out)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
