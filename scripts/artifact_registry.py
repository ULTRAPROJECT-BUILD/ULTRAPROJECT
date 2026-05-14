#!/usr/bin/env python3
"""Registry interface for V7-A artifact producers."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import shlex
import sys
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Generator

try:
    import yaml
except ImportError as exc:  # pragma: no cover - dependency gate
    raise SystemExit("artifact_registry.py requires PyYAML. Install with: python3 -m pip install PyYAML") from exc

try:
    import jsonschema
except ImportError as exc:  # pragma: no cover - dependency gate
    raise SystemExit("artifact_registry.py requires jsonschema. Install with: python3 -m pip install jsonschema") from exc

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
REGISTRY_RELATIVE = Path("config") / "artifact-producers.md"
STATE_LOG_RELATIVE = Path("config") / "artifact-producer-state-log.md"
PRODUCER_SCHEMA = REPO_ROOT / "schemas" / "artifact-producer.schema.json"
PRODUCER_ID_RE = re.compile(r"^[a-z][a-z0-9_]*$")
ACTIVE_STATES = {"active", "repaired_active"}
TERMINAL_STATES = {"deprecated"}
ALLOWED_TRANSITIONS = {
    ("pending", "active"),
    ("pending", "failed"),
    ("active", "quarantined"),
    ("quarantined", "repaired_active"),
    ("quarantined", "failed"),
    ("repaired_active", "quarantined"),
}


class RegistryError(RuntimeError):
    """Base registry error."""


class RegistryConflict(RegistryError):
    """Raised when a registry compare-and-swap conflict persists."""


def now_local_iso(timespec: str = "seconds") -> str:
    """Return machine-local ISO time with timezone offset."""
    return datetime.now().astimezone().isoformat(timespec=timespec)


def resolve_vault_root(raw: str | None = None) -> Path:
    """Resolve the vault root from an override, environment, script location, or cwd."""
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


def registry_path(vault_root: Path | None = None) -> Path:
    """Return the artifact producer registry path."""
    root = vault_root or resolve_vault_root()
    return root / REGISTRY_RELATIVE


def state_log_path(vault_root: Path | None = None) -> Path:
    """Return the artifact producer state log path."""
    root = vault_root or resolve_vault_root()
    return root / STATE_LOG_RELATIVE


def lock_dir(vault_root: Path | None = None) -> Path:
    """Return the artifact producer lock directory."""
    root = vault_root or resolve_vault_root()
    path = root / "locks" / "artifact-producers"
    path.mkdir(parents=True, exist_ok=True)
    return path


def validate_producer_id(producer_id: str) -> None:
    """Validate a producer ID before using it in paths."""
    if not PRODUCER_ID_RE.fullmatch(producer_id):
        raise ValueError(f"invalid producer_id {producer_id!r}; expected {PRODUCER_ID_RE.pattern}")


def producer_lock_path(producer_id: str, vault_root: Path | None = None) -> Path:
    """Return the per-producer lock path."""
    validate_producer_id(producer_id)
    return lock_dir(vault_root) / f"{producer_id}.lock"


def registry_guard_path(vault_root: Path | None = None) -> Path:
    """Return the short-lived registry CAS guard path."""
    return lock_dir(vault_root) / "_registry-cas.lock"


def fsync_parent(path: Path) -> None:
    """Best-effort fsync of a directory after atomic updates."""
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


def atomic_write_text(path: Path, text: str) -> None:
    """Atomically write text to path via a unique temporary file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f"{path.name}.tmp-{os.getpid()}-{time.monotonic_ns()}")
    with tmp_path.open("w", encoding="utf-8") as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp_path, path)
    fsync_parent(path)


def split_frontmatter(text: str, path: Path) -> tuple[dict[str, Any], str]:
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
    frontmatter = yaml.safe_load("".join(lines[1:closing_index])) or {}
    if not isinstance(frontmatter, dict):
        raise ValueError(f"{path} frontmatter is not a mapping")
    return frontmatter, "".join(lines[closing_index + 1 :])


