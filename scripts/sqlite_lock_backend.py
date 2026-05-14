#!/usr/bin/env python3
"""SQLite visual-spec lock backend for shared filesystem deployments."""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_SQLITE_TEMPLATE = "{vault_root}/locks/_lock_store.db"

CREATE_LOCKS_SQL = """
CREATE TABLE IF NOT EXISTS visual_spec_locks (
  visual_spec_id TEXT PRIMARY KEY,
  holder_agent TEXT NOT NULL,
  holder_pid INTEGER NOT NULL,
  holder_session_id TEXT NOT NULL,
  base_revision_id TEXT NOT NULL,
  acquired_at TEXT NOT NULL,
  lease_expires_at TEXT NOT NULL,
  lease_renewed_at TEXT NOT NULL,
  generation INTEGER NOT NULL DEFAULT 0
)
"""

CREATE_GENERATION_SQL = """
CREATE TABLE IF NOT EXISTS visual_spec_generation (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  generation INTEGER NOT NULL DEFAULT 0,
  last_amendment_at TEXT
)
"""


def now_dt() -> datetime:
    """Return the current UTC datetime."""
    return datetime.now(timezone.utc)


def now_iso() -> str:
    """Return the current UTC timestamp as ISO text."""
    return now_dt().isoformat()


def to_iso(value: str | datetime | None = None) -> str:
    """Convert a datetime or ISO-ish value to explicit UTC ISO text."""
    if value is None:
        return now_iso()
    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat()


def resolve_vault_root(raw_path: str | None = None) -> Path:
    """Resolve the OneShot vault root."""
    raw_path = raw_path or os.environ.get("ONESHOT_VAULT_ROOT")
    if raw_path:
        candidate = Path(raw_path).expanduser().resolve()
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


def sqlite_template(vault_root: Path) -> str:
    """Read the SQLite lock path template from platform.md when present."""
    platform_path = vault_root / "config" / "platform.md"
    if not platform_path.exists():
        return DEFAULT_SQLITE_TEMPLATE
    try:
        text = platform_path.read_text(encoding="utf-8")
    except OSError:
        return DEFAULT_SQLITE_TEMPLATE
    match = re.search(r'visual_spec_lock_backend_sqlite_path_template:\s*["\']?([^"\']+)["\']?', text)
    return match.group(1).strip() if match else DEFAULT_SQLITE_TEMPLATE


def db_path(vault_root: Path | None = None) -> Path:
    """Return the SQLite lock-store path."""
    root = vault_root or resolve_vault_root()
    return Path(sqlite_template(root).replace("{vault_root}", str(root))).expanduser().resolve()


