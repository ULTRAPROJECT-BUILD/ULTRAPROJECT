#!/usr/bin/env python3
"""Check visual-spec lock state for stale leases and concurrency hazards."""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

try:
    import jsonschema
except ImportError as exc:  # pragma: no cover - dependency gate
    raise SystemExit("check_vs_concurrency.py requires jsonschema. Install with: python3 -m pip install jsonschema") from exc

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
OUTPUT_SCHEMA = REPO_ROOT / "schemas" / "concurrency-report.schema.json"


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json-out", help="Optional path to write concurrency report JSON.")
    parser.add_argument("--vault-root", help="Optional vault root override; useful for isolated tests.")
    return parser.parse_args()


def now_dt() -> datetime:
    """Return the current UTC datetime."""
    return datetime.now(timezone.utc)


def now_iso() -> str:
    """Return the current UTC timestamp."""
    return now_dt().isoformat()


def parse_datetime(value: Any) -> datetime | None:
    """Parse a lock timestamp as aware UTC."""
    if value is None or str(value).strip() == "":
        return None
    try:
        if isinstance(value, datetime):
            parsed = value
        else:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def resolve_vault_root(raw: str | None = None) -> Path:
    """Resolve the active vault root from an override, environment, or cwd."""
    candidates: list[Path] = []
    if raw:
        candidates.append(Path(raw).expanduser())
    env_root = os.environ.get("ONESHOT_VAULT_ROOT")
    if env_root:
        candidates.append(Path(env_root).expanduser())
    candidates.extend([REPO_ROOT / "vault", Path.cwd(), *Path.cwd().parents])
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved.name == "vault":
            return resolved
        if (resolved / "vault").is_dir():
            return (resolved / "vault").resolve()
    raise FileNotFoundError("Could not locate vault root")


def load_backend_config(vault_root: Path) -> dict[str, Any]:
    """Read vault/config/lock-backend.json."""
    config_path = vault_root / "config" / "lock-backend.json"
    if not config_path.exists():
        raise FileNotFoundError("vault/config/lock-backend.json is missing; run scripts/probe_lock_backend.py first")
    return json.loads(config_path.read_text(encoding="utf-8"))


def split_frontmatter(text: str, path: Path) -> tuple[str, str]:
    """Split markdown frontmatter from body."""
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        raise ValueError(f"{path} does not start with YAML frontmatter")
    closing_index = None
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            closing_index = index
            break
    if closing_index is None:
        raise ValueError(f"{path} has no closing YAML frontmatter delimiter")
    return "".join(lines[1:closing_index]), "".join(lines[closing_index + 1 :])


def load_frontmatter(path: Path) -> dict[str, Any]:
    """Load markdown YAML frontmatter."""
    frontmatter_text, _ = split_frontmatter(path.read_text(encoding="utf-8"), path)
    data = yaml.safe_load(frontmatter_text)
    return data if isinstance(data, dict) else {}


def lock_path_text(path: Path) -> str:
    """Return a stable path string for reports."""
    return str(path.resolve())


def read_fcntl_locks(vault_root: Path) -> list[dict[str, Any]]:
    """Read fcntl lock files from vault/locks/visual-spec."""
    locks: list[dict[str, Any]] = []
    lock_dir = vault_root / "locks" / "visual-spec"
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
            locks.append(
                {
                    "visual_spec_id": path.stem,
                    "lock_path": lock_path_text(path),
                    "parse_error": str(exc),
                    "holder_agent": "",
                    "base_revision_id": "",
                    "acquired_at": None,
                    "lease_expires_at": None,
                }
            )
            continue
        payload["lock_path"] = lock_path_text(path)
        payload.setdefault("visual_spec_id", path.stem)
        locks.append(payload)
    return locks