def extract_registry_yaml(body: str) -> dict[str, Any]:
    """Extract the fenced YAML registry body."""
    for match in re.finditer(r"```ya?ml\s*\n(.*?)\n```", body, flags=re.DOTALL | re.IGNORECASE):
        loaded = yaml.safe_load(match.group(1)) or {}
        if isinstance(loaded, dict) and "producers" in loaded:
            producers = loaded.get("producers")
            if producers is None:
                loaded["producers"] = []
            if not isinstance(loaded["producers"], list):
                raise ValueError("artifact producer registry YAML has non-list producers")
            return loaded
    loaded = yaml.safe_load(body) or {}
    if isinstance(loaded, dict) and "producers" in loaded:
        producers = loaded.get("producers")
        if producers is None:
            loaded["producers"] = []
        if not isinstance(loaded["producers"], list):
            raise ValueError("artifact producer registry YAML has non-list producers")
        return loaded
    raise ValueError("artifact producer registry body must contain a fenced YAML block with producers")


def load_registry_document(vault_root: Path | None = None) -> dict[str, Any]:
    """Read the registry document with metadata, registry data, and revision hash."""
    path = registry_path(vault_root)
    if not path.exists():
        raise FileNotFoundError(f"{path} is missing")
    text = path.read_text(encoding="utf-8")
    frontmatter, body = split_frontmatter(text, path)
    registry = extract_registry_yaml(body)
    return {
        "path": path,
        "text": text,
        "frontmatter": frontmatter,
        "registry": registry,
        "last_updated": str(frontmatter.get("last_updated") or ""),
        "content_hash": hashlib.sha256(text.encode("utf-8")).hexdigest(),
    }


def read_registry() -> dict[str, Any]:
    """Parse vault/config/artifact-producers.md's YAML body."""
    return copy.deepcopy(load_registry_document()["registry"])


def dump_frontmatter(frontmatter: dict[str, Any]) -> str:
    """Render frontmatter deterministically."""
    rendered = yaml.safe_dump(frontmatter, sort_keys=False, allow_unicode=True).strip()
    return f"---\n{rendered}\n---\n"


def dump_registry_yaml(registry: dict[str, Any]) -> str:
    """Render the producer registry YAML block."""
    return yaml.safe_dump(registry, sort_keys=False, allow_unicode=True).strip()


def render_registry_document(frontmatter: dict[str, Any], registry: dict[str, Any]) -> str:
    """Render the full markdown registry document."""
    producers = registry.get("producers") or []
    producer_note = "(none registered — operator registers as needed)" if not producers else f"({len(producers)} registered)"
    return (
        f"{dump_frontmatter(frontmatter)}\n"
        "# Artifact Producers Registry\n\n"
        "This is the central registry of artifact producers (image-gen, 3D, video, audio, etc.) "
        "that can satisfy artifact requests from Visual Specifications.\n\n"
        "Each producer is operator-registered manually OR via the existing source-capability flow. "
        "V7-A does NOT auto-bootstrap producers; that's V7-B (deferred).\n\n"
        "## Producers\n\n"
        f"{producer_note}\n\n"
        "```yaml\n"
        f"{dump_registry_yaml({'producers': producers})}\n"
        "```\n\n"
        "## Adding a producer\n\n"
        "Use the `register-artifact-producer` skill. The skill handles concurrent registration safety, "
        "schema validation, lifecycle state assignment, and synthetic fixture testing before promoting "
        "from `pending` to `active`.\n\n"
        "## Lifecycle states\n\n"
        "- `pending`: just registered; needs ≥3 successful synthetic-fixture invocations to promote to `active`\n"
        "- `active`: in production use; rolling success rate ≥80% and last fixture <14 days old\n"
        "- `repaired_active`: previously quarantined; operator confirmed repair; back to active\n"
        "- `quarantined`: 2 consecutive failures or success rate <50%; fallback chain takes over; repair ticket created\n"
        "- `failed`: terminal failure; superseded by replacement\n"
        "- `deprecated`: replaced by newer producer (`canonical_replaces` field on successor points back)\n"
    )


