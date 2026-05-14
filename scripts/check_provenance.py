#!/usr/bin/env python3
"""Verify reviewer/adversarial session provenance for visual-spec review artifacts."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from visual_spec_telemetry_common import load_frontmatter, utc_now_iso, write_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adjudication-paths", nargs="+", required=True, help="Adjudication markdown artifact paths.")
    parser.add_argument("--adversarial-path", required=True, help="Adversarial-pass markdown artifact path.")
    parser.add_argument("--runtime-log", help="Optional runtime log path for session provenance verification.")
    parser.add_argument("--json-out", help="Optional path to write JSON output.")
    return parser.parse_args()


def session_id_from_frontmatter(path: Path) -> str:
    """Extract reviewer_session_id from a markdown artifact."""
    frontmatter = load_frontmatter(path)
    session_id = str(frontmatter.get("reviewer_session_id") or frontmatter.get("session_id") or "").strip()
    if not session_id:
        raise ValueError(f"{path} is missing reviewer_session_id.")
    return session_id


def load_runtime_index(path: Path) -> list[dict[str, str]]:
    """Load a best-effort runtime event index from JSON, JSONL, or text logs."""
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    entries: list[dict[str, str]] = []

    if path.suffix.lower() == ".json":
        loaded = json.loads(text)
        entries.extend(flatten_runtime_payload(loaded))
    elif path.suffix.lower() == ".jsonl":
        for line in text.splitlines():
            if not line.strip():
                continue
            entries.extend(flatten_runtime_payload(json.loads(line)))
    else:
        for line in text.splitlines():
            lowered = line.lower()
            session_match = re.search(r"(?:session_id|session)[\"'=:\s]+([A-Za-z0-9._:-]+)", line)
            if not session_match:
                continue
            role_match = re.search(r"(?:task_type|role|agent_role|force-agent)[\"'=:\s]+([A-Za-z0-9._:-]+)", line)
            entries.append({"session_id": session_match.group(1), "role": role_match.group(1) if role_match else lowered})
    return entries


def flatten_runtime_payload(payload: Any) -> list[dict[str, str]]:
    """Flatten JSON runtime payloads to session/role records."""
    entries: list[dict[str, str]] = []
    if isinstance(payload, dict):
        session_id = str(payload.get("session_id") or "").strip()
        role = str(payload.get("role") or payload.get("task_type") or payload.get("agent_role") or "").strip()
        if session_id:
            entries.append({"session_id": session_id, "role": role})
        for value in payload.values():
            entries.extend(flatten_runtime_payload(value))
        return entries
    if isinstance(payload, list):
        for item in payload:
            entries.extend(flatten_runtime_payload(item))
    return entries


def role_matches(expected: str, actual: str) -> bool:
    """Return true when a runtime role is compatible with the expected artifact type."""
    normalized = actual.lower()
    if expected == "adjudication":
        return any(token in normalized for token in ("review", "visual", "adjudication"))
    return any(token in normalized for token in ("adversarial", "visual", "review"))


def verify_runtime_sessions(runtime_entries: list[dict[str, str]], adjudications: list[str], adversarial: str) -> tuple[bool, str]:
    """Verify all sessions appear in the runtime log with plausible roles."""
    if not runtime_entries:
        return False, "runtime log had no parseable session records"
    grouped: dict[str, list[str]] = {}
    for entry in runtime_entries:
        grouped.setdefault(entry.get("session_id", ""), []).append(entry.get("role", ""))

    missing: list[str] = []
    mismatched: list[str] = []
    for session_id in adjudications:
        roles = grouped.get(session_id)
        if not roles:
            missing.append(session_id)
            continue
        if not any(role_matches("adjudication", role) for role in roles):
            mismatched.append(f"{session_id} (roles={roles})")
    roles = grouped.get(adversarial)
    if not roles:
        missing.append(adversarial)
    elif not any(role_matches("adversarial", role) for role in roles):
        mismatched.append(f"{adversarial} (roles={roles})")

    if missing or mismatched:
        details = []
        if missing:
            details.append("missing sessions: " + ", ".join(sorted(missing)))
        if mismatched:
            details.append("role mismatches: " + ", ".join(sorted(mismatched)))
        return False, "; ".join(details)
    return True, "all sessions found in runtime log with plausible roles"


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    adjudication_ids = [session_id_from_frontmatter(Path(raw).expanduser().resolve()) for raw in args.adjudication_paths]
    adversarial_id = session_id_from_frontmatter(Path(args.adversarial_path).expanduser().resolve())
    all_sessions = adjudication_ids + [adversarial_id]
    unique = len(all_sessions) == len(set(all_sessions))

    runtime_verified = True
    runtime_details = "runtime log not provided"
    if args.runtime_log:
        runtime_entries = load_runtime_index(Path(args.runtime_log).expanduser().resolve())
        runtime_verified, runtime_details = verify_runtime_sessions(runtime_entries, adjudication_ids, adversarial_id)

    verdict = "pass" if unique and runtime_verified else "fail"
    details = []
    if not unique:
        details.append("reviewer_session_id values are not unique across adjudications/adversarial artifact")
    if runtime_details:
        details.append(runtime_details)

    return {
        "checked_at": utc_now_iso(),
        "adjudication_session_ids": adjudication_ids,
        "adversarial_session_id": adversarial_id,
        "all_unique": unique,
        "session_provenance_verified": runtime_verified,
        "verdict": verdict,
        "details": "; ".join(details),
    }


def main() -> int:
    args = parse_args()
    try:
        payload = build_payload(args)
        write_json(payload, args.json_out)
        return 0 if payload["verdict"] == "pass" else 1
    except Exception as exc:
        write_json(
            {
                "checked_at": utc_now_iso(),
                "all_unique": False,
                "session_provenance_verified": False,
                "verdict": "fail",
                "details": str(exc),
            },
            args.json_out,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
