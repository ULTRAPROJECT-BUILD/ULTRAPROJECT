#!/usr/bin/env python3
"""
Plan QA mechanical pre-check — enforces the Plan QA rubric letter-for-letter.

This is the structural compliance floor that runs BEFORE the model-graded gate
review. The cross-context reviewer (especially in chat_native single-host mode)
tends to classify mechanical compliance gaps as "non-blocking tightening" — this
script removes that decision from the model entirely.

Checks (the rubric items NOT already covered by check_quality_contract.py):

- Required structural sections present: Architecture Decisions, Phases, plus
  frontier-specific Playbook Usage Contract and Why This Cannot Just Be The Playbook.
- For execution_model: capability-waves: Capability Register and Dynamic Wave Log present.
- Reverse trace coverage: every WS-N referenced in the Goal Workstreams table has at
  least one [TRACES: WS-N] tag in some phase exit criterion (rubric dim 7).
- Exit criteria taxonomy: every line that looks like an exit criterion (under a Phase
  block) carries one of [EXECUTABLE], [INFRASTRUCTURE-DEPENDENT], or [MANUAL].
- [PARTIAL-COVERAGE] enforcement (rubric dim 8): if the Goal Contract's Partial-coverage
  rule field references WS-N IDs, those workstreams' exit-criteria lines must carry
  the literal [PARTIAL-COVERAGE] tag.
- Frontier reuse mode is pattern_only (rubric dim 11).

Exits non-zero on any violation. Emits JSON + Markdown reports.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from check_quality_contract import (
    build_check,
    extract_section,
    extract_traces,
    parse_labeled_bullets,
    parse_markdown_table_text,
    split_frontmatter,
)
from check_ticket_evidence import parse_frontmatter_map

TIMESTAMP_FMT = "%Y-%m-%dT%H:%M:%S"
WS_RE = re.compile(r"\bWS-\d+\b", re.IGNORECASE)
TRACE_RE = re.compile(r"\[TRACES:\s*([^\]]+)\]", re.IGNORECASE)
# Taxonomy tags may carry an optional inline qualifier after a dash/colon, e.g.
# [INFRASTRUCTURE-DEPENDENT — display server required] or [MANUAL: human review].
TAXONOMY_TAG_RE = re.compile(
    r"\[(EXECUTABLE|INFRASTRUCTURE-DEPENDENT|MANUAL)(?:\s*[—\-:][^\]]*)?\]",
    re.IGNORECASE,
)
PARTIAL_COVERAGE_TAG_RE = re.compile(r"\[PARTIAL-COVERAGE\]", re.IGNORECASE)
PHASE_HEADING_RE = re.compile(r"^###\s+Phase\s+(\d+)", re.IGNORECASE | re.MULTILINE)


def now() -> str:
    return datetime.now().astimezone().strftime(TIMESTAMP_FMT)


def normalize_ws_id(value: str) -> str:
    """Normalize a workstream identifier to canonical 'WS-N' form."""
    match = WS_RE.search(value or "")
    if not match:
        return ""
    return match.group(0).upper().replace(" ", "")


def workstream_ids_from_table(rows: list[dict[str, str]]) -> set[str]:
    """Extract canonical WS-N IDs from the Goal Workstreams table."""
    ids: set[str] = set()
    for row in rows:
        # Try the canonical column first, then any cell.
        candidate = row.get("Goal / Workstream", "")
        ws_id = normalize_ws_id(candidate)
        if not ws_id:
            for cell in row.values():
                ws_id = normalize_ws_id(cell)
                if ws_id:
                    break
        if ws_id:
            ids.add(ws_id)
    return ids


def trace_ids_from_body(body: str) -> set[str]:
    """Extract every WS-N referenced inside any [TRACES: ...] tag in the body."""
    ids: set[str] = set()
    for raw in TRACE_RE.findall(body):
        for chunk in raw.split(","):
            ws_id = normalize_ws_id(chunk)
            if ws_id:
                ids.add(ws_id)
            # Range syntax like "WS-1..WS-7" expands to all in between.
            range_match = re.match(
                r"\s*WS-(\d+)\s*\.\.\s*WS-(\d+)\s*", chunk, re.IGNORECASE
            )
            if range_match:
                lo, hi = int(range_match.group(1)), int(range_match.group(2))
                for n in range(min(lo, hi), max(lo, hi) + 1):
                    ids.add(f"WS-{n}")
    return ids


def partial_coverage_workstreams(goal_fields: dict[str, str]) -> set[str]:
    """Workstreams referenced in the Goal Contract's Partial-coverage rule field."""
    text = goal_fields.get("partial-coverage rule", "") or ""
    return {match.group(0).upper() for match in WS_RE.finditer(text)}


