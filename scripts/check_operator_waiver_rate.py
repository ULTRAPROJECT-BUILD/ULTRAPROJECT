#!/usr/bin/env python3
"""Compute per-operator visual-spec waiver rates over rolling windows."""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from visual_spec_telemetry_common import (
    PLATFORM_CONFIG_PATH,
    load_outcomes_with_metadata,
    load_project_records_from_log,
    load_waiver_log,
    outcome_operator_id,
    pct,
    platform_value,
    utc_now_iso,
    write_json,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--waivers-log", required=True, help="Path to vault/config/visual-spec-waivers.md.")
    parser.add_argument("--operator-id", required=True, help="Operator identifier to evaluate.")
    parser.add_argument("--total-projects-log", help="Optional dated project log for denominator counts.")
    parser.add_argument("--json-out", help="Optional path to write JSON output.")
    return parser.parse_args()


def fallback_project_records(operator_id: str) -> list[dict[str, Any]]:
    """Best-effort fallback to outcome telemetry when no total-project log exists."""
    root = Path(os.environ.get("ONESHOT_VAULT_ROOT", str((SCRIPT_DIR.parent / "vault").resolve())))
    outcomes_root = root / "snapshots"
    outcomes, _invalid = load_outcomes_with_metadata(outcomes_root)
    records: list[dict[str, Any]] = []
    for outcome in outcomes:
        if outcome_operator_id(outcome) != operator_id:
            continue
        records.append(
            {
                "project": str(outcome.get("project") or ""),
                "operator": operator_id,
                "timestamp": outcome.get("_timestamp"),
            }
        )
    return records


def count_window(items: list[dict[str, Any]], operator_id: str, start: datetime, end: datetime) -> int:
    """Count operator items inside a time window."""
    total = 0
    for item in items:
        if str(item.get("operator") or "").strip() != operator_id:
            continue
        timestamp = item.get("timestamp")
        if timestamp is None or not (start <= timestamp < end):
            continue
        total += 1
    return total


def alert_level(rate_pct: float, *, window: str) -> str:
    """Return alert color for a window."""
    if window == "30d":
        yellow = float(platform_value("visual_spec_waiver_rate_30d_yellow_threshold_pct", 30))
        red = float(platform_value("visual_spec_waiver_rate_30d_red_threshold_pct", 50))
        if rate_pct > red:
            return "red"
        if rate_pct > yellow:
            return "yellow"
        return "none"
    red = float(platform_value("visual_spec_waiver_rate_90d_red_threshold_pct", 40))
    return "red" if rate_pct > red else "none"


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    waivers = load_waiver_log(Path(args.waivers_log).expanduser().resolve())
    now = datetime.now(timezone.utc)
    windows = {
        "30d": (now - timedelta(days=30), now),
        "90d": (now - timedelta(days=90), now),
    }

    if args.total_projects_log:
        project_records = load_project_records_from_log(Path(args.total_projects_log).expanduser().resolve())
    else:
        project_records = fallback_project_records(args.operator_id)

    waiver_records = [{"operator": row["operator"], "timestamp": row["timestamp"]} for row in waivers]
    window_payloads: dict[str, dict[str, Any]] = {}
    saw_denominator = False
    for label, (start, end) in windows.items():
        waiver_count = count_window(waiver_records, args.operator_id, start, end)
        total_projects = count_window(project_records, args.operator_id, start, end)
        saw_denominator = saw_denominator or total_projects > 0
        rate_pct = pct(waiver_count, total_projects)
        window_payloads[label] = {
            "waivers": waiver_count,
            "total": total_projects,
            "rate_pct": rate_pct,
            "alert_level": alert_level(rate_pct, window=label),
        }

    red = "red" in {window_payloads["30d"]["alert_level"], window_payloads["90d"]["alert_level"]}
    yellow = window_payloads["30d"]["alert_level"] == "yellow" and not red
    cooling_hours = int(platform_value("visual_spec_waiver_cooling_off_hours", 24))
    return {
        "operator_id": args.operator_id,
        "checked_at": utc_now_iso(),
        "windows": window_payloads,
        "requires_second_review": red,
        "requires_cooling_off": red,
        "cooling_off_hours": cooling_hours if red else 0,
        "verdict": "red" if red else "yellow" if yellow else "ok",
        "data_source": repo_source_label(args.total_projects_log, saw_denominator),
    }


def repo_source_label(total_projects_log: str | None, saw_denominator: bool) -> str:
    """Describe the denominator source for debugging."""
    if total_projects_log:
        return "total_projects_log"
    if saw_denominator:
        return "outcome_fallback"
    return f"no_data_yet ({PLATFORM_CONFIG_PATH.parent / 'visual-spec-waivers.md'})"


def main() -> int:
    args = parse_args()
    try:
        write_json(build_payload(args), args.json_out)
        return 0
    except Exception as exc:
        write_json(
            {
                "operator_id": args.operator_id,
                "checked_at": utc_now_iso(),
                "error": str(exc),
                "verdict": "error",
            },
            args.json_out,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