def connect(vault_root: Path | None = None) -> sqlite3.Connection:
    """Open a SQLite connection with explicit transaction control."""
    path = db_path(vault_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=30, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 30000")
    ensure_schema(conn)
    return conn


def ensure_schema(conn: sqlite3.Connection) -> None:
    """Create backend tables on first use."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        conn.execute(CREATE_LOCKS_SQL)
        conn.execute(CREATE_GENERATION_SQL)
        conn.execute("INSERT OR IGNORE INTO visual_spec_generation (id, generation) VALUES (1, 0)")
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise


def row_to_lock(row: sqlite3.Row, include_generation: bool = False) -> dict[str, Any]:
    """Convert a SQLite row to a lock dictionary."""
    payload = {
        "visual_spec_id": row["visual_spec_id"],
        "holder_agent": row["holder_agent"],
        "holder_pid": row["holder_pid"],
        "holder_session_id": row["holder_session_id"],
        "base_revision_id": row["base_revision_id"],
        "acquired_at": row["acquired_at"],
        "lease_expires_at": row["lease_expires_at"],
        "lease_renewed_at": row["lease_renewed_at"],
    }
    if include_generation:
        payload["generation"] = row["generation"]
    return payload


def acquire(
    visual_spec_id: str,
    holder_agent: str,
    holder_pid: int,
    holder_session_id: str,
    base_revision_id: str,
    lease_minutes: int = 5,
) -> bool:
    """Acquire a lock, returning False if the visual spec is already locked."""
    acquired_at = now_dt()
    expires_at = acquired_at + timedelta(minutes=lease_minutes)
    conn = connect()
    conn.execute("BEGIN IMMEDIATE")
    try:
        cursor = conn.execute(
            """
            INSERT INTO visual_spec_locks (
              visual_spec_id, holder_agent, holder_pid, holder_session_id,
              base_revision_id, acquired_at, lease_expires_at,
              lease_renewed_at, generation
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, (SELECT generation FROM visual_spec_generation WHERE id = 1))
            ON CONFLICT(visual_spec_id) DO NOTHING
            """,
            (
                visual_spec_id,
                holder_agent,
                int(holder_pid),
                holder_session_id,
                base_revision_id,
                acquired_at.isoformat(),
                expires_at.isoformat(),
                acquired_at.isoformat(),
            ),
        )
        conn.execute("COMMIT")
        return cursor.rowcount == 1
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()


def renew(visual_spec_id: str, holder_session_id: str, lease_minutes: int = 5) -> bool:
    """Renew a lock lease when the caller is the current holder."""
    renewed_at = now_dt()
    expires_at = renewed_at + timedelta(minutes=lease_minutes)
    conn = connect()
    conn.execute("BEGIN IMMEDIATE")
    try:
        cursor = conn.execute(
            """
            UPDATE visual_spec_locks
            SET lease_renewed_at = ?, lease_expires_at = ?
            WHERE visual_spec_id = ? AND holder_session_id = ?
            """,
            (renewed_at.isoformat(), expires_at.isoformat(), visual_spec_id, holder_session_id),
        )
        conn.execute("COMMIT")
        return cursor.rowcount == 1
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()


def release(visual_spec_id: str, holder_session_id: str) -> bool:
    """Release a lock when the caller is the current holder."""
    conn = connect()
    conn.execute("BEGIN IMMEDIATE")
    try:
        cursor = conn.execute(
            "DELETE FROM visual_spec_locks WHERE visual_spec_id = ? AND holder_session_id = ?",
            (visual_spec_id, holder_session_id),
        )
        conn.execute("COMMIT")
        return cursor.rowcount == 1
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()


def read(visual_spec_id: str) -> dict[str, Any] | None:
    """Read the current lock content for a visual spec."""
    conn = connect()
    try:
        row = conn.execute("SELECT * FROM visual_spec_locks WHERE visual_spec_id = ?", (visual_spec_id,)).fetchone()
        return row_to_lock(row) if row else None
    finally:
        conn.close()


def list_stale(now: str | datetime) -> list[dict[str, Any]]:
    """List stale locks without deleting them."""
    now_text = to_iso(now)
    conn = connect()
    try:
        rows = conn.execute(
            "SELECT * FROM visual_spec_locks WHERE lease_expires_at < ? ORDER BY lease_expires_at",
            (now_text,),
        ).fetchall()
        return [row_to_lock(row, include_generation=True) for row in rows]
    finally:
        conn.close()


def cleanup_stale(now: str | datetime) -> list[dict[str, Any]]:
    """Remove expired locks and return removed rows for audit."""
    now_text = to_iso(now)
    conn = connect()
    conn.execute("BEGIN IMMEDIATE")
    try:
        rows = conn.execute(
            "SELECT * FROM visual_spec_locks WHERE lease_expires_at < ? ORDER BY lease_expires_at",
            (now_text,),
        ).fetchall()
        removed = [row_to_lock(row, include_generation=True) for row in rows]
        conn.execute("DELETE FROM visual_spec_locks WHERE lease_expires_at < ?", (now_text,))
        conn.execute("COMMIT")
        return removed
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()


def bump_generation() -> int:
    """Atomically increment and return the visual-spec resolver generation."""
    amended_at = now_iso()
    conn = connect()
    conn.execute("BEGIN IMMEDIATE")
    try:
        conn.execute(
            "UPDATE visual_spec_generation SET generation = generation + 1, last_amendment_at = ? WHERE id = 1",
            (amended_at,),
        )
        row = conn.execute("SELECT generation FROM visual_spec_generation WHERE id = 1").fetchone()
        conn.execute("COMMIT")
        return int(row["generation"])
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()


def get_generation() -> dict[str, Any]:
    """Read the current visual-spec resolver generation."""
    conn = connect()
    try:
        row = conn.execute("SELECT generation, last_amendment_at FROM visual_spec_generation WHERE id = 1").fetchone()
        if row is None:
            return {"generation": 0, "last_amendment_at": None}
        return {"generation": int(row["generation"]), "last_amendment_at": row["last_amendment_at"]}
    finally:
        conn.close()


def parse_args() -> argparse.Namespace:
    """Parse the small diagnostic CLI for this backend."""
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    read_parser = subparsers.add_parser("read")
    read_parser.add_argument("--visual-spec-id", required=True)
    cleanup_parser = subparsers.add_parser("cleanup-stale")
    cleanup_parser.add_argument("--now", default=now_iso())
    subparsers.add_parser("bump-generation")
    subparsers.add_parser("get-generation")
    return parser.parse_args()


def main() -> int:
    """Run diagnostic backend commands."""
    args = parse_args()
    if args.command == "read":
        print(json.dumps(read(args.visual_spec_id), indent=2, sort_keys=True))
    elif args.command == "cleanup-stale":
        print(json.dumps(cleanup_stale(args.now), indent=2, sort_keys=True))
    elif args.command == "bump-generation":
        print(json.dumps({"generation": bump_generation(), "last_amendment_at": get_generation()["last_amendment_at"]}))
    elif args.command == "get-generation":
        print(json.dumps(get_generation(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
