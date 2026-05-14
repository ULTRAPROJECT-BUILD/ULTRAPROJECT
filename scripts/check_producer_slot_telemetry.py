#!/usr/bin/env python3
"""Aggregate producer-medium-slot incompatibility telemetry."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import artifact_registry

LOG_RELATIVE = Path("config") / "producer-slot-incompatibility-log.md"
LIMITATION_THRESHOLD = 5


def now_iso() -> str:
    """Return a machine-local timestamp."""
    return datetime.now().astimezone().isoformat(timespec="seconds")


def write_json(payload: dict[str, Any], json_out: str | None) -> None:
    """Write JSON to stdout and optionally to a file."""
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if json_out:
        out_path = Path(json_out).expanduser()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text, encoding="utf-8")
    sys.stdout.write(text)


def log_path(vault_root: Path) -> Path:
    """Return the telemetry log path."""
    return vault_root / LOG_RELATIVE


def split_table_row(line: str) -> list[str] | None:
    """Split a markdown table row into cells."""
    stripped = line.strip()
    if not stripped.startswith("|") or not stripped.endswith("|"):
        return None
    cells = [cell.strip().replace("\\|", "|") for cell in stripped.strip("|").split("|")]
    if len(cells) != 6:
        return None
    if cells[0].lower() in {"date", "------"}:
        return None
    return cells


def read_records(path: Path) -> list[dict[str, str]]:
    """Read telemetry records from the markdown table."""
    if not path.exists():
        return []
    records: list[dict[str, str]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        cells = split_table_row(line)
        if cells is None:
            continue
        date, producer_id, medium, slot_role, failure_mode, project = cells
        records.append(
            {
                "date": date,
                "producer_id": producer_id,
                "medium": medium,
                "slot_role": slot_role,
                "failure_mode": failure_mode,
                "project": project,
            }
        )
    return records


def matches(record: dict[str, str], producer_id: str | None, medium: str | None) -> bool:
    """Return whether a record passes optional filters."""
    if producer_id and record.get("producer_id") != producer_id:
        return False
    if medium and record.get("medium") != medium:
        return False
    return True


def aggregate(records: list[dict[str, str]]) -> list[dict[str, Any]]:
    """Aggregate records by producer, medium, and slot role."""
    grouped: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    for record in records:
        key = (record["producer_id"], record["medium"], record["slot_role"])
        grouped[key].append(record)

    rows: list[dict[str, Any]] = []
    for (producer_id, medium, slot_role), items in sorted(grouped.items()):
        projects = sorted({item.get("project", "") for item in items if item.get("project")})
        failure_modes = Counter(item.get("failure_mode", "") for item in items)
        count = len(items)
        rows.append(
            {
                "producer_id": producer_id,
                "medium": medium,
                "slot_role": slot_role,
                "incompatibility_count": count,
                "projects_impacted": len(projects),
                "project_examples": projects[:10],
                "dominant_failure_modes": [
                    {"failure_mode": mode, "count": mode_count}
                    for mode, mode_count in failure_modes.most_common(5)
                ],
                "incompatibility_rate": 1.0,
                "rate_basis": "incompatibility log contains failures only; total slot attempts are not recorded in this log",
                "flag": "producer-slot-fit limitation" if count >= LIMITATION_THRESHOLD else None,
                "surface_in_monthly_engagement_report": count >= LIMITATION_THRESHOLD,
                "v7b_planning_signal": count >= LIMITATION_THRESHOLD,
            }
        )
    return rows


def build_report(vault_root: Path, producer_id: str | None = None, medium: str | None = None) -> dict[str, Any]:
    """Build telemetry aggregation report."""
    path = log_path(vault_root)
    all_records = read_records(path)
    filtered = [record for record in all_records if matches(record, producer_id, medium)]
    aggregates = aggregate(filtered)
    flagged = [row for row in aggregates if row["flag"]]
    return {
        "checked_at": now_iso(),
        "log_path": str(path),
        "filters": {"producer_id": producer_id, "medium": medium},
        "record_count": len(filtered),
        "aggregate_count": len(aggregates),
        "aggregates": aggregates,
        "flagged_limitations": flagged,
        "threshold": LIMITATION_THRESHOLD,
        "monthly_engagement_report_signal_count": len(flagged),
    }


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--producer-id")
    parser.add_argument("--medium")
    parser.add_argument("--json-out")
    parser.add_argument("--vault-root")
    return parser.parse_args()


def main() -> int:
    """Run telemetry aggregation."""
    args = parse_args()
    if args.vault_root:
        os.environ["ONESHOT_VAULT_ROOT"] = str(Path(args.vault_root).expanduser().resolve())
    try:
        vault_root = artifact_registry.resolve_vault_root()
        report = build_report(vault_root, args.producer_id, args.medium)
    except Exception as exc:
        report = {
            "checked_at": now_iso(),
            "log_path": None,
            "filters": {"producer_id": args.producer_id, "medium": args.medium},
            "record_count": 0,
            "aggregate_count": 0,
            "aggregates": [],
            "flagged_limitations": [],
            "threshold": LIMITATION_THRESHOLD,
            "monthly_engagement_report_signal_count": 0,
            "error": str(exc),
        }
        write_json(report, args.json_out)
        return 1
    write_json(report, args.json_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