def read_sqlite_locks(vault_root: Path) -> list[dict[str, Any]]:
    """Read all SQLite lock rows through the backend module."""
    os.environ["ONESHOT_VAULT_ROOT"] = str(vault_root)
    if str(SCRIPT_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPT_DIR))
    import sqlite_lock_backend

    db_path = sqlite_lock_backend.db_path(vault_root)
    if not db_path.exists():
        return []
    conn = sqlite_lock_backend.connect(vault_root)
    try:
        rows = conn.execute("SELECT * FROM visual_spec_locks ORDER BY visual_spec_id").fetchall()
        return [
            {
                "visual_spec_id": row["visual_spec_id"],
                "holder_agent": row["holder_agent"],
                "holder_pid": row["holder_pid"],
                "holder_session_id": row["holder_session_id"],
                "base_revision_id": row["base_revision_id"],
                "acquired_at": row["acquired_at"],
                "lease_expires_at": row["lease_expires_at"],
                "lease_renewed_at": row["lease_renewed_at"],
                "lock_path": str(db_path),
            }
            for row in rows
        ]
    except sqlite3.Error:
        raise
    finally:
        conn.close()


def discover_visual_specs(vault_root: Path) -> dict[str, list[Path]]:
    """Index visual-spec files by visual_spec_id without requiring active status."""
    by_id: dict[str, list[Path]] = defaultdict(list)
    roots = [vault_root / "snapshots", vault_root / "clients"]
    for root in roots:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*-visual-spec-*.md")):
            try:
                frontmatter = load_frontmatter(path)
            except Exception:
                continue
            visual_spec_id = str(frontmatter.get("visual_spec_id") or "").strip()
            if visual_spec_id:
                by_id[visual_spec_id].append(path.resolve())
    return by_id


def stale_lock_record(lock: dict[str, Any]) -> dict[str, Any]:
    """Build a schema-compatible stale lock record."""
    return {
        "visual_spec_id": str(lock.get("visual_spec_id") or ""),
        "lock_path": str(lock.get("lock_path") or ""),
        "holder_agent": str(lock.get("holder_agent") or ""),
        "lease_expires_at": str(lock.get("lease_expires_at") or ""),
        "action_taken": "none",
    }


def conflict_record(first: dict[str, Any], second: dict[str, Any], reason: str) -> dict[str, Any]:
    """Build a conflict record from two lock records."""
    return {
        "old_revision": str(first.get("base_revision_id") or ""),
        "new_revision": str(second.get("base_revision_id") or ""),
        "conflict_reason": reason,
    }


def orphan_record(lock: dict[str, Any], reason: str) -> dict[str, Any]:
    """Build an orphan lock record."""
    return {
        "visual_spec_id": str(lock.get("visual_spec_id") or ""),
        "lock_path": str(lock.get("lock_path") or ""),
        "holder_agent": str(lock.get("holder_agent") or ""),
        "acquired_at": lock.get("acquired_at"),
        "reason": reason,
    }


def concurrent_modification_record(lock: dict[str, Any], vs_path: Path, mtime: datetime) -> dict[str, Any]:
    """Build a concurrent modification record."""
    return {
        "visual_spec_id": str(lock.get("visual_spec_id") or ""),
        "lock_path": str(lock.get("lock_path") or ""),
        "vs_path": str(vs_path.resolve()),
        "lock_acquired_at": str(lock.get("acquired_at") or ""),
        "vs_modified_at": mtime.isoformat(),
        "conflict_reason": "visual spec file mtime is newer than lock acquired_at",
    }


