#!/usr/bin/env python3
"""Generate a monthly Visual Specification System engagement report."""

from __future__ import annotations

import argparse
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from visual_spec_telemetry_common import (
    load_markdown_with_frontmatter,
    load_outcomes_with_metadata,
    load_waiver_log,
    month_bounds,
    operator_from_text,
    outcome_operator_id,
    outcome_primary_reviewer,
    parse_timestamp,
    parse_timestamp_from_path,
    platform_value,
    points_to_grade,
    repo_relative,
    utc_now_iso,
    write_json,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--month", help="Month to aggregate in YYYY-MM form. Defaults to the current UTC month.")
    parser.add_argument("--out", help="Optional markdown output path override.")
    parser.add_argument("--json-out", help="Optional path to write JSON output.")
    return parser.parse_args()


def default_month() -> str:
    """Return the current UTC month."""
    return datetime.now(timezone.utc).strftime("%Y-%m")


def month_label(month: str) -> str:
    """Return a human-readable month label."""
    start, _ = month_bounds(month)
    return start.strftime("%B %Y")


def proposal_operators_for_month(root: Path, start: datetime, end: datetime) -> set[str]:
    """Collect operators named in proposal bodies/frontmatter for the month."""
    if not root.exists():
        return set()
    operators: set[str] = set()
    for path in root.rglob("*.md"):
        if not path.is_file():
            continue
        try:
            frontmatter, body = load_markdown_with_frontmatter(path)
        except Exception:
            continue
        created = parse_timestamp(frontmatter.get("created")) or parse_timestamp_from_path(path)
        if created is None or not (start <= created < end):
            continue
        operator_id = operator_from_text(frontmatter, body)
        if operator_id:
            operators.add(operator_id)
    return operators


def choose_operator(outcome: dict[str, Any]) -> str:
    """Choose the best available operator bucket for an outcome."""
    return outcome_operator_id(outcome) or outcome_primary_reviewer(outcome) or "unknown"


def output_path_for_month(month: str, override: str | None) -> Path:
    """Resolve the markdown output path."""
    if override:
        return Path(override).expanduser().resolve()
    template = str(platform_value("visual_spec_engagement_report_path_template", "vault/config/visual-system-engagement-{YYYY-MM}.md"))
    return (SCRIPT_DIR.parent / template.replace("{YYYY-MM}", month)).resolve()


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    month = args.month or default_month()
    start, end = month_bounds(month)
    vault_root = Path(os.environ.get("ONESHOT_VAULT_ROOT", str((SCRIPT_DIR.parent / "vault").resolve())))
    outcomes_root = vault_root / "snapshots"
    waivers_path = vault_root / "config" / "visual-spec-waivers.md"
    proposals_root = vault_root / "archive" / "visual-aesthetics" / "proposals"

    outcomes, invalid_outcomes = load_outcomes_with_metadata(outcomes_root)
    waivers = load_waiver_log(waivers_path)
    operators = proposal_operators_for_month(proposals_root, start, end)
    stats: dict[str, dict[str, Any]] = defaultdict(lambda: {"projects": set(), "vs_fired": 0, "waivers": 0, "grade_points": []})

    for outcome in outcomes:
        timestamp = outcome.get("_timestamp")
        if timestamp is None or not (start <= timestamp < end):
            continue
        operator = choose_operator(outcome)
        stats[operator]["projects"].add(str(outcome.get("project") or ""))
        stats[operator]["vs_fired"] += 1
        grade_points = outcome.get("reviewer_grades")
        if isinstance(grade_points, list) and grade_points:
            last = grade_points[-1]
            from visual_spec_telemetry_common import grade_to_points

            points = grade_to_points(last.get("grade") if isinstance(last, dict) else None)
        else:
            from visual_spec_telemetry_common import grade_to_points

            points = grade_to_points(outcome.get("delivery_review_grade"))
        if points is not None:
            stats[operator]["grade_points"].append(points)
        operators.add(operator)

    for row in waivers:
        timestamp = row.get("timestamp")
        if timestamp is None or not (start <= timestamp < end):
            continue
        operator = str(row.get("operator") or "").strip() or "unknown"
        stats[operator]["waivers"] += 1
        operators.add(operator)

    sorted_operators = sorted(operators)
    rows: list[dict[str, Any]] = []
    for operator in sorted_operators:
        entry = stats.get(operator, {"projects": set(), "vs_fired": 0, "waivers": 0, "grade_points": []})
        project_total = len({project for project in entry["projects"] if project})
        waiver_rate = 0.0 if project_total == 0 else round((entry["waivers"] / project_total) * 100.0, 2)
        avg_points = None
        if entry["grade_points"]:
            avg_points = sum(entry["grade_points"]) / len(entry["grade_points"])
        rows.append(
            {
                "operator": operator,
                "projects": project_total,
                "vs_fired": entry["vs_fired"],
                "waivers": entry["waivers"],
                "waiver_rate_pct": waiver_rate,
                "avg_visual_gate_grade": points_to_grade(avg_points),
            }
        )

    if not rows:
        rows.append(
            {
                "operator": "—",
                "projects": 0,
                "vs_fired": 0,
                "waivers": 0,
                "waiver_rate_pct": 0.0,
                "avg_visual_gate_grade": "N/A",
            }
        )

    markdown_lines = [
        f"# Visual System Engagement — {month_label(month)}",
        "",
        "| Operator | Projects | VS Fired | Waivers | Waiver Rate | Avg Visual Gate Grade |",
        "|----------|----------|----------|---------|-------------|----------------------|",
    ]
    for row in rows:
        markdown_lines.append(
            f"| {row['operator']} | {row['projects']} | {row['vs_fired']} | {row['waivers']} | {row['waiver_rate_pct']:.2f}% | {row['avg_visual_gate_grade']} |"
        )
    markdown = "\n".join(markdown_lines) + "\n"

    out_path = output_path_for_month(month, args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(markdown, encoding="utf-8")

    return {
        "month": month,
        "generated_at": utc_now_iso(),
        "report_path": repo_relative(out_path),
        "markdown_written": str(out_path),
        "rows": rows,
        "invalid_outcomes": invalid_outcomes,
        "status": "no_data_yet" if rows and rows[0]["operator"] == "—" else "ok",
    }


def main() -> int:
    args = parse_args()
    try:
        write_json(build_report(args), args.json_out)
        return 0
    except Exception as exc:
        write_json(
            {
                "month": args.month or default_month(),
                "generated_at": utc_now_iso(),
                "error": str(exc),
                "verdict": "error",
            },
            args.json_out,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