def producer_schema() -> dict[str, Any]:
    """Load the producer schema."""
    return json.loads(PRODUCER_SCHEMA.read_text(encoding="utf-8"))


def validate_producer_record(record: dict[str, Any]) -> None:
    """Validate a producer record against schemas/artifact-producer.schema.json."""
    schema = producer_schema()
    validator = jsonschema.Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(record), key=lambda error: list(error.path))
    if errors:
        details = "; ".join(f"{'/'.join(map(str, error.path)) or '/'}: {error.message}" for error in errors)
        raise ValueError(f"artifact producer schema validation failed: {details}")


def normalize_json(value: Any) -> str:
    """Return a stable JSON representation for idempotency comparisons."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def producers(registry: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the registry producer list."""
    value = registry.get("producers", [])
    if not isinstance(value, list):
        raise ValueError("registry producers field is not a list")
    return value


def find_producer(registry: dict[str, Any], producer_id: str) -> dict[str, Any] | None:
    """Find a producer by ID in a registry mapping."""
    for producer in producers(registry):
        if producer.get("producer_id") == producer_id:
            return producer
    return None


def get_producer(producer_id: str) -> dict[str, Any] | None:
    """Return a producer by ID, if registered."""
    validate_producer_id(producer_id)
    producer = find_producer(read_registry(), producer_id)
    return copy.deepcopy(producer) if producer else None


def list_producers_by_state(state: str) -> list[dict[str, Any]]:
    """Return all producers in a lifecycle state."""
    return [copy.deepcopy(item) for item in producers(read_registry()) if item.get("state") == state]


def producer_supports(producer: dict[str, Any], artifact_type: str, medium: str | None) -> bool:
    """Return whether a producer supports an artifact type and optional medium."""
    if artifact_type not in producer.get("artifact_types", []):
        return False
    if medium is not None and medium not in producer.get("applicable_mediums", []):
        return False
    return producer.get("state") in ACTIVE_STATES


def resolve_producer(artifact_type: str, medium: str | None = None) -> dict[str, Any] | None:
    """Find the first active producer that handles an artifact type for an optional medium."""
    for producer in producers(read_registry()):
        if producer_supports(producer, artifact_type, medium):
            return copy.deepcopy(producer)
    return None


def resolve_producer_with_fallback(
    artifact_type: str,
    medium: str | None,
    exclude_ids: set[str] | None = None,
) -> Generator[dict[str, Any], None, None]:
    """Yield compatible producers in primary-then-fallback order."""
    excluded = set(exclude_ids or set())
    registry = read_registry()
    by_id = {str(item.get("producer_id")): item for item in producers(registry)}
    primary = None
    for producer in producers(registry):
        producer_id = str(producer.get("producer_id"))
        if producer_id in excluded:
            continue
        if producer_supports(producer, artifact_type, medium):
            primary = producer
            break
    if primary is None:
        return

    yielded: set[str] = set()
    queue = [primary]
    while queue:
        current = queue.pop(0)
        current_id = str(current.get("producer_id"))
        if current_id in yielded or current_id in excluded:
            continue
        if producer_supports(current, artifact_type, medium):
            yielded.add(current_id)
            yield copy.deepcopy(current)
            for fallback_id in current.get("fallback_chain", []):
                fallback = by_id.get(str(fallback_id))
                if fallback is not None:
                    queue.append(fallback)


