#!/usr/bin/env python3
"""Run producer-medium-slot remediation after a slot integration failure."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib import request
from urllib.error import URLError

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import artifact_registry
import check_slot_integration

INCOMPATIBILITY_LOG_RELATIVE = Path("config") / "producer-slot-incompatibility-log.md"
ACTIVE_STATES = {"active", "repaired_active"}


def now_iso(timespec: str = "seconds") -> str:
    """Return a machine-local timestamp."""
    return datetime.now().astimezone().isoformat(timespec=timespec)


def date_text() -> str:
    """Return a local calendar date."""
    return datetime.now().astimezone().strftime("%Y-%m-%d")


def read_json(path: Path) -> Any:
    """Read JSON from a path."""
    return json.loads(path.expanduser().read_text(encoding="utf-8"))


def write_json(payload: dict[str, Any], json_out: str | None) -> None:
    """Write report JSON to stdout and optionally to a file."""
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if json_out:
        out_path = Path(json_out).expanduser()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text, encoding="utf-8")
    sys.stdout.write(text)


def parse_bool(value: str) -> bool:
    """Parse CLI boolean strings."""
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "y"}:
        return True
    if normalized in {"0", "false", "no", "n"}:
        return False
    raise argparse.ArgumentTypeError(f"expected true/false, got {value!r}")


def get_slot_contract(path: Path) -> dict[str, Any]:
    """Load a slot contract file."""
    return check_slot_integration.extract_slot_contract(read_json(path))


def get_producer_or_raise(producer_id: str) -> dict[str, Any]:
    """Fetch a producer record from the registry."""
    producer = artifact_registry.get_producer(producer_id)
    if producer is None:
        raise KeyError(f"producer_id {producer_id!r} is not registered")
    return producer


def producer_active(producer: dict[str, Any]) -> bool:
    """Return whether a producer may be invoked for production."""
    return str(producer.get("state")) in ACTIVE_STATES


def artifact_type_for(producer: dict[str, Any], explicit: str | None = None) -> str:
    """Resolve an artifact type for a producer invocation."""
    if explicit:
        return explicit
    artifact_types = producer.get("artifact_types") or []
    if not artifact_types:
        raise ValueError(f"producer {producer.get('producer_id')} has no artifact_types")
    return str(artifact_types[0])


def augment_prompt(original_prompt: str, slot_contract: dict[str, Any], attempt_number: int, previous_reason: str | None) -> str:
    """Append medium-owned slot constraints to a producer prompt."""
    strict = ""
    if attempt_number > 1:
        strict = (
            "\nStrict remediation pass: satisfy the slot contract exactly. "
            "Prioritize fit over stylistic variation."
        )
    if previous_reason:
        strict += f"\nPrevious slot integration failure: {previous_reason}"
    constraints = json.dumps(slot_contract, sort_keys=True)
    return f"{original_prompt.rstrip()}\n\nSlot integration constraints:\n{constraints}{strict}\n"


def work_dir_for(args: argparse.Namespace) -> Path:
    """Choose a durable work directory for generated remediation artifacts."""
    if args.work_dir:
        path = Path(args.work_dir).expanduser()
    elif args.json_out:
        path = Path(args.json_out).expanduser().parent / f"{args.artifact_id}-slot-remediation-artifacts"
    else:
        path = Path(tempfile.mkdtemp(prefix=f"{args.artifact_id}-slot-remediation-"))
    path.mkdir(parents=True, exist_ok=True)
    return path


def request_payload(
    artifact_id: str,
    producer: dict[str, Any],
    artifact_type: str,
    slot_contract: dict[str, Any],
    prompt: str,
    attempt_number: int,
    attempt_type: str,
    output_dir: Path,
) -> dict[str, Any]:
    """Build the producer invocation request."""
    return {
        "artifact_id": artifact_id,
        "producer_id": producer.get("producer_id"),
        "artifact_type": artifact_type,
        "medium": slot_contract.get("medium"),
        "slot_role": slot_contract.get("slot_role"),
        "slot_contract": slot_contract,
        "prompt": prompt,
        "attempt_number": attempt_number,
        "attempt_type": attempt_type,
        "output_dir": str(output_dir),
    }


def expand_command(raw: str, request_path: Path, payload: dict[str, Any], producer: dict[str, Any]) -> list[str]:
    """Expand a registry cli_command with remediation placeholders."""
    replacements = {
        "request": str(request_path),
        "prompt": str(payload.get("prompt") or ""),
        "artifact_id": str(payload.get("artifact_id") or ""),
        "producer_id": str(producer.get("producer_id") or ""),
        "artifact_type": str(payload.get("artifact_type") or ""),
        "medium": str(payload.get("medium") or ""),
        "slot_role": str(payload.get("slot_role") or ""),
        "output_dir": str(payload.get("output_dir") or ""),
    }
    command = [part.format(**replacements) for part in shlex.split(raw)]
    if "{request}" not in raw and str(request_path) not in command:
        command.append(str(request_path))
    return command


def mcp_command(mcp_path: str, request_path: Path) -> list[str]:
    """Build a best-effort command for an MCP wrapper."""
    path = Path(mcp_path).expanduser()
    if not path.is_absolute():
        path = REPO_ROOT / path
    if not path.exists():
        raise FileNotFoundError(f"mcp_path does not exist: {path}")
    if os.access(path, os.X_OK):
        return [str(path), str(request_path)]
    if path.suffix == ".py":
        return [sys.executable, str(path), str(request_path)]
    if path.suffix in {".js", ".mjs", ".cjs"}:
        return ["node", str(path), str(request_path)]
    raise RuntimeError(f"mcp_path is not executable and has no known runner: {path}")


def parse_producer_stdout(stdout: str) -> dict[str, Any]:
    """Parse a producer JSON response, tolerating log lines before the JSON."""
    stripped = stdout.strip()
    if not stripped:
        return {}
    try:
        loaded = json.loads(stripped)
    except json.JSONDecodeError:
        for line in reversed(stripped.splitlines()):
            try:
                loaded = json.loads(line)
                break
            except json.JSONDecodeError:
                continue
        else:
            raise ValueError("producer stdout did not contain JSON")
    if not isinstance(loaded, dict):
        raise ValueError("producer stdout JSON must be an object")
    return loaded


def run_subprocess(command: list[str], request_path: Path, producer: dict[str, Any], timeout_seconds: int) -> dict[str, Any]:
    """Invoke a CLI or MCP producer."""
    env = os.environ.copy()
    env.update(
        {
            "ONESHOT_PRODUCER_ID": str(producer.get("producer_id") or ""),
            "ONESHOT_SLOT_REMEDIATION_REQUEST": str(request_path),
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
    if completed.returncode != 0:
        return {
            "ok": False,
            "error": f"producer exited {completed.returncode}",
            "stdout_tail": completed.stdout[-1000:],
            "stderr_tail": completed.stderr[-1000:],
            "command": command,
        }
    response = parse_producer_stdout(completed.stdout)
    response.setdefault("command", command)
    response.setdefault("stderr_tail", completed.stderr[-1000:])
    response["ok"] = True
    return response


def run_api(endpoint: str, payload: dict[str, Any], producer: dict[str, Any], timeout_seconds: int) -> dict[str, Any]:
    """Invoke an API producer with a JSON POST."""
    body = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    api_key_env = producer.get("api_key_env_var")
    if api_key_env and os.environ.get(str(api_key_env)):
        headers["Authorization"] = f"Bearer {os.environ[str(api_key_env)]}"
    req = request.Request(endpoint, data=body, headers=headers, method="POST")
    try:
        with request.urlopen(req, timeout=timeout_seconds) as response:
            raw = response.read().decode("utf-8", errors="replace")
            loaded = json.loads(raw) if raw.strip() else {}
            if not isinstance(loaded, dict):
                raise ValueError("producer API response JSON must be an object")
            loaded["ok"] = 200 <= response.status < 300
            loaded["http_status"] = response.status
            return loaded
    except (URLError, ValueError, json.JSONDecodeError) as exc:
        return {"ok": False, "error": str(exc)}


def invoke_producer(
    producer: dict[str, Any],
    payload: dict[str, Any],
    request_path: Path,
    timeout_seconds: int,
) -> dict[str, Any]:
    """Invoke a producer according to its registry method."""
    request_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if producer.get("cli_command"):
        command = expand_command(str(producer["cli_command"]), request_path, payload, producer)
        return run_subprocess(command, request_path, producer, timeout_seconds)
    if producer.get("mcp_path"):
        return run_subprocess(mcp_command(str(producer["mcp_path"]), request_path), request_path, producer, timeout_seconds)
    if producer.get("api_endpoint"):
        return run_api(str(producer["api_endpoint"]), payload, producer, timeout_seconds)
    return {"ok": False, "error": "producer has no invocation method"}


def quality_gate_passed(response: dict[str, Any], pass_required: bool) -> tuple[bool, str]:
    """Evaluate producer-owned quality gate output."""
    verdict = (
        response.get("quality_gate_result")
        or response.get("quality_gate_verdict")
        or response.get("quality_verdict")
        or response.get("quality")
    )
    if isinstance(verdict, str):
        normalized = verdict.lower()
        if normalized == "pass":
            return True, "quality_gate: pass"
        return False, f"quality_gate: {normalized}"
    if not pass_required:
        return True, "quality_gate: not required"
    return False, "quality_gate: missing pass verdict"


def artifact_path_from_response(response: dict[str, Any]) -> Path | None:
    """Extract an artifact path from a producer response."""
    raw = response.get("artifact_path") or response.get("path") or response.get("locked_artifact_path")
    if not isinstance(raw, str) or not raw.strip():
        return None
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = (REPO_ROOT / path).resolve()
    return path


def first_failed_check(slot_report: dict[str, Any]) -> str:
    """Return a concise reason from a failed slot report."""
    for name, check in slot_report.get("checks", {}).items():
        if isinstance(check, dict) and check.get("verdict") == "fail":
            details = check.get("details") or ""
            return f"slot_integration: {name}: {details}"
    return f"slot_integration: {slot_report.get('remediation_hint') or 'failed'}"


def attempt_record(
    attempt: int,
    producer_id: str,
    attempt_type: str,
    verdict: str,
    reason: str | None = None,
    artifact_path: str | None = None,
) -> dict[str, Any]:
    """Build an output attempt record."""
    record: dict[str, Any] = {
        "attempt": attempt,
        "producer_id": producer_id,
        "type": attempt_type,
        "verdict": verdict,
    }
    if reason:
        record["reason"] = reason
    if artifact_path:
        record["artifact_path"] = artifact_path
    return record


def escape_table(value: Any) -> str:
    """Escape markdown table cell text."""
    return str(value or "").replace("|", "\\|").replace("\n", " ").strip()


def incompatibility_log_path(vault_root: Path) -> Path:
    """Return the producer-slot incompatibility log path."""
    return vault_root / INCOMPATIBILITY_LOG_RELATIVE


def initial_log_text() -> str:
    """Return initial producer-slot incompatibility log text."""
    return (
        "---\n"
        "type: producer-slot-incompatibility-log\n"
        "version: 1\n"
        f"last_updated: {now_iso(timespec='minutes')}\n"
        "---\n\n"
        "# Producer-Slot Incompatibility Log\n\n"
        "Append-only log of cases where a producer's artifact passed its quality gate but failed a medium's slot "
        "integration gate. Used by `check_producer_slot_telemetry.py` to surface \"producer-slot-fit limitation\" "
        "signals informing V7-B planning.\n\n"
        "## Format\n\n"
        "| Date | Producer ID | Medium | Slot Role | Failure Mode | Project |\n"
        "|------|-------------|--------|-----------|--------------|---------|\n"
        "\n"
        "(populated automatically by run_slot_remediation.py)\n"
    )


def ensure_incompatibility_log(vault_root: Path) -> Path:
    """Create the log if missing."""
    path = incompatibility_log_path(vault_root)
    if not path.exists():
        artifact_registry.atomic_write_text(path, initial_log_text())
    return path


def append_incompatibility(
    vault_root: Path,
    producer_id: str,
    medium: str,
    slot_role: str,
    failure_mode: str,
    project: str,
) -> None:
    """Append a producer-medium-slot incompatibility record."""
    path = ensure_incompatibility_log(vault_root)
    row = (
        f"| {escape_table(date_text())} | {escape_table(producer_id)} | {escape_table(medium)} | "
        f"{escape_table(slot_role)} | {escape_table(failure_mode)} | {escape_table(project)} |\n"
    )
    with path.open("a", encoding="utf-8") as handle:
        handle.write(row)
        handle.flush()
        os.fsync(handle.fileno())
    artifact_registry.fsync_parent(path)


def report_dir(vault_root: Path, project: str) -> Path:
    """Return the directory for operator reports."""
    safe_project = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in project).strip("-") or "slot-remediation"
    path = vault_root / "snapshots" / safe_project
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_incompatibility_report(
    vault_root: Path,
    artifact_id: str,
    artifact_type: str,
    slot_contract: dict[str, Any],
    attempts: list[dict[str, Any]],
    project: str,
) -> Path:
    """Write the operator decision report when remediation is exhausted."""
    path = report_dir(vault_root, project) / f"{date_text()}-{artifact_id}-slot-incompatibility-report.md"
    body = (
        "---\n"
        "type: snapshot\n"
        "slot_incompatibility_report: true\n"
        f"project: {json.dumps(project)}\n"
        f"artifact_id: {json.dumps(artifact_id)}\n"
        f"artifact_type: {json.dumps(artifact_type)}\n"
        f"medium: {json.dumps(slot_contract.get('medium'))}\n"
        f"slot_role: {json.dumps(slot_contract.get('slot_role'))}\n"
        f"created_at: {now_iso()}\n"
        "operator_action_options:\n"
        "  - adjust_slot_contract\n"
        "  - approve_different_producer\n"
        "  - accept_manual_art_direction\n"
        "  - reroute_to_custom_mode\n"
        "---\n\n"
        f"# Slot Incompatibility Report - {artifact_id}\n\n"
        "The artifact producer(s) passed producer-owned quality checks but failed the medium-owned slot integration gate.\n\n"
        "## Slot Contract\n\n"
        "```json\n"
        f"{json.dumps(slot_contract, indent=2, sort_keys=True)}\n"
        "```\n\n"
        "## Remediation Attempts\n\n"
    )
    for attempt in attempts:
        body += (
            f"- Attempt {attempt.get('attempt')}: `{attempt.get('producer_id')}` "
            f"({attempt.get('type')}) -> {attempt.get('verdict')}. "
            f"{attempt.get('reason', '')}\n"
        )
    body += (
        "\n## Operator Decision Needed\n\n"
        "Choose whether to adjust the slot contract, approve a different producer, accept manual art direction, "
        "or reroute this artifact to custom mode.\n"
    )
    artifact_registry.atomic_write_text(path, body)
    return path


def run_single_attempt(
    *,
    artifact_id: str,
    producer: dict[str, Any],
    artifact_type: str,
    slot_contract: dict[str, Any],
    prompt: str,
    attempt_number: int,
    attempt_type: str,
    output_dir: Path,
    pass_required: bool,
    timeout_seconds: int,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Invoke a producer, run quality gate, then slot integration gate."""
    producer_id = str(producer.get("producer_id") or "")
    payload = request_payload(
        artifact_id,
        producer,
        artifact_type,
        slot_contract,
        prompt,
        attempt_number,
        attempt_type,
        output_dir,
    )
    request_path = output_dir / f"attempt-{attempt_number}-{producer_id}-request.json"
    response = invoke_producer(producer, payload, request_path, timeout_seconds)
    if not response.get("ok"):
        reason = f"producer_invocation: {response.get('error') or 'failed'}"
        return attempt_record(attempt_number, producer_id, attempt_type, "fail", reason), None

    quality_ok, quality_reason = quality_gate_passed(response, pass_required)
    artifact_path = artifact_path_from_response(response)
    if not quality_ok:
        return attempt_record(attempt_number, producer_id, attempt_type, "fail", quality_reason), None
    if artifact_path is None or not artifact_path.exists():
        reason = f"producer_output: missing artifact_path after {quality_reason}"
        return attempt_record(attempt_number, producer_id, attempt_type, "fail", reason), None

    slot_report = check_slot_integration.build_report(
        artifact_path,
        artifact_type,
        slot_contract,
        str(slot_contract.get("medium") or ""),
    )
    if slot_report.get("verdict") == "pass":
        return attempt_record(attempt_number, producer_id, attempt_type, "pass", artifact_path=str(artifact_path)), slot_report
    reason = first_failed_check(slot_report)
    return attempt_record(attempt_number, producer_id, attempt_type, "fail", reason, str(artifact_path)), slot_report


