#!/usr/bin/env python3
"""
Check whether the active brief stack explicitly covers a capability-wave.

Policy:
- If no phase-scoped brief exists for the phase, the project brief governs by default.
- If one or more phase-scoped briefs exist, at least one of them must cover the target
  wave (either explicitly via `covered_waves` / wave mentions, or implicitly by being a
  broad phase brief with no wave limitation).
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from resolve_briefs import (
    BriefRecord,
    brief_sort_key,
    dedupe_by_path,
    infer_project,
    infer_search_roots,
    normalize_wave_label,
    phase_brief_covers_wave,
    scan_briefs,
)

TIMESTAMP_FMT = "%Y-%m-%dT%H:%M:%S"


def now() -> str:
    return datetime.now().astimezone().strftime(TIMESTAMP_FMT)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", help="Project slug.")
    parser.add_argument("--project-file", help="Optional project markdown path.")
    parser.add_argument("--project-plan", help="Optional project plan markdown path.")
    parser.add_argument("--phase", required=True, type=int, help="Phase number whose active wave is being checked.")
    parser.add_argument("--wave", required=True, help="Active wave name (for example: Wave 2B).")
    parser.add_argument(
        "--search-root",
        action="append",
        default=[],
        help="Optional creative-brief snapshot roots to scan. May be repeated.",
    )
    parser.add_argument("--json-out", help="Optional JSON output path.")
    parser.add_argument("--markdown-out", help="Optional markdown output path.")
    return parser.parse_args()


def serialize_record(record: BriefRecord) -> dict:
    return {
        "path": record.path,
        "title": record.title,
        "scope": record.scope,
        "phase": record.phase,
        "ticket": record.ticket,
        "covered_waves": record.covered_waves,
        "captured": record.captured,
        "updated": record.updated,
    }


def build_report(args: argparse.Namespace) -> dict:
    project = infer_project(args)
    wave = normalize_wave_label(args.wave)
    search_roots = infer_search_roots(args)
    scanned = scan_briefs(search_roots, project)

    project_briefs = dedupe_by_path([record for record in scanned if record.scope == "project"])
    phase_briefs_all = dedupe_by_path(
        [record for record in scanned if record.scope == "phase" and record.phase == args.phase]
    )
    applicable_phase_briefs = dedupe_by_path(
        [record for record in phase_briefs_all if phase_brief_covers_wave(record, wave)]
    )

    checks: list[dict] = []
    issues: list[str] = []
    verdict = "PASS"
    coverage_mode = ""
    reason = ""

    has_project_brief = bool(project_briefs)
    checks.append(
        {
            "name": "has_project_brief",
            "ok": has_project_brief,
            "detail": "project-scoped master brief exists" if has_project_brief else "no project-scoped master brief found",
        }
    )
    if not has_project_brief:
        verdict = "FAIL"
        issues.append("missing_project_brief")
        reason = "Wave coverage cannot be trusted without a project-scoped master brief."

    if verdict != "FAIL" and not phase_briefs_all:
        coverage_mode = "project_default"
        reason = "No phase-scoped brief exists for this phase, so the project brief governs by default."
        checks.append(
            {
                "name": "phase_brief_coverage",
                "ok": True,
                "detail": "no phase-scoped brief exists for this phase",
            }
        )
    elif verdict != "FAIL" and applicable_phase_briefs:
        coverage_mode = "phase_scoped"
        selected = sorted(applicable_phase_briefs, key=brief_sort_key, reverse=True)[0]
        if selected.covered_waves:
            reason = (
                f"Phase brief `{selected.title}` covers {wave} via "
                f"{', '.join(selected.covered_waves)}."
            )
        else:
            reason = (
                f"Phase brief `{selected.title}` has no wave limitation, so it governs the whole phase."
            )
        checks.append(
            {
                "name": "phase_brief_coverage",
                "ok": True,
                "detail": reason,
            }
        )
    elif verdict != "FAIL":
        verdict = "FAIL"
        coverage_mode = "missing_wave_supplement"
        issues.append("active_wave_not_covered_by_phase_brief")
        reason = (
            f"Phase-scoped briefs exist for phase {args.phase}, but none of them explicitly cover {wave}. "
            "Create a wave supplement creative brief before unblocking the new wave."
        )
        checks.append(
            {
                "name": "phase_brief_coverage",
                "ok": False,
                "detail": reason,
            }
        )

    return {
        "generated_at": now(),
        "project": project,
        "phase": args.phase,
        "wave": wave,
        "search_roots": [str(path) for path in search_roots],
        "verdict": verdict,
        "coverage_mode": coverage_mode,
        "reason": reason,
        "issues": issues,
        "checks": checks,
        "project_briefs": [serialize_record(record) for record in project_briefs],
        "phase_briefs_for_phase": [serialize_record(record) for record in phase_briefs_all],
        "applicable_phase_briefs": [serialize_record(record) for record in applicable_phase_briefs],
    }


def render_markdown(report: dict) -> str:
    lines = [
        f"# Wave Brief Coverage — {report['project']}",
        "",
        f"- Generated: {report['generated_at']}",
        f"- Phase: {report['phase']}",
        f"- Wave: {report['wave']}",
        f"- Verdict: {report['verdict']}",
        f"- Coverage mode: {report.get('coverage_mode') or 'N/A'}",
        f"- Reason: {report['reason']}",
        "",
        "## Checks",
        "",
    ]
    for check in report["checks"]:
        status = "PASS" if check["ok"] else "FAIL"
        lines.append(f"- [{status}] `{check['name']}` — {check['detail']}")

    for key, heading in (
        ("project_briefs", "Project Briefs"),
        ("phase_briefs_for_phase", "Phase Briefs For This Phase"),
        ("applicable_phase_briefs", "Applicable Phase Briefs For Target Wave"),
    ):
        lines.extend(["", f"## {heading}", ""])
        entries = report.get(key) or []
        if not entries:
            lines.append("- None")
            continue
        for entry in entries:
            detail_bits = []
            if entry.get("phase") is not None:
                detail_bits.append(f"phase {entry['phase']}")
            if entry.get("covered_waves"):
                detail_bits.append("covered_waves=" + ",".join(entry["covered_waves"]))
            detail_text = f" ({'; '.join(detail_bits)})" if detail_bits else ""
            lines.append(f"- `{entry['title']}`{detail_text} → `{entry['path']}`")
    return "\n".join(lines).rstrip() + "\n"


def write_output(path: str | None, content: str) -> None:
    if not path:
        return
    target = Path(path).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def main() -> int:
    args = parse_args()
    report = build_report(args)
    write_output(args.json_out, json.dumps(report, indent=2, sort_keys=True) + "\n")
    write_output(args.markdown_out, render_markdown(report))
    return 0 if report["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