def acquire_exclusive_file(path: Path, payload: dict[str, Any], timeout_seconds: float = 10.0) -> int:
    """Acquire an O_EXCL lock file, waiting briefly for short-lived guards."""
    deadline = time.monotonic() + timeout_seconds
    while True:
        try:
            fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
            os.write(fd, (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8"))
            os.fsync(fd)
            fsync_parent(path)
            return fd
        except FileExistsError:
            if time.monotonic() >= deadline:
                raise TimeoutError(f"timed out waiting for lock {path}")
            time.sleep(0.05)


def release_exclusive_file(path: Path, fd: int) -> None:
    """Release an O_EXCL lock file."""
    try:
        os.close(fd)
    finally:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        fsync_parent(path)


@contextmanager
def producer_lock(producer_id: str, vault_root: Path | None = None) -> Generator[dict[str, Any], None, None]:
    """Acquire and release a per-producer registration lock."""
    root = vault_root or resolve_vault_root()
    path = producer_lock_path(producer_id, root)
    acquired_at = datetime.now().astimezone()
    session_id = f"artifact-registry-{os.getpid()}-{uuid.uuid4()}"
    payload = {
        "producer_id": producer_id,
        "holder_agent": "artifact_registry.py",
        "holder_pid": os.getpid(),
        "holder_session_id": session_id,
        "acquired_at": acquired_at.isoformat(timespec="seconds"),
        "lease_expires_at": (acquired_at + timedelta(minutes=5)).isoformat(timespec="seconds"),
    }
    fd = acquire_exclusive_file(path, payload, timeout_seconds=0.1)
    try:
        yield payload
    finally:
        release_exclusive_file(path, fd)


@contextmanager
def registry_cas_guard(vault_root: Path | None = None) -> Generator[None, None, None]:
    """Acquire and release the short-lived registry CAS guard."""
    root = vault_root or resolve_vault_root()
    path = registry_guard_path(root)
    payload = {
        "guard": "artifact-producers-registry-cas",
        "holder_pid": os.getpid(),
        "holder_session_id": f"registry-cas-{os.getpid()}-{uuid.uuid4()}",
        "acquired_at": now_local_iso(),
        "lease_expires_at": (datetime.now().astimezone() + timedelta(minutes=1)).isoformat(timespec="seconds"),
    }
    fd = acquire_exclusive_file(path, payload, timeout_seconds=10.0)
    try:
        yield
    finally:
        release_exclusive_file(path, fd)


def write_registry_from_document(document: dict[str, Any], vault_root: Path | None = None) -> None:
    """Write a loaded registry document after mutation."""
    path = registry_path(vault_root)
    text = render_registry_document(document["frontmatter"], document["registry"])
    atomic_write_text(path, text)


def cas_write_registry(
    before: dict[str, Any],
    after: dict[str, Any],
    vault_root: Path | None = None,
) -> bool:
    """Compare-and-swap the registry document under the registry guard."""
    root = vault_root or resolve_vault_root()
    with registry_cas_guard(root):
        current = load_registry_document(root)
        same_revision = (
            current["last_updated"] == before["last_updated"]
            and current["content_hash"] == before["content_hash"]
        )
        if not same_revision:
            return False
        write_registry_from_document(after, root)
        return True


def register_producer_atomic(producer_record: dict[str, Any]) -> dict[str, Any]:
    """Register a producer with per-producer locking and registry CAS."""
    producer_id = str(producer_record.get("producer_id") or "")
    validate_producer_id(producer_id)
    validate_producer_record(producer_record)
    root = resolve_vault_root()

    with producer_lock(producer_id, root):
        conflicts: list[dict[str, Any]] = []
        for attempt in (1, 2):
            before = load_registry_document(root)
            registry = copy.deepcopy(before["registry"])
            existing = find_producer(registry, producer_id)
            if existing is not None:
                if normalize_json(existing) == normalize_json(producer_record):
                    return {
                        "status": "no_op",
                        "producer_id": producer_id,
                        "attempt": attempt,
                        "reason": "identical producer already registered",
                    }
                raise RegistryConflict(f"producer_id {producer_id!r} already exists with a different record")

            registry.setdefault("producers", []).append(copy.deepcopy(producer_record))
            after = copy.deepcopy(before)
            after["registry"] = registry
            after["frontmatter"] = copy.deepcopy(before["frontmatter"])
            after["frontmatter"]["last_updated"] = now_local_iso(timespec="minutes")
            if cas_write_registry(before, after, root):
                return {
                    "status": "registered",
                    "producer_id": producer_id,
                    "attempt": attempt,
                    "last_updated": after["frontmatter"]["last_updated"],
                }
            conflicts.append(
                {
                    "attempt": attempt,
                    "expected_last_updated": before["last_updated"],
                    "expected_hash": before["content_hash"],
                }
            )
        raise RegistryConflict(
            "artifact producer registry changed during registration; retry exhausted. "
            f"conflicts={json.dumps(conflicts, sort_keys=True)}"
        )


def transition_allowed(old_state: str, new_state: str) -> bool:
    """Return whether a lifecycle transition is allowed."""
    if old_state == new_state:
        return True
    if old_state in TERMINAL_STATES:
        return False
    if new_state == "deprecated":
        return True
    return (old_state, new_state) in ALLOWED_TRANSITIONS


def append_state_log(
    producer_id: str,
    old_state: str,
    new_state: str,
    reason: str,
    changed_at: str,
    vault_root: Path | None = None,
) -> None:
    """Append one lifecycle event to the markdown state log."""
    path = state_log_path(vault_root)
    if not path.exists():
        atomic_write_text(
            path,
            "---\ntype: artifact-producer-state-log\nversion: 1\n"
            f"created_at: {now_local_iso(timespec='minutes')}\nschema_version: 1\n---\n\n"
            "# Artifact Producer State Log\n\n",
        )
    entry = (
        f"\n## {changed_at} — {producer_id}\n\n"
        "```yaml\n"
        f"producer_id: {producer_id}\n"
        f"old_state: {old_state}\n"
        f"new_state: {new_state}\n"
        f"reason: {json.dumps(reason)}\n"
        f"changed_at: {changed_at}\n"
        "```\n"
    )
    with path.open("a", encoding="utf-8") as handle:
        handle.write(entry)
        handle.flush()
        os.fsync(handle.fileno())
    fsync_parent(path)


def mutate_producer_atomic(
    producer_id: str,
    mutator: Callable[[dict[str, Any]], tuple[dict[str, Any], dict[str, Any]]],
) -> dict[str, Any]:
    """Apply a producer-record mutation under lock and registry CAS."""
    validate_producer_id(producer_id)
    root = resolve_vault_root()
    with producer_lock(producer_id, root):
        conflicts: list[dict[str, Any]] = []
        for attempt in (1, 2):
            before = load_registry_document(root)
            registry = copy.deepcopy(before["registry"])
            producer_list = producers(registry)
            index = next((idx for idx, item in enumerate(producer_list) if item.get("producer_id") == producer_id), None)
            if index is None:
                raise KeyError(f"producer_id {producer_id!r} is not registered")
            original = copy.deepcopy(producer_list[index])
            updated, result = mutator(copy.deepcopy(original))
            validate_producer_record(updated)
            producer_list[index] = updated
            after = copy.deepcopy(before)
            after["registry"] = registry
            after["frontmatter"] = copy.deepcopy(before["frontmatter"])
            after["frontmatter"]["last_updated"] = now_local_iso(timespec="minutes")
            if cas_write_registry(before, after, root):
                result.update(
                    {
                        "producer_id": producer_id,
                        "attempt": attempt,
                        "last_updated": after["frontmatter"]["last_updated"],
                    }
                )
                return result
            conflicts.append(
                {
                    "attempt": attempt,
                    "expected_last_updated": before["last_updated"],
                    "expected_hash": before["content_hash"],
                }
            )
        raise RegistryConflict(
            "artifact producer registry changed during producer update; retry exhausted. "
            f"conflicts={json.dumps(conflicts, sort_keys=True)}"
        )


def update_producer_state(producer_id: str, new_state: str, reason: str) -> dict[str, Any]:
    """Enforce a lifecycle transition and append it to the state log."""
    if new_state not in {"pending", "active", "repaired_active", "quarantined", "failed", "deprecated"}:
        raise ValueError(f"unsupported state {new_state!r}")
    if not reason.strip():
        raise ValueError("state transition reason is required")

    event: dict[str, Any] = {}

    def mutator(record: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        old_state = str(record.get("state") or "")
        if not transition_allowed(old_state, new_state):
            raise ValueError(f"forbidden state transition {old_state} -> {new_state}")
        if old_state == new_state:
            return record, {"status": "no_op", "old_state": old_state, "new_state": new_state}
        changed_at = now_local_iso()
        record["state"] = new_state
        record["state_changed_at"] = changed_at
        record["state_change_reason"] = reason
        event.update(
            {
                "producer_id": producer_id,
                "old_state": old_state,
                "new_state": new_state,
                "reason": reason,
                "changed_at": changed_at,
            }
        )
        return record, {"status": "updated", "old_state": old_state, "new_state": new_state, "changed_at": changed_at}

    result = mutate_producer_atomic(producer_id, mutator)
    if event:
        append_state_log(
            event["producer_id"],
            event["old_state"],
            event["new_state"],
            event["reason"],
            event["changed_at"],
        )
    return result


def update_producer_metrics(producer_id: str, metrics: dict[str, Any]) -> dict[str, Any]:
    """Update health telemetry fields on a producer record."""
    allowed = {
        "last_synthetic_fixture_pass",
        "last_synthetic_fixture_status",
        "rolling_success_rate_30d",
        "rolling_success_rate_90d",
        "total_invocations",
    }
    extra = sorted(set(metrics) - allowed)
    if extra:
        raise ValueError(f"unsupported producer metric fields: {', '.join(extra)}")

    def mutator(record: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        record.update(metrics)
        return record, {"status": "updated", "updated_fields": sorted(metrics)}

    return mutate_producer_atomic(producer_id, mutator)


def emit(payload: Any) -> None:
    """Emit structured JSON."""
    print(json.dumps(payload, indent=2, sort_keys=True))


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vault-root", help="Optional vault root override.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list")
    list_parser.add_argument("--state")

    resolve_parser = subparsers.add_parser("resolve")
    resolve_parser.add_argument("--artifact-type", required=True)
    resolve_parser.add_argument("--medium")

    register_parser = subparsers.add_parser("register")
    register_parser.add_argument("--record-json", required=True)

    state_parser = subparsers.add_parser("state")
    state_parser.add_argument("--producer-id", required=True)
    state_parser.add_argument("--state", required=True)
    state_parser.add_argument("--reason", required=True)

    get_parser = subparsers.add_parser("get")
    get_parser.add_argument("--producer-id", required=True)

    return parser.parse_args()


def main() -> int:
    """Run the artifact registry CLI."""
    args = parse_args()
    if args.vault_root:
        os.environ["ONESHOT_VAULT_ROOT"] = str(Path(args.vault_root).expanduser().resolve())
    try:
        if args.command == "list":
            items = list_producers_by_state(args.state) if args.state else producers(read_registry())
            emit({"producers": items, "count": len(items)})
            return 0
        if args.command == "resolve":
            producer = resolve_producer(args.artifact_type, args.medium)
            emit(
                {
                    "found": producer is not None,
                    "producer": producer,
                    "message": None
                    if producer is not None
                    else f"no active producer found for artifact_type={shlex.quote(args.artifact_type)}",
                }
            )
            return 0
        if args.command == "register":
            record_path = Path(args.record_json).expanduser()
            record = json.loads(record_path.read_text(encoding="utf-8"))
            if not isinstance(record, dict):
                raise ValueError("--record-json must contain a JSON object")
            emit(register_producer_atomic(record))
            return 0
        if args.command == "state":
            emit(update_producer_state(args.producer_id, args.state, args.reason))
            return 0
        if args.command == "get":
            producer = get_producer(args.producer_id)
            emit({"found": producer is not None, "producer": producer})
            return 0
        raise ValueError(f"unsupported command {args.command!r}")
    except Exception as exc:
        emit({"error": str(exc), "ok": False})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