def lines_with_trace(body: str, ws_id: str) -> list[str]:
    """Return body lines whose [TRACES: ...] tag references ws_id."""
    matches: list[str] = []
    for line in body.splitlines():
        for raw in TRACE_RE.findall(line):
            ids: set[str] = set()
            for chunk in raw.split(","):
                norm = normalize_ws_id(chunk)
                if norm:
                    ids.add(norm)
                range_match = re.match(
                    r"\s*WS-(\d+)\s*\.\.\s*WS-(\d+)\s*", chunk, re.IGNORECASE
                )
                if range_match:
                    lo, hi = int(range_match.group(1)), int(range_match.group(2))
                    for n in range(min(lo, hi), max(lo, hi) + 1):
                        ids.add(f"WS-{n}")
            if ws_id in ids:
                matches.append(line)
                break
    return matches


def exit_criteria_lines_in_phases(body: str) -> list[tuple[int, str]]:
    """
    Return (line_number, line_text) for every line that looks like an exit
    criterion under a Phase heading. Heuristic: bullet lines (starting with '-')
    inside a section that starts with '**Exit criteria:**' below a Phase heading.
    """
    lines = body.splitlines()
    out: list[tuple[int, str]] = []
    in_phase = False
    in_exit_criteria = False
    for idx, line in enumerate(lines, start=1):
        if PHASE_HEADING_RE.match(line):
            in_phase = True
            in_exit_criteria = False
            continue
        if not in_phase:
            continue
        # Section header like ### or ## ends the current phase block.
        if re.match(r"^##\s+", line) or re.match(r"^###\s+", line):
            if not PHASE_HEADING_RE.match(line):
                in_phase = False
                in_exit_criteria = False
                continue
        stripped = line.strip()
        if stripped.startswith("**Exit criteria:**"):
            in_exit_criteria = True
            continue
        # Any new bold-labeled line ends the exit-criteria block within the phase.
        if in_exit_criteria and stripped.startswith("**") and stripped != "**Exit criteria:**":
            in_exit_criteria = False
            continue
        if in_exit_criteria and stripped.startswith("-"):
            out.append((idx, stripped))
    return out


def line_has_taxonomy_tag(line: str) -> bool:
    return bool(TAXONOMY_TAG_RE.search(line))


def line_has_partial_coverage_tag(line: str) -> bool:
    return bool(PARTIAL_COVERAGE_TAG_RE.search(line))


def partial_coverage_field_has_content(goal_fields: dict[str, str]) -> bool:
    """True when the Partial-coverage rule field has substantive content.

    'None' or empty/whitespace counts as no content; anything else (prose
    naming a workstream, an explanation, etc.) means the plan author has
    declared that some workstream is being met at less than full scope.
    """
    text = (goal_fields.get("partial-coverage rule", "") or "").strip()
    if not text:
        return False
    # Accept conventional empty markers.
    return text.lower() not in {"none", "n/a", "na", "—", "-"}