def run_remediation(args: argparse.Namespace) -> dict[str, Any]:
    """Run the full re-prompt -> fallback -> pause remediation flow."""
    if args.vault_root:
        os.environ["ONESHOT_VAULT_ROOT"] = str(Path(args.vault_root).expanduser().resolve())
    vault_root = artifact_registry.resolve_vault_root()
    slot_contract = get_slot_contract(Path(args.slot_contract_json))
    medium = str(slot_contract.get("medium") or "")
    slot_role = str(slot_contract.get("slot_role") or "")
    project = args.project or os.environ.get("ONESHOT_PROJECT_SLUG") or args.artifact_id
    output_dir = work_dir_for(args)
    primary = get_producer_or_raise(args.producer_id)
    if not producer_active(primary):
        raise RuntimeError(f"producer {args.producer_id} is not active for remediation")
    artifact_type = artifact_type_for(primary, args.artifact_type)
    pass_required = bool(args.quality_gate_pass_required)

    attempts: list[dict[str, Any]] = []
    telemetry_logged = False
    previous_reason: str | None = None
    attempt_number = 1

    for reprompt_index in range(1, args.max_attempts + 1):
        attempt_type = "re-prompt" if reprompt_index == 1 else "re-prompt-with-stricter-constraints"
        prompt = augment_prompt(args.original_prompt, slot_contract, reprompt_index, previous_reason)
        record, slot_report = run_single_attempt(
            artifact_id=args.artifact_id,
            producer=primary,
            artifact_type=artifact_type,
            slot_contract=slot_contract,
            prompt=prompt,
            attempt_number=attempt_number,
            attempt_type=attempt_type,
            output_dir=output_dir,
            pass_required=pass_required,
            timeout_seconds=args.timeout_seconds,
        )
        attempts.append(record)
        if record["verdict"] == "pass":
            return {
                "artifact_id": args.artifact_id,
                "slot_role": slot_role,
                "medium": medium,
                "remediation_attempts": attempts,
                "final_verdict": "pass_via_reprompt",
                "producer_substitution_for_slot": None,
                "incompatibility_report_path": None,
                "telemetry_logged": telemetry_logged,
            }
        if slot_report is not None and slot_report.get("verdict") == "fail":
            append_incompatibility(vault_root, args.producer_id, medium, slot_role, str(record.get("reason")), project)
            telemetry_logged = True
        previous_reason = str(record.get("reason") or "")
        attempt_number += 1

    for fallback_id in primary.get("fallback_chain", []):
        fallback = get_producer_or_raise(str(fallback_id))
        if not producer_active(fallback):
            attempts.append(attempt_record(attempt_number, str(fallback_id), "fallback", "fail", "producer not active"))
            attempt_number += 1
            continue
        fallback_type = artifact_type_for(fallback, args.artifact_type)
        prompt = augment_prompt(args.original_prompt, slot_contract, args.max_attempts + 1, previous_reason)
        record, slot_report = run_single_attempt(
            artifact_id=args.artifact_id,
            producer=fallback,
            artifact_type=fallback_type,
            slot_contract=slot_contract,
            prompt=prompt,
            attempt_number=attempt_number,
            attempt_type="fallback",
            output_dir=output_dir,
            pass_required=pass_required,
            timeout_seconds=args.timeout_seconds,
        )
        attempts.append(record)
        if record["verdict"] == "pass":
            return {
                "artifact_id": args.artifact_id,
                "slot_role": slot_role,
                "medium": medium,
                "remediation_attempts": attempts,
                "final_verdict": "pass_via_substitution",
                "producer_substitution_for_slot": str(fallback.get("producer_id")),
                "incompatibility_report_path": None,
                "telemetry_logged": telemetry_logged,
            }
        if slot_report is not None and slot_report.get("verdict") == "fail":
            append_incompatibility(vault_root, str(fallback.get("producer_id")), medium, slot_role, str(record.get("reason")), project)
            telemetry_logged = True
        previous_reason = str(record.get("reason") or "")
        attempt_number += 1

    report_path = write_incompatibility_report(vault_root, args.artifact_id, artifact_type, slot_contract, attempts, project)
    return {
        "artifact_id": args.artifact_id,
        "slot_role": slot_role,
        "medium": medium,
        "remediation_attempts": attempts,
        "final_verdict": "paused_with_incompatibility_report",
        "producer_substitution_for_slot": None,
        "incompatibility_report_path": str(report_path),
        "telemetry_logged": telemetry_logged,
    }


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-id", required=True)
    parser.add_argument("--slot-contract-json", required=True)
    parser.add_argument("--producer-id", required=True)
    parser.add_argument("--original-prompt", required=True)
    parser.add_argument("--quality-gate-pass-required", required=True, type=parse_bool)
    parser.add_argument("--max-attempts", type=int, default=2)
    parser.add_argument("--json-out")
    parser.add_argument("--artifact-type")
    parser.add_argument("--project")
    parser.add_argument("--timeout-seconds", type=int, default=120)
    parser.add_argument("--vault-root")
    parser.add_argument("--work-dir")
    return parser.parse_args()


def main() -> int:
    """Run slot remediation."""
    args = parse_args()
    try:
        report = run_remediation(args)
    except Exception as exc:
        report = {
            "artifact_id": getattr(args, "artifact_id", None),
            "slot_role": None,
            "medium": None,
            "remediation_attempts": [],
            "final_verdict": "error",
            "producer_substitution_for_slot": None,
            "incompatibility_report_path": None,
            "telemetry_logged": False,
            "error": str(exc),
        }
        write_json(report, args.json_out)
        return 1
    write_json(report, args.json_out)
    return 0 if report["final_verdict"] in {"pass_via_reprompt", "pass_via_substitution"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
