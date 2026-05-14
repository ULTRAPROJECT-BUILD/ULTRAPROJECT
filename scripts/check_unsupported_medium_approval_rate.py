#!/usr/bin/env python3
"""Track per-operator approvals of proposals that required unsupported-medium review."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from visual_spec_telemetry_common import (
    load_markdown_with_frontmatter,
    operator_from_text,
    parse_timestamp,
    parse_timestamp_from_path,
    platform_value,
    proposal_regression_status,
    utc_now_iso,
    write_json,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--proposals-dir", required=True, help="Path to vault/archive/visual-aesthetics/proposals/.")
    parser.add_argument("--operator-id", required=True, help="Operator identifier to evaluate.")
    parser.add_argument("--json-out", help="Optional path to write JSON output.")
    return parser.parse_args()


def iter_proposals(root: Path) -> list[Path]:
    """Return markdown proposals beneath a directory."""
    if not root.exists():
        return []
    return sorted(path.resolve() for path in root.rglob("*.md") if path.is_file())


def is_approved_unsupported(frontmatter: dict[str, Any]) -> bool:
    """Return true when a proposal required operator review and was approved."""
    if str(frontmatter.get("operator_decision") or "").strip() != "approved":
        return False
    return proposal_regression_status(frontmatter) == "operator_review_required"


def proposal_operator(frontmatter: dict[str, Any], body: str) -> str | None:
    """Return the proposal approver/operator when recorded."""
    return operator_from_text(frontmatter, body)


def proposal_timestamp(frontmatter: dict[str, Any], path: Path) -> datetime | None:
    """Prefer the proposal frontmatter timestamp, then filename."""
    return parse_timestamp(frontmatter.get("created")) or parse_timestamp_from_path(path)


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    proposals_dir = Path(args.proposals_dir).expanduser().resolve()
    threshold = int(platform_value("visual_spec_unsupported_medium_approval_90d_red_threshold_count", 3))
    cooling_hours = int(platform_value("visual_spec_unsupported_medium_cooling_off_hours", 48))
    start = datetime.now(timezone.utc) - timedelta(days=90)
    end = datetime.now(timezone.utc)

    approvals: list[dict[str, Any]] = []
    missing_operator = 0
    for path in iter_proposals(proposals_dir):
        try:
            frontmatter, body = load_markdown_with_frontmatter(path)
        except Exception:
            continue
        if frontmatter.get("type") != "preset-update-proposal":
            continue
        if not is_approved_unsupported(frontmatter):
            continue
        operator_id = proposal_operator(frontmatter, body)
        if not operator_id:
            missing_operator += 1
            continue
        created = proposal_timestamp(frontmatter, path)
        if created is None or not (start <= created < end):
            continue
        if operator_id != args.operator_id:
            continue
        approvals.append({"path": str(path), "created": created.isoformat()})

    count = len(approvals)
    red = count > threshold
    payload = {
        "operator_id": args.operator_id,
        "checked_at": utc_now_iso(),
        "windows": {
            "90d": {
                "approvals": count,
                "threshold_count": threshold,
                "alert_level": "red" if red else "none",
            }
        },
        "requires_second_review": red,
        "requires_cooling_off": red,
        "cooling_off_hours": cooling_hours if red else 0,
        "verdict": "red" if red else "ok",
        "approvals": approvals,
        "missing_operator_attribution": missing_operator,
        "data_source": "no_data_yet" if not proposals_dir.exists() else "proposal_frontmatter_and_body",
    }
    return payload


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