def validate_plan_compliance(plan_path: Path) -> dict[str, Any]:
    plan_text = plan_path.read_text(encoding="utf-8")
    plan_frontmatter = parse_frontmatter_map(plan_path)
    _, plan_body = split_frontmatter(plan_text)

    tags = plan_frontmatter.get("tags") or []
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.strip("[]").split(",") if t.strip()]
    is_frontier = any("frontier" in str(t).lower() for t in tags)
    execution_model = str(plan_frontmatter.get("execution_model") or "").strip().lower()
    is_capability_waves = execution_model == "capability-waves"

    checks: list[dict[str, Any]] = []

    # 1. Required core sections.
    core_sections = ["Architecture Decisions", "Goal Contract", "Assumption Register", "Phases"]
    for section in core_sections:
        present = bool(extract_section(plan_body, section).strip())
        checks.append(
            build_check(
                f"section_{section.lower().replace(' ', '_')}_present",
                present,
                f"## {section} section present." if present else f"Missing required ## {section} section.",
            )
        )

    # 2. Frontier-specific sections.
    if is_frontier:
        for section in ["Playbook Usage Contract", "Why This Cannot Just Be The Playbook"]:
            present = bool(extract_section(plan_body, section).strip())
            checks.append(
                build_check(
                    f"frontier_section_{section.lower().replace(' ', '_').replace('/', '_')}_present",
                    present,
                    f"## {section} section present (required for frontier projects)."
                    if present
                    else f"Frontier projects must include ## {section} section.",
                )
            )

        # Reuse mode must be pattern_only for frontier (rubric dim 11).
        playbook_section = extract_section(plan_body, "Playbook Usage Contract")
        is_pattern_only = "pattern_only" in playbook_section.lower()
        checks.append(
            build_check(
                "frontier_reuse_mode_pattern_only",
                is_pattern_only,
                "Frontier project caps reuse mode at pattern_only."
                if is_pattern_only
                else "Frontier projects must declare reuse mode pattern_only in Playbook Usage Contract.",
            )
        )

    # 3. Capability-waves structural sections.
    if is_capability_waves:
        for section in ["Capability Register", "Dynamic Wave Log"]:
            present = bool(extract_section(plan_body, section).strip())
            checks.append(
                build_check(
                    f"capability_waves_section_{section.lower().replace(' ', '_')}_present",
                    present,
                    f"## {section} section present (required for capability-waves execution model)."
                    if present
                    else f"capability-waves projects must include ## {section} section.",
                )
            )

    # 4. Reverse trace coverage (rubric dim 7).
    goal_section = extract_section(plan_body, "Goal Contract")
    workstream_rows = parse_markdown_table_text(goal_section)
    declared_ws = workstream_ids_from_table(workstream_rows)
    traced_ws = trace_ids_from_body(plan_body)
    untraced = sorted(declared_ws - traced_ws)
    checks.append(
        build_check(
            "reverse_trace_coverage",
            not untraced,
            "Every workstream has at least one [TRACES: WS-N] tag in some phase exit criterion."
            if not untraced
            else f"Workstreams declared but not traced in any phase exit criterion: {', '.join(untraced)}",
        )
    )

    # 5. Exit criteria taxonomy tags (rubric dim 4).
    exit_lines = exit_criteria_lines_in_phases(plan_body)
    untagged = [(num, line) for num, line in exit_lines if not line_has_taxonomy_tag(line)]
    checks.append(
        build_check(
            "exit_criteria_taxonomy_tags",
            not untagged,
            f"All {len(exit_lines)} exit criteria carry [EXECUTABLE]/[INFRASTRUCTURE-DEPENDENT]/[MANUAL] taxonomy tags."
            if not untagged
            else "Exit criteria missing taxonomy tag ([EXECUTABLE]/[INFRASTRUCTURE-DEPENDENT]/[MANUAL]): "
            + "; ".join(f"line {num}: {line[:80]}" for num, line in untagged[:5])
            + ("..." if len(untagged) > 5 else ""),
        )
    )

    # 6. [PARTIAL-COVERAGE] tag enforcement (rubric dim 8).
    # Two-tier check:
    #   (a) Strict: if the Partial-coverage rule field references WS-N IDs, each
    #       must have at least one exit criterion line with [PARTIAL-COVERAGE].
    #   (b) Fallback: if the field has substantive prose content but no WS-N IDs
    #       (e.g., refers to workstreams by prose name), require AT LEAST one
    #       [PARTIAL-COVERAGE] tag somewhere in the phases. This catches plans
    #       that describe partial coverage in prose without the literal tag.
    goal_fields = parse_labeled_bullets(goal_section)
    partial_ws = partial_coverage_workstreams(goal_fields)
    has_partial_field = partial_coverage_field_has_content(goal_fields)

    if partial_ws:
        # Strict per-WS check.
        missing_partial_tag: list[str] = []
        for ws_id in sorted(partial_ws):
            trace_lines = lines_with_trace(plan_body, ws_id)
            if not trace_lines:
                # Already caught by reverse_trace_coverage; don't double-count.
                continue
            if not any(line_has_partial_coverage_tag(line) for line in trace_lines):
                missing_partial_tag.append(ws_id)
        checks.append(
            build_check(
                "partial_coverage_tag_per_workstream",
                not missing_partial_tag,
                f"All workstreams in Partial-coverage rule ({', '.join(sorted(partial_ws))}) "
                "have at least one exit criterion line carrying [PARTIAL-COVERAGE]."
                if not missing_partial_tag
                else "Workstreams declared as partial-coverage in Goal Contract must carry literal [PARTIAL-COVERAGE] "
                f"on at least one [TRACES: WS-N] exit criterion. Missing: {', '.join(missing_partial_tag)}",
            )
        )
    elif has_partial_field:
        # Fallback: prose names instead of WS-N IDs in the field. Require at
        # least one [PARTIAL-COVERAGE] tag anywhere in the phases.
        any_tagged = bool(PARTIAL_COVERAGE_TAG_RE.search(plan_body))
        checks.append(
            build_check(
                "partial_coverage_tag_present",
                any_tagged,
                "Partial-coverage rule has content and at least one exit criterion carries [PARTIAL-COVERAGE]."
                if any_tagged
                else "Goal Contract declares partial coverage in prose but no exit criterion carries [PARTIAL-COVERAGE]. "
                "Either add the literal [PARTIAL-COVERAGE] tag to the relevant exit criterion lines, "
                "or rewrite the Partial-coverage rule field to reference workstreams by WS-N ID for stricter checking.",
            )
        )

    return {
        "is_frontier": is_frontier,
        "is_capability_waves": is_capability_waves,
        "declared_workstreams": sorted(declared_ws),
        "traced_workstreams": sorted(traced_ws),
        "partial_coverage_workstreams": sorted(partial_ws),
        "exit_criteria_count": len(exit_lines),
        "checks": checks,
    }


