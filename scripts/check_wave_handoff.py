#!/usr/bin/env python3
"""
Mechanical wave closeout / handoff check for capability-wave phases.

This is intentionally lighter than a phase gate. It answers:
1. Is the closing wave actually done?
2. Is the next wave safe to start immediately, or does it need a brief supplement first?

Verdict meanings:
- PASS + GREEN: close the wave and start the next wave normally.
- PASS + YELLOW: close the wave, but only start the next wave behind a supplement brief.
- FAIL + RED: the current wave is not actually closeable yet.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from check_brief_gate import build_report as build_brief_gate_report
from check_ticket_evidence import parse_frontmatter_map
from check_wave_brief_coverage import build_report as build_wave_brief_coverage_report
from resolve_briefs import normalize_wave_label

TIMESTAMP_FMT = "%Y-%m-%dT%H:%M:%S"
TICKET_ID_RE = re.compile(r"\bT-\d+\b", re.IGNORECASE)
PHASE_RE = re.compile(r"\bphase\s+(\d+)\b", re.IGNORECASE)
TERMINAL_STATUSES = {"closed", "done"}
NON_TERMINAL_WAVE_STATUSES = {"planned", "active", "open", "pending", "ready"}


def now() -> str:
    return datetime.now().astimezone().strftime(TIMESTAMP_FMT)


def normalize_text(value: object) -> str:
    return str(value or "").strip()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-plan", required=True, help="Project plan markdown path.")
    parser.add_argument("--tickets-dir", required=True, help="Tickets directory for the project.")
    parser.add_argument("--phase", required=True, type=int, help="Anchor phase whose wave handoff is being checked.")
    parser.add_argument("--closing-wave", help="Wave being closed. Defaults to the active wave in the plan.")
    parser.add_argument("--next-wave", help="Optional next wave to activate. Defaults to the next same-phase planned wave in the plan.")
    parser.add_argument(
        "--search-root",
        action="append",
        default=[],
        help="Optional creative-brief snapshot roots to scan. May be repeated.",
    )
    parser.add_argument("--json-out", help="Optional JSON output path.")
    parser.add_argument("--markdown-out", help="Optional markdown output path.")
    return parser.parse_args()


def write_output(path: str | None, content: str) -> None:
    if not path:
        return
    target = Path(path).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def extract_section_lines(text: str, heading: str) -> list[str]:
    lines = text.splitlines()
    target = heading.strip()
    capturing = False
    collected: list[str] = []
    for line in lines:
        if line.strip() == target:
            capturing = True
            continue
        if capturing and line.startswith("## "):
            break
        if capturing:
            collected.append(line.rstrip("\n"))
    return collected


def parse_markdown_table(lines: list[str]) -> tuple[list[str], list[list[str]]]:
    table_lines = [line.strip() for line in lines if line.strip().startswith("|")]
    if len(table_lines) < 2:
        return [], []
    header = [cell.strip() for cell in table_lines[0].strip("|").split("|")]
    rows: list[list[str]] = []
    for raw in table_lines[1:]:
        if set(raw.replace("|", "").strip()) <= {"-", ":"}:
            continue
        rows.append([cell.strip() for cell in raw.strip("|").split("|")])
    return header, rows


def normalize_header(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")


def parse_wave_phase(value: str) -> int | None:
    text = normalize_text(value)
    if not text:
        return None
    match = PHASE_RE.search(text)
    if match:
        return int(match.group(1))
    if text.isdigit():
        return int(text)
    return None


def parse_ticket_refs(value: str) -> list[str]:
    return list(dict.fromkeys(match.group(0).upper() for match in TICKET_ID_RE.finditer(value or "")))


def load_wave_rows(plan_path: Path) -> list[dict[str, object]]:
    body = plan_path.read_text(encoding="utf-8")
    wave_lines = extract_section_lines(body, "## Dynamic Wave Log")
    if not wave_lines:
        wave_lines = extract_section_lines(body, "## Dynamic Waves")
    header, rows = parse_markdown_table(wave_lines)
    if not header:
        return []
    cols = {normalize_header(name): idx for idx, name in enumerate(header)}

    def row_value(row: list[str], *keys: str) -> str:
        for key in keys:
            idx = cols.get(key)
            if idx is not None and idx < len(row):
                return row[idx].strip()
        return ""

    parsed: list[dict[str, object]] = []
    for position, row in enumerate(rows):
        name = normalize_wave_label(row_value(row, "wave", "name"))
        if not name:
            continue
        parsed.append(
            {
                "name": name,
                "status": normalize_text(row_value(row, "status")).lower(),
                "anchor_phase": parse_wave_phase(row_value(row, "anchor_phase", "phase")),
                "tickets": parse_ticket_refs(row_value(row, "tickets")),
                "success_signal": row_value(row, "success_signal", "success"),
                "capability_lanes": row_value(row, "capability_lanes", "capabilities"),
                "position": position,
            }
        )
    return parsed


def infer_project_slug(plan_path: Path) -> str:
    fm = parse_frontmatter_map(plan_path)
    explicit = normalize_text(fm.get("project"))
    if explicit:
        return explicit
    stem = plan_path.stem
    stem = re.sub(r"^\d{4}-\d{2}-\d{2}-", "", stem)
    stem = re.sub(r"^project-plan-", "", stem)
    return stem


def index_ticket_metadata(tickets_dir: Path) -> dict[str, dict[str, str]]:
    index: dict[str, dict[str, str]] = {}
    for path in tickets_dir.rglob("*.md"):
        fm = parse_frontmatter_map(path)
        ticket_id = normalize_text(fm.get("id")).upper()
        if not ticket_id:
            match = TICKET_ID_RE.search(path.stem.upper())
            if match:
                ticket_id = match.group(0).upper()
        if not ticket_id:
            continue
        index[ticket_id] = {
            "path": str(path.resolve()),
            "status": normalize_text(fm.get("status")).lower(),
            "task_type": normalize_text(fm.get("task_type")).lower(),
            "title": normalize_text(fm.get("title")),
        }
    return index


def classify_wave_coverage_failure(report: dict) -> str:
    issues = set(report.get("issues") or [])
    if "active_wave_not_covered_by_phase_brief" in issues:
        return "missing_wave_supplement"
    return "hard_failure"


def summarize_brief_gate_report(report: dict) -> str:
    if report.get("verdict") == "PASS":
        return "fresh passing brief gate found"
    failing_checks = [check for check in (report.get("checks") or []) if not check.get("ok")]
    if failing_checks:
        return "; ".join(str(check.get("details") or check.get("name") or "").strip() for check in failing_checks if str(check.get("details") or check.get("name") or "").strip())
    selection_reason = normalize_text(report.get("selection_reason"))
    return selection_reason or "brief gate failed"


def build_report(args: argparse.Namespace) -> dict:
    plan_path = Path(args.project_plan).expanduser().resolve()
    tickets_dir = Path(args.tickets_dir).expanduser().resolve()
    project = infer_project_slug(plan_path)
    wave_rows = load_wave_rows(plan_path)

    closing_wave = normalize_wave_label(args.closing_wave)
    if not closing_wave:
        for row in wave_rows:
            if row.get("anchor_phase") == args.phase and row.get("status") == "active":
                closing_wave = str(row["name"])
                break

    closing_row = next(
        (
            row
            for row in wave_rows
            if row.get("anchor_phase") == args.phase and row.get("name") == closing_wave
        ),
        None,
    )

    next_wave = normalize_wave_label(args.next_wave)
    if not next_wave and closing_row is not None:
        for row in wave_rows:
            if row.get("anchor_phase") != args.phase:
                continue
            if int(row.get("position", -1)) <= int(closing_row.get("position", -1)):
                continue
            if str(row.get("status", "")).lower() in NON_TERMINAL_WAVE_STATUSES:
                next_wave = str(row["name"])
                break

    next_row = next(
        (
            row
            for row in wave_rows
            if row.get("anchor_phase") == args.phase and row.get("name") == next_wave
        ),
        None,
    )

    checks: list[dict[str, object]] = []
    issues: list[str] = []
    handoff_state = "GREEN"
    verdict = "PASS"
    reason = ""
    recommended_action = ""

    checks.append(
        {
            "name": "closing_wave_found",
            "ok": closing_row is not None,
            "detail": (
                f"Found closing wave {closing_wave} in phase {args.phase}."
                if closing_row is not None
                else f"Could not find closing wave for phase {args.phase}."
            ),
        }
    )
    if closing_row is None:
        verdict = "FAIL"
        handoff_state = "RED"
        issues.append("closing_wave_missing")
        reason = f"Cannot evaluate wave handoff without a closing wave row for phase {args.phase}."
        recommended_action = "Fix the Dynamic Wave Log before attempting a wave handoff."
        return {
            "generated_at": now(),
            "project": project,
            "phase": args.phase,
            "closing_wave": closing_wave,
            "next_wave": next_wave,
            "verdict": verdict,
            "handoff_state": handoff_state,
            "reason": reason,
            "recommended_action": recommended_action,
            "issues": issues,
            "checks": checks,
            "closing_wave_row": None,
            "next_wave_row": None,
            "ticket_statuses": [],
            "brief_gate_results": [],
            "next_wave_brief_coverage": None,
        }

    closing_tickets = list(closing_row.get("tickets") or [])
    checks.append(
        {
            "name": "closing_wave_has_tickets",
            "ok": bool(closing_tickets),
            "detail": (
                f"{len(closing_tickets)} ticket(s) attached to {closing_wave}."
                if closing_tickets
                else f"{closing_wave} has no ticket IDs in the Dynamic Wave Log."
            ),
        }
    )
    if not closing_tickets:
        verdict = "FAIL"
        handoff_state = "RED"
        issues.append("closing_wave_missing_ticket_refs")

    ticket_index = index_ticket_metadata(tickets_dir)
    ticket_statuses: list[dict[str, str]] = []
    missing_ticket_ids: list[str] = []
    non_terminal_ticket_ids: list[str] = []
    creative_brief_failures: list[dict[str, object]] = []

    for ticket_id in closing_tickets:
        metadata = ticket_index.get(ticket_id)
        if metadata is None:
            missing_ticket_ids.append(ticket_id)
            ticket_statuses.append({"id": ticket_id, "status": "missing", "task_type": "", "path": ""})
            continue
        ticket_statuses.append(
            {
                "id": ticket_id,
                "status": metadata["status"],
                "task_type": metadata["task_type"],
                "path": metadata["path"],
            }
        )
        if metadata["status"] not in TERMINAL_STATUSES:
            non_terminal_ticket_ids.append(ticket_id)
        if metadata["task_type"] == "creative_brief" and metadata["status"] in TERMINAL_STATUSES:
            brief_report = build_brief_gate_report(
                argparse.Namespace(
                    ticket_path=metadata["path"],
                    required_grade="A",
                    search_root=args.search_root,
                    json_out=None,
                    markdown_out=None,
                )
            )
            creative_brief_failures.append(
                {
                    "ticket_id": ticket_id,
                    "verdict": brief_report["verdict"],
                    "reason": summarize_brief_gate_report(brief_report),
                    "target_brief": brief_report.get("target_brief"),
                    "latest_review": brief_report.get("latest_review"),
                }
            )

    checks.append(
        {
            "name": "closing_wave_ticket_status",
            "ok": not missing_ticket_ids and not non_terminal_ticket_ids,
            "detail": (
                f"All {len(closing_tickets)} closing-wave tickets are closed."
                if not missing_ticket_ids and not non_terminal_ticket_ids
                else (
                    ("missing ticket files: " + ", ".join(missing_ticket_ids) + ". " if missing_ticket_ids else "")
                    + ("non-terminal tickets: " + ", ".join(non_terminal_ticket_ids) + "." if non_terminal_ticket_ids else "")
                ).strip()
            ),
        }
    )
    if missing_ticket_ids:
        verdict = "FAIL"
        handoff_state = "RED"
        issues.append("closing_wave_missing_ticket_files")
    if non_terminal_ticket_ids:
        verdict = "FAIL"
        handoff_state = "RED"
        issues.append("closing_wave_has_open_tickets")

    failed_brief_gates = [item for item in creative_brief_failures if item.get("verdict") != "PASS"]
    checks.append(
        {
            "name": "closing_wave_creative_brief_gates",
            "ok": not failed_brief_gates,
            "detail": (
                "All closing-wave creative briefs have a fresh passing brief gate."
                if not failed_brief_gates
                else "Creative brief gate failed for " + ", ".join(item["ticket_id"] for item in failed_brief_gates) + "."
            ),
        }
    )
    if failed_brief_gates:
        verdict = "FAIL"
        handoff_state = "RED"
        issues.append("closing_wave_brief_gate_failed")

    next_wave_coverage_report: dict | None = None
    if next_wave:
        checks.append(
            {
                "name": "next_wave_found",
                "ok": next_row is not None,
                "detail": (
                    f"Found next wave {next_wave} in phase {args.phase}."
                    if next_row is not None
                    else f"Could not find next wave {next_wave} in phase {args.phase}."
                ),
            }
        )
        if next_row is None:
            verdict = "FAIL"
            handoff_state = "RED"
            issues.append("next_wave_missing")
        else:
            next_wave_coverage_report = build_wave_brief_coverage_report(
                argparse.Namespace(
                    project=project,
                    project_file=None,
                    project_plan=str(plan_path),
                    phase=args.phase,
                    wave=next_wave,
                    search_root=args.search_root,
                    json_out=None,
                    markdown_out=None,
                )
            )
            coverage_ok = next_wave_coverage_report["verdict"] == "PASS"
            checks.append(
                {
                    "name": "next_wave_brief_coverage",
                    "ok": coverage_ok,
                    "detail": next_wave_coverage_report["reason"],
                }
            )
            if not coverage_ok:
                coverage_kind = classify_wave_coverage_failure(next_wave_coverage_report)
                if coverage_kind == "missing_wave_supplement" and verdict != "FAIL":
                    handoff_state = "YELLOW"
                    issues.append("next_wave_requires_supplement_brief")
                else:
                    verdict = "FAIL"
                    handoff_state = "RED"
                    issues.append("next_wave_brief_coverage_failed")
    else:
        checks.append(
            {
                "name": "next_wave_target",
                "ok": True,
                "detail": "No next wave specified or inferable; treat this as a wave closeout before phase-advance evaluation.",
            }
        )

    if verdict == "FAIL":
        if not reason:
            reason = f"{closing_wave} is not actually safe to hand off yet."
        recommended_action = "Keep the current wave active and remediate the failed checks before closing it."
        handoff_state = "RED"
    elif handoff_state == "YELLOW":
        reason = (
            f"{closing_wave} is closeable, but {next_wave} is not covered by the current phase brief stack yet."
        )
        recommended_action = (
            f"Close {closing_wave}, activate {next_wave}, and create a wave supplement creative brief before unblocking the new wave's build tickets."
        )
    elif next_wave:
        reason = f"{closing_wave} is closeable and {next_wave} is covered by the current brief stack."
        recommended_action = f"Close {closing_wave} and start {next_wave} normally."
    else:
        reason = f"{closing_wave} is closeable. No later wave is queued in phase {args.phase}, so this handoff is ready for phase-advance evaluation."
        recommended_action = "Close the wave and evaluate whether the anchor phase should advance."

    return {
        "generated_at": now(),
        "project": project,
        "phase": args.phase,
        "closing_wave": closing_wave,
        "next_wave": next_wave,
        "verdict": verdict,
        "handoff_state": handoff_state,
        "reason": reason,
        "recommended_action": recommended_action,
        "issues": issues,
        "checks": checks,
        "closing_wave_row": closing_row,
        "next_wave_row": next_row,
        "ticket_statuses": ticket_statuses,
        "brief_gate_results": creative_brief_failures,
        "next_wave_brief_coverage": next_wave_coverage_report,
    }


def render_markdown(report: dict) -> str:
    lines = [
        f"# Wave Handoff Check — {report['project']}",
        "",
        f"- Generated: {report['generated_at']}",
        f"- Phase: {report['phase']}",
        f"- Closing wave: {report.get('closing_wave') or 'N/A'}",
        f"- Next wave: {report.get('next_wave') or 'N/A'}",
        f"- Verdict: {report['verdict']}",
        f"- Handoff state: {report['handoff_state']}",
        f"- Reason: {report['reason']}",
        f"- Recommended action: {report['recommended_action']}",
        "",
        "## Checks",
        "",
    ]
    for check in report["checks"]:
        status = "PASS" if check["ok"] else "FAIL"
        lines.append(f"- [{status}] `{check['name']}` — {check['detail']}")

    lines.extend(["", "## Closing Wave Tickets", ""])
    if not report["ticket_statuses"]:
        lines.append("- None")
    else:
        for ticket in report["ticket_statuses"]:
            lines.append(
                f"- `{ticket['id']}` — status `{ticket['status']}`"
                + (f", task_type `{ticket['task_type']}`" if ticket.get("task_type") else "")
            )

    if report.get("brief_gate_results"):
        lines.extend(["", "## Creative Brief Gate Results", ""])
        for item in report["brief_gate_results"]:
            lines.append(f"- `{item['ticket_id']}` — {item['verdict']}: {item['reason']}")

    next_wave_coverage = report.get("next_wave_brief_coverage")
    if next_wave_coverage:
        lines.extend(["", "## Next Wave Brief Coverage", ""])
        lines.append(
            f"- Verdict: {next_wave_coverage['verdict']} ({next_wave_coverage.get('coverage_mode') or 'N/A'})"
        )
        lines.append(f"- Reason: {next_wave_coverage['reason']}")

    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    args = parse_args()
    report = build_report(args)
    write_output(args.json_out, json.dumps(report, indent=2, sort_keys=True) + "\n")
    write_output(args.markdown_out, render_markdown(report))
    return 0 if report["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
