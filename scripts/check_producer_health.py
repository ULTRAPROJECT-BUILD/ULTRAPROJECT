#!/usr/bin/env python3
"""Run synthetic health checks for registered artifact producers."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from urllib import request
from urllib.error import URLError

try:
    import yaml
except ImportError as exc:  # pragma: no cover - dependency gate
    raise SystemExit("check_producer_health.py requires PyYAML. Install with: python3 -m pip install PyYAML") from exc

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import artifact_registry

HEALTH_LOG_RELATIVE = Path("config") / "artifact-producer-health-log.jsonl"
FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "v7-a" / "synthetic-producer"
IMAGE_TYPES = {"photograph", "illustration", "icon_set", "pattern_texture"}


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


def health_log_path(vault_root: Path) -> Path:
    """Return the health log path."""
    return vault_root / HEALTH_LOG_RELATIVE


def read_json_or_yaml(path: Path) -> Any:
    """Read a JSON or YAML fixture payload."""
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        return json.loads(text)
    if path.suffix.lower() in {".yaml", ".yml"}:
        return yaml.safe_load(text)
    return text


def find_fixture(producer_id: str, artifact_type: str) -> tuple[Path | None, Any]:
    """Find a producer fixture, or return an in-memory default for image producers."""
    for path in sorted(FIXTURE_DIR.glob(f"{producer_id}-fixture.*")):
        return path, read_json_or_yaml(path)
    if artifact_type in IMAGE_TYPES:
        return None, {
            "prompt": "Generate a 200x200 PNG of a flat red square on a transparent background.",
            "dimensions": "200x200",
        }
    return None, None


def fixture_to_tempfile(payload: Any) -> Path:
    """Write an in-memory fixture payload to a temporary JSON file for subprocess wrappers."""
    handle = tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", prefix="producer-fixture-", delete=False)
    with handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return Path(handle.name)


def command_from_mcp_path(mcp_path: str, fixture_path: Path, producer: dict[str, Any], artifact_type: str, medium: str) -> list[str]:
    """Build a best-effort executable command for an MCP wrapper path."""
    path = Path(mcp_path)
    if not path.is_absolute():
        path = REPO_ROOT / path
    if not path.exists():
        raise FileNotFoundError(f"mcp_path does not exist: {path}")
    if os.access(path, os.X_OK):
        command = [str(path)]
    elif path.suffix == ".py":
        command = [sys.executable, str(path)]
    elif path.suffix in {".js", ".mjs", ".cjs"}:
        command = ["node", str(path)]
    else:
        raise RuntimeError(f"mcp_path is not executable and has no known runner: {path}")
    return command + [str(fixture_path), "--artifact-type", artifact_type, "--medium", medium]


def expand_command(raw: str, fixture_path: Path, producer: dict[str, Any], artifact_type: str, medium: str) -> list[str]:
    """Expand a CLI command with fixture placeholders."""
    replacements = {
        "fixture": str(fixture_path),
        "artifact_type": artifact_type,
        "medium": medium,
        "producer_id": str(producer.get("producer_id")),
    }
    parts = [part.format(**replacements) for part in shlex.split(raw)]
    if "{fixture}" not in raw and str(fixture_path) not in parts:
        parts.append(str(fixture_path))
    return parts


def fixture_health_command(payload: Any) -> str | list[str] | None:
    """Return a fixture-provided health command, if present."""
    if isinstance(payload, dict):
        value = payload.get("health_command")
        if isinstance(value, (str, list)):
            return value
    return None


def run_subprocess_fixture(
    command: list[str],
    fixture_path: Path,
    producer: dict[str, Any],
    artifact_type: str,
    medium: str,
    timeout_seconds: int,
) -> dict[str, Any]:
    """Execute a producer subprocess fixture."""
    env = os.environ.copy()
    env.update(
        {
            "ONESHOT_PRODUCER_ID": str(producer.get("producer_id")),
            "ONESHOT_ARTIFACT_TYPE": artifact_type,
            "ONESHOT_MEDIUM": medium,
            "ONESHOT_FIXTURE_PATH": str(fixture_path),
        }
    )
    completed = subprocess.run(
        command,
        cwd=str(REPO_ROOT),
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout_seconds,
        check=False,
    )
    return {
        "status": "pass" if completed.returncode == 0 else "fail",
        "returncode": completed.returncode,
        "stdout_tail": completed.stdout[-1000:],
        "stderr_tail": completed.stderr[-1000:],
        "command": command,
    }


def run_api_fixture(
    endpoint: str,
    payload: Any,
    producer: dict[str, Any],
    artifact_type: str,
    medium: str,
    timeout_seconds: int,
) -> dict[str, Any]:
    """POST a synthetic fixture to an API producer endpoint."""
    request_payload = payload if isinstance(payload, dict) else {"prompt": str(payload)}
    request_payload = {
        **request_payload,
        "producer_id": producer.get("producer_id"),
        "artifact_type": artifact_type,
        "medium": medium,
        "synthetic_fixture": True,
    }
    body = json.dumps(request_payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    api_key_env = producer.get("api_key_env_var")
    if api_key_env and os.environ.get(str(api_key_env)):
        headers["Authorization"] = f"Bearer {os.environ[str(api_key_env)]}"
    req = request.Request(endpoint, data=body, headers=headers, method="POST")
    try:
        with request.urlopen(req, timeout=timeout_seconds) as response:
            response_body = response.read(1000).decode("utf-8", errors="replace")
            return {
                "status": "pass" if 200 <= response.status < 300 else "fail",
                "http_status": response.status,
                "response_tail": response_body,
            }
    except URLError as exc:
        return {"status": "fail", "error": str(exc)}


def invoke_fixture(
    producer: dict[str, Any],
    fixture_path: Path | None,
    fixture_payload: Any,
    artifact_type: str,
    medium: str,
    timeout_seconds: int,
) -> dict[str, Any]:
    """Invoke one synthetic fixture for a producer and medium."""
    temp_path: Path | None = None
    if fixture_payload is None:
        return {"status": "fail", "error": "missing synthetic fixture"}
    if fixture_path is None:
        temp_path = fixture_to_tempfile(fixture_payload)
        fixture_path = temp_path
    try:
        custom = fixture_health_command(fixture_payload)
        if custom:
            if isinstance(custom, str):
                command = expand_command(custom, fixture_path, producer, artifact_type, medium)
            else:
                raw = " ".join(shlex.quote(str(part)) for part in custom)
                command = expand_command(raw, fixture_path, producer, artifact_type, medium)
            return run_subprocess_fixture(command, fixture_path, producer, artifact_type, medium, timeout_seconds)
        if producer.get("cli_command"):
            command = expand_command(str(producer["cli_command"]), fixture_path, producer, artifact_type, medium)
            return run_subprocess_fixture(command, fixture_path, producer, artifact_type, medium, timeout_seconds)
        if producer.get("mcp_path"):
            command = command_from_mcp_path(str(producer["mcp_path"]), fixture_path, producer, artifact_type, medium)
            return run_subprocess_fixture(command, fixture_path, producer, artifact_type, medium, timeout_seconds)
        if producer.get("api_endpoint"):
            return run_api_fixture(str(producer["api_endpoint"]), fixture_payload, producer, artifact_type, medium, timeout_seconds)
        return {"status": "fail", "error": "producer has no invocation method"}
    except subprocess.TimeoutExpired as exc:
        return {"status": "fail", "error": f"fixture timed out after {exc.timeout}s"}
    except Exception as exc:
        return {"status": "fail", "error": str(exc)}
    finally:
        if temp_path is not None:
            try:
                temp_path.unlink()
            except FileNotFoundError:
                pass


def load_history(vault_root: Path) -> list[dict[str, Any]]:
    """Read historical producer health events."""
    path = health_log_path(vault_root)
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            records.append(payload)
    return records


def append_history(vault_root: Path, records: list[dict[str, Any]]) -> None:
    """Append health records to the JSONL log."""
    if not records:
        return
    path = health_log_path(vault_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    artifact_registry.fsync_parent(path)


def success_rate(history: list[dict[str, Any]], producer_id: str, days: int) -> float:
    """Calculate a rolling success rate."""
    cutoff = now_dt() - timedelta(days=days)
    scoped = []
    for item in history:
        if item.get("producer_id") != producer_id:
            continue
        parsed = parse_datetime(item.get("timestamp"))
        if parsed is not None and parsed >= cutoff:
            scoped.append(item)
    if not scoped:
        return 0.0
    passed = sum(1 for item in scoped if item.get("status") == "pass")
    return round(passed / len(scoped), 4)


def consecutive_failures(history: list[dict[str, Any]], producer_id: str) -> int:
    """Count most recent consecutive failures."""
    scoped = [item for item in history if item.get("producer_id") == producer_id]
    count = 0
    for item in reversed(scoped):
        if item.get("status") == "fail":
            count += 1
            continue
        break
    return count


def recent_successes(history: list[dict[str, Any]], producer_id: str) -> int:
    """Count most recent consecutive successful fixture invocations."""
    scoped = [item for item in history if item.get("producer_id") == producer_id]
    count = 0
    for item in reversed(scoped):
        if item.get("status") == "pass":
            count += 1
            continue
        break
    return count


def create_repair_ticket(vault_root: Path, producer_id: str, reason: str) -> str:
    """Create a producer repair ticket if one does not already exist."""
    date = now_dt().strftime("%Y-%m-%d")
    ticket_dir = vault_root / "projects" / "repair-tickets"
    ticket_dir.mkdir(parents=True, exist_ok=True)
    path = ticket_dir / f"producer-{producer_id}-{date}.md"
    if not path.exists():
        text = (
            "---\n"
            "type: producer-repair-ticket\n"
            f"producer_id: {producer_id}\n"
            f"created_at: {now_iso()}\n"
            "status: open\n"
            "---\n\n"
            f"# Repair producer `{producer_id}`\n\n"
            f"Reason: {reason}\n"
        )
        artifact_registry.atomic_write_text(path, text)
    return str(path)


def check_one_producer(
    producer: dict[str, Any],
    vault_root: Path,
    auto_quarantine: bool,
    auto_repair_ticket: bool,
    timeout_seconds: int,
) -> dict[str, Any]:
    """Run all synthetic fixture checks for one producer."""
    producer_id = str(producer["producer_id"])
    artifact_type = str(producer["artifact_types"][0])
    fixture_path, fixture_payload = find_fixture(producer_id, artifact_type)
    timestamp = now_iso()
    medium_results: list[dict[str, Any]] = []
    for medium in producer.get("applicable_mediums", []):
        result = invoke_fixture(producer, fixture_path, fixture_payload, artifact_type, str(medium), timeout_seconds)
        medium_results.append(
            {
                "timestamp": timestamp,
                "producer_id": producer_id,
                "artifact_type": artifact_type,
                "medium": str(medium),
                "status": result.get("status", "fail"),
                "detail": result,
            }
        )

    if not medium_results:
        medium_results.append(
            {
                "timestamp": timestamp,
                "producer_id": producer_id,
                "artifact_type": artifact_type,
                "medium": "",
                "status": "fail",
                "detail": {"error": "producer has no applicable_mediums"},
            }
        )
    append_history(vault_root, medium_results)
    history = load_history(vault_root)
    rate_30 = success_rate(history, producer_id, 30)
    rate_90 = success_rate(history, producer_id, 90)
    failures = consecutive_failures(history, producer_id)
    successes = recent_successes(history, producer_id)
    overall_status = "pass" if all(item["status"] == "pass" for item in medium_results) else "fail"

    metrics = {
        "last_synthetic_fixture_status": overall_status,
        "rolling_success_rate_30d": rate_30,
        "rolling_success_rate_90d": rate_90,
        "total_invocations": int(producer.get("total_invocations", 0)) + len(medium_results),
    }
    if overall_status == "pass":
        metrics["last_synthetic_fixture_pass"] = timestamp
    metrics_update = artifact_registry.update_producer_metrics(producer_id, metrics)

    state_transition = None
    repair_ticket = None
    current_state = str(producer.get("state"))
    if current_state == "pending" and successes >= 3:
        state_transition = artifact_registry.update_producer_state(
            producer_id,
            "active",
            "promoted after at least three successful synthetic fixture invocations",
        )
    elif auto_quarantine and current_state in {"active", "repaired_active"} and (failures >= 2 or rate_30 < 0.5):
        reason = f"synthetic health check failed policy: consecutive_failures={failures}, rolling_success_rate_30d={rate_30}"
        state_transition = artifact_registry.update_producer_state(producer_id, "quarantined", reason)
        if auto_repair_ticket:
            repair_ticket = create_repair_ticket(vault_root, producer_id, reason)
    elif auto_repair_ticket and current_state == "quarantined":
        repair_ticket = create_repair_ticket(vault_root, producer_id, "producer remains quarantined")

    return {
        "producer_id": producer_id,
        "artifact_type": artifact_type,
        "fixture_path": str(fixture_path) if fixture_path else "default:image_red_square_200x200",
        "status": overall_status,
        "medium_results": medium_results,
        "metrics": metrics,
        "metrics_update": metrics_update,
        "consecutive_failures": failures,
        "recent_successes": successes,
        "state_transition": state_transition,
        "repair_ticket": repair_ticket,
    }


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--producer-id")
    parser.add_argument("--auto-quarantine", action="store_true")
    parser.add_argument("--auto-repair-ticket", action="store_true")
    parser.add_argument("--json-out")
    parser.add_argument("--timeout-seconds", type=int, default=120)
    parser.add_argument("--vault-root")
    return parser.parse_args()


def write_output(payload: dict[str, Any], json_out: str | None) -> None:
    """Write JSON output to stdout and optional file."""
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if json_out:
        out_path = Path(json_out).expanduser()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text, encoding="utf-8")
    sys.stdout.write(text)


def main() -> int:
    """Run producer health checks."""
    args = parse_args()
    if args.vault_root:
        os.environ["ONESHOT_VAULT_ROOT"] = str(Path(args.vault_root).expanduser().resolve())
    try:
        vault_root = artifact_registry.resolve_vault_root()
        if args.producer_id:
            producer = artifact_registry.get_producer(args.producer_id)
            selected = [producer] if producer else []
        else:
            selected = artifact_registry.producers(artifact_registry.read_registry())
        results = [
            check_one_producer(item, vault_root, args.auto_quarantine, args.auto_repair_ticket, args.timeout_seconds)
            for item in selected
        ]
        payload = {"checked_at": now_iso(), "producer_count": len(selected), "results": results}
        write_output(payload, args.json_out)
        return 1 if any(item["status"] == "fail" for item in results) else 0
    except Exception as exc:
        payload = {"checked_at": now_iso(), "error": str(exc), "ok": False}
        write_output(payload, args.json_out)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