def render_markdown(report: dict[str, Any], plan_path: Path) -> str:
    lines = [
        f"# Plan Compliance Report — {plan_path.name}",
        "",
        f"_Generated: {now()}_",
        "",
        f"- Frontier project: {report['is_frontier']}",
        f"- Capability-waves: {report['is_capability_waves']}",
        f"- Declared workstreams: {', '.join(report['declared_workstreams']) or '(none)'}",
        f"- Traced workstreams: {', '.join(report['traced_workstreams']) or '(none)'}",
        f"- Partial-coverage workstreams: {', '.join(report['partial_coverage_workstreams']) or '(none)'}",
        f"- Exit criteria scanned: {report['exit_criteria_count']}",
        "",
        "## Checks",
        "",
    ]
    for check in report["checks"]:
        marker = "✅" if check["ok"] else "❌"
        lines.append(f"- {marker} **{check['name']}** — {check['details']}")
    failures = [c for c in report["checks"] if not c["ok"]]
    lines.extend(["", f"**Verdict:** {'PASS' if not failures else f'FAIL — {len(failures)} violation(s)'}"])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True, help="Path to the project plan markdown file.")
    parser.add_argument("--json-out", help="Optional JSON output path.")
    parser.add_argument("--markdown-out", help="Optional markdown output path.")
    args = parser.parse_args()

    plan_path = Path(args.plan).resolve()
    if not plan_path.is_file():
        print(f"error: plan not found at {plan_path}", file=sys.stderr)
        return 2

    report = validate_plan_compliance(plan_path)
    failures = [c for c in report["checks"] if not c["ok"]]

    if args.json_out:
        out = {"ok": not failures, "plan": str(plan_path), "report": report, "generated": now()}
        Path(args.json_out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json_out).write_text(json.dumps(out, indent=2), encoding="utf-8")

    if args.markdown_out:
        Path(args.markdown_out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.markdown_out).write_text(render_markdown(report, plan_path), encoding="utf-8")

    # Always print the markdown to stdout so callers see the result without --markdown-out.
    print(render_markdown(report, plan_path))

    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