def check_locks(vault_root: Path, locks: list[dict[str, Any]]) -> dict[str, Any]:
    """Run concurrency checks over lock records."""
    current = now_dt()
    visual_specs = discover_visual_specs(vault_root)
    stale_locks: list[dict[str, Any]] = []
    conflicting_amendments: list[dict[str, Any]] = []
    orphaned_locks: list[dict[str, Any]] = []
    concurrent_modifications: list[dict[str, Any]] = []

    locks_by_vs: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for lock in locks:
        visual_spec_id = str(lock.get("visual_spec_id") or "")
        locks_by_vs[visual_spec_id].append(lock)
        expires_at = parse_datetime(lock.get("lease_expires_at"))
        if expires_at is None:
            orphaned_locks.append(orphan_record(lock, "lock has missing or unparsable lease_expires_at"))
        elif expires_at < current:
            stale_locks.append(stale_lock_record(lock))

        vs_paths = visual_specs.get(visual_spec_id, [])
        if not vs_paths:
            orphaned_locks.append(orphan_record(lock, f"no visual spec file found for visual_spec_id={visual_spec_id}"))
            continue
        acquired_at = parse_datetime(lock.get("acquired_at"))
        if acquired_at is None:
            orphaned_locks.append(orphan_record(lock, "lock has missing or unparsable acquired_at"))
            continue
        for vs_path in vs_paths:
            modified_at = datetime.fromtimestamp(vs_path.stat().st_mtime, timezone.utc)
            if modified_at > acquired_at:
                concurrent_modifications.append(concurrent_modification_record(lock, vs_path, modified_at))

    for visual_spec_id, grouped in sorted(locks_by_vs.items()):
        if len(grouped) <= 1:
            continue
        first = grouped[0]
        for second in grouped[1:]:
            conflicting_amendments.append(
                conflict_record(first, second, f"multiple locks held for visual_spec_id={visual_spec_id}")
            )

    recommended_actions: list[str] = []
    if stale_locks:
        recommended_actions.append("Run cleanup_stale_vs_locks.py")
    for item in orphaned_locks:
        recommended_actions.append(f"Investigate orphaned lock for visual_spec_id={item['visual_spec_id']}")
    if conflicting_amendments:
        recommended_actions.append("Investigate conflicting in-flight visual-spec amendments")
    if concurrent_modifications:
        recommended_actions.append("Inspect visual-spec files modified during lock hold")

    return {
        "checked_at": now_iso(),
        "stale_locks": stale_locks,
        "conflicting_amendments": conflicting_amendments,
        "orphaned_locks": orphaned_locks,
        "concurrent_modifications": concurrent_modifications,
        "recommended_actions": recommended_actions,
    }


def validate_output(payload: dict[str, Any]) -> None:
    """Validate output against schemas/concurrency-report.schema.json."""
    schema = json.loads(OUTPUT_SCHEMA.read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker())
    errors = sorted(validator.iter_errors(payload), key=lambda error: list(error.path))
    if errors:
        detail = "; ".join(f"{'/'.join(map(str, error.path)) or '/'}: {error.message}" for error in errors)
        raise ValueError(f"concurrency report schema validation failed: {detail}")


def emit(payload: dict[str, Any], json_out: str | None) -> None:
    """Validate and emit JSON."""
    validate_output(payload)
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if json_out:
        out_path = Path(json_out).expanduser()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text, encoding="utf-8")
    sys.stdout.write(text)


def run(args: argparse.Namespace) -> tuple[dict[str, Any], bool]:
    """Run the configured backend check."""
    vault_root = resolve_vault_root(args.vault_root)
    config = load_backend_config(vault_root)
    backend = config.get("backend")
    if backend == "fcntl_excl":
        locks = read_fcntl_locks(vault_root)
    elif backend == "sqlite":
        locks = read_sqlite_locks(vault_root)
    else:
        raise RuntimeError(f"Unsupported or missing lock backend ({backend}). Run scripts/probe_lock_backend.py.")
    payload = check_locks(vault_root, locks)
    has_concerns = any(
        payload[key]
        for key in ("stale_locks", "conflicting_amendments", "orphaned_locks", "concurrent_modifications")
    )
    return payload, has_concerns


def main() -> int:
    """Run the CLI."""
    args = parse_args()
    try:
        payload, has_concerns = run(args)
        emit(payload, args.json_out)
        return 1 if has_concerns else 0
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
