#!/usr/bin/env python3
"""Backend-dispatching public lock API for visual specification amendments."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

try:
    from jsonschema import Draft202012Validator, FormatChecker

    JSONSCHEMA_AVAILABLE = True
except ImportError:
    Draft202012Validator = None
    FormatChecker = None
    JSONSCHEMA_AVAILABLE = False


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    acquire_parser = subparsers.add_parser("acquire")
    acquire_parser.add_argument("--visual-spec-id", required=True)
    acquire_parser.add_argument("--holder-agent", required=True)
    acquire_parser.add_argument("--holder-pid", type=int, required=True)
    acquire_parser.add_argument("--holder-session-id", required=True)
    acquire_parser.add_argument("--base-revision-id", required=True)
    acquire_parser.add_argument("--lease-minutes", type=int, default=5)

    renew_parser = subparsers.add_parser("renew")
    renew_parser.add_argument("--visual-spec-id", required=True)
    renew_parser.add_argument("--holder-session-id", required=True)
    renew_parser.add_argument("--lease-minutes", type=int, default=5)

    release_parser = subparsers.add_parser("release")
    release_parser.add_argument("--visual-spec-id", required=True)
    release_parser.add_argument("--holder-session-id", required=True)

    read_parser = subparsers.add_parser("read")
    read_parser.add_argument("--visual-spec-id", required=True)

    subparsers.add_parser("bump-generation")
    subparsers.add_parser("get-generation")
    return parser.parse_args()


def now_dt() -> datetime:
    """Return the current UTC datetime."""
    return datetime.now(timezone.utc)


def now_iso() -> str:
    """Return the current UTC timestamp as ISO text."""
    return now_dt().isoformat()


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
    """Read the probed lock backend configuration."""
    config_path = vault_root / "config" / "lock-backend.json"
    if not config_path.exists():
        raise FileNotFoundError("vault/config/lock-backend.json is missing; run scripts/probe_lock_backend.py first.")
    return json.loads(config_path.read_text(encoding="utf-8"))


def schema_path() -> Path:
    """Return the amendment-lock schema path."""
    return SCRIPT_DIR.parent / "schemas" / "amendment-lock.schema.json"


def validate_lock(lock: dict[str, Any]) -> list[str]:
    """Validate lock content against schemas/amendment-lock.schema.json."""
    warnings: list[str] = []
    if not JSONSCHEMA_AVAILABLE:
        warnings.append("jsonschema is not available; skipped amendment-lock schema validation")
        print(warnings[-1], file=sys.stderr)
        return warnings
    schema = json.loads(schema_path().read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(lock), key=lambda error: list(error.path))
    if errors:
        detail = "; ".join(error.message for error in errors)
        raise ValueError(f"amendment-lock schema validation failed: {detail}")
    return warnings


def emit(payload: Any) -> None:
    """Print structured JSON to stdout."""
    print(json.dumps(payload, indent=2, sort_keys=True))


def fail(message: str, payload: dict[str, Any] | None = None) -> int:
    """Emit a structured failure and return a non-zero status."""
    print(message, file=sys.stderr)
    emit(payload or {"error": message})
    return 1


def lock_dir(vault_root: Path) -> Path:
    """Return the fcntl lock directory."""
    path = vault_root / "locks" / "visual-spec"
    path.mkdir(parents=True, exist_ok=True)
    return path


def lock_path(vault_root: Path, visual_spec_id: str) -> Path:
    """Return the fcntl lock path for a logical visual_spec_id."""
    if "/" in visual_spec_id or "\\" in visual_spec_id or visual_spec_id in {"", ".", ".."}:
        raise ValueError("visual_spec_id must be a logical ID, not a path")
    return lock_dir(vault_root) / f"{visual_spec_id}.lock"


def fsync_parent(path: Path) -> None:
    """Best-effort fsync of a directory after atomic file updates."""
    try:
        dir_fd = os.open(str(path.parent), os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(dir_fd)
    except OSError:
        pass
    finally:
        os.close(dir_fd)


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    """Atomically write JSON to path via a unique temporary file."""
    tmp_path = path.with_name(f"{path.name}.tmp-{os.getpid()}-{time.monotonic_ns()}")
    with tmp_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp_path, path)
    fsync_parent(path)


def read_json(path: Path) -> dict[str, Any] | None:
    """Read a JSON object from path if it exists."""
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def make_lock(
    visual_spec_id: str,
    holder_agent: str,
    holder_pid: int,
    holder_session_id: str,
    base_revision_id: str,
    lease_minutes: int,
) -> dict[str, Any]:
    """Create validated amendment lock content."""
    acquired_at = now_dt()
    lock = {
        "visual_spec_id": visual_spec_id,
        "holder_agent": holder_agent,
        "holder_pid": holder_pid,
        "holder_session_id": holder_session_id,
        "base_revision_id": base_revision_id,
        "acquired_at": acquired_at.isoformat(),
        "lease_expires_at": (acquired_at + timedelta(minutes=lease_minutes)).isoformat(),
        "lease_renewed_at": acquired_at.isoformat(),
    }
    validate_lock(lock)
    return lock


def fcntl_acquire(args: argparse.Namespace, vault_root: Path) -> dict[str, Any]:
    """Acquire a fcntl_excl visual-spec lock."""
    path = lock_path(vault_root, args.visual_spec_id)
    lock = make_lock(
        args.visual_spec_id,
        args.holder_agent,
        args.holder_pid,
        args.holder_session_id,
        args.base_revision_id,
        args.lease_minutes,
    )
    try:
        fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    except FileExistsError:
        return {"acquired": False, "lock": read_json(path), "error": "already_locked"}

    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(lock, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        fsync_parent(path)
    except Exception:
        try:
            path.unlink()
        except OSError:
            pass
        raise
    return {"acquired": True, "lock": lock, "error": None}


def fcntl_renew(args: argparse.Namespace, vault_root: Path) -> dict[str, Any]:
    """Renew a fcntl_excl visual-spec lock."""
    path = lock_path(vault_root, args.visual_spec_id)
    lock = read_json(path)
    if lock is None:
        return {"acquired": False, "lock": None, "error": "not_locked"}
    if lock.get("holder_session_id") != args.holder_session_id:
        return {"acquired": False, "lock": lock, "error": "not_lock_holder"}

    renewed_at = now_dt()
    lock["lease_renewed_at"] = renewed_at.isoformat()
    lock["lease_expires_at"] = (renewed_at + timedelta(minutes=args.lease_minutes)).isoformat()
    validate_lock(lock)
    atomic_write_json(path, lock)
    return {"acquired": True, "lock": lock, "error": None}


def fcntl_release(args: argparse.Namespace, vault_root: Path) -> dict[str, Any]:
    """Release a fcntl_excl visual-spec lock."""
    path = lock_path(vault_root, args.visual_spec_id)
    lock = read_json(path)
    if lock is None:
        return {"acquired": False, "lock": None, "error": "not_locked"}
    if lock.get("holder_session_id") != args.holder_session_id:
        return {"acquired": False, "lock": lock, "error": "not_lock_holder"}
    try:
        path.unlink()
        fsync_parent(path)
    except FileNotFoundError:
        return {"acquired": False, "lock": None, "error": "not_locked"}
    return {"acquired": True, "lock": lock, "error": None}


def fcntl_read(visual_spec_id: str, vault_root: Path) -> dict[str, Any] | None:
    """Read fcntl_excl lock content."""
    return read_json(lock_path(vault_root, visual_spec_id))


def generation_path(vault_root: Path) -> Path:
    """Return the fcntl generation file path."""
    return lock_dir(vault_root) / "_generation.json"


def generation_guard_path(vault_root: Path) -> Path:
    """Return the short-lived generation guard path."""
    return lock_dir(vault_root) / "_generation.json.lock"


def acquire_generation_guard(vault_root: Path, timeout_seconds: float = 5.0) -> int:
    """Acquire an O_EXCL guard for generation file updates."""
    path = generation_guard_path(vault_root)
    deadline = time.monotonic() + timeout_seconds
    while True:
        try:
            fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
            os.write(fd, f"{os.getpid()} {now_iso()}\n".encode("utf-8"))
            return fd
        except FileExistsError:
            if time.monotonic() >= deadline:
                raise TimeoutError("timed out waiting for generation guard")
            time.sleep(0.05)


def release_generation_guard(vault_root: Path, fd: int) -> None:
    """Release the generation update guard."""
    guard = generation_guard_path(vault_root)
    try:
        os.close(fd)
    finally:
        try:
            guard.unlink()
        except FileNotFoundError:
            pass
        fsync_parent(guard)


def fcntl_get_generation(vault_root: Path) -> dict[str, Any]:
    """Read the current fcntl generation counter."""
    payload = read_json(generation_path(vault_root))
    if payload is None:
        return {"generation": 0, "last_amendment_at": None}
    return {
        "generation": int(payload.get("generation", 0)),
        "last_amendment_at": payload.get("last_amendment_at"),
    }


def fcntl_bump_generation(vault_root: Path) -> dict[str, Any]:
    """Atomically increment the fcntl generation counter."""
    fd = acquire_generation_guard(vault_root)
    try:
        current = fcntl_get_generation(vault_root)
        payload = {
            "generation": int(current.get("generation", 0)) + 1,
            "last_amendment_at": now_iso(),
        }
        atomic_write_json(generation_path(vault_root), payload)
        return payload
    finally:
        release_generation_guard(vault_root, fd)


def sqlite_dispatch(args: argparse.Namespace, vault_root: Path) -> dict[str, Any] | None:
    """Dispatch a command to the SQLite backend."""
    os.environ["ONESHOT_VAULT_ROOT"] = str(vault_root)
    import sqlite_lock_backend

    if args.command == "acquire":
        lock = make_lock(
            args.visual_spec_id,
            args.holder_agent,
            args.holder_pid,
            args.holder_session_id,
            args.base_revision_id,
            args.lease_minutes,
        )
        acquired = sqlite_lock_backend.acquire(
            args.visual_spec_id,
            args.holder_agent,
            args.holder_pid,
            args.holder_session_id,
            args.base_revision_id,
            args.lease_minutes,
        )
        return {
            "acquired": acquired,
            "lock": lock if acquired else sqlite_lock_backend.read(args.visual_spec_id),
            "error": None if acquired else "already_locked",
        }
    if args.command == "renew":
        renewed = sqlite_lock_backend.renew(args.visual_spec_id, args.holder_session_id, args.lease_minutes)
        return {
            "acquired": renewed,
            "lock": sqlite_lock_backend.read(args.visual_spec_id),
            "error": None if renewed else "not_locked_or_not_lock_holder",
        }
    if args.command == "release":
        existing = sqlite_lock_backend.read(args.visual_spec_id)
        released = sqlite_lock_backend.release(args.visual_spec_id, args.holder_session_id)
        return {
            "acquired": released,
            "lock": existing if released else sqlite_lock_backend.read(args.visual_spec_id),
            "error": None if released else "not_locked_or_not_lock_holder",
        }
    if args.command == "read":
        return sqlite_lock_backend.read(args.visual_spec_id)
    if args.command == "bump-generation":
        generation = sqlite_lock_backend.bump_generation()
        current = sqlite_lock_backend.get_generation()
        return {"generation": generation, "last_amendment_at": current.get("last_amendment_at")}
    if args.command == "get-generation":
        return sqlite_lock_backend.get_generation()
    raise ValueError(f"unsupported command: {args.command}")


def main() -> int:
    """Run the public visual-spec lock API."""
    args = parse_args()
    try:
        vault_root = resolve_vault_root()
        backend_config = load_backend_config(vault_root)
        backend = backend_config.get("backend")
        if backend == "fcntl_excl":
            if args.command == "acquire":
                emit(fcntl_acquire(args, vault_root))
            elif args.command == "renew":
                emit(fcntl_renew(args, vault_root))
            elif args.command == "release":
                emit(fcntl_release(args, vault_root))
            elif args.command == "read":
                emit(fcntl_read(args.visual_spec_id, vault_root))
            elif args.command == "bump-generation":
                emit(fcntl_bump_generation(vault_root))
            elif args.command == "get-generation":
                emit(fcntl_get_generation(vault_root))
            return 0
        if backend == "sqlite":
            emit(sqlite_dispatch(args, vault_root))
            return 0
        return fail(f"Unsupported or missing lock backend ({backend}). Run scripts/probe_lock_backend.py.")
    except Exception as exc:
        return fail(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
