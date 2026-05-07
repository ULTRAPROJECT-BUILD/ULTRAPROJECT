#!/usr/bin/env python3
"""
Validate the platform quality-primitives contract for a project plan and brief stack.

This script makes three platform-level primitives mechanically checkable:
- Goal Contract
- Assumption Register
- Proof Strategy

It is intentionally additive. Older artifacts may not include these sections yet,
so callers can choose when to enforce it. New planning/brief flows should treat a
failing report as a real revision blocker.
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

from check_ticket_evidence import parse_frontmatter_map

TIMESTAMP_FMT = "%Y-%m-%dT%H:%M:%S"
TRACE_RE = re.compile(r"\[TRACES:\s*([^\]]+)\]", re.IGNORECASE)
SECTION_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
BULLET_FIELD_RE = re.compile(r"^- \*\*(.+?):\*\*\s*(.+?)?\s*$")

GOAL_CONTRACT_FIELDS = (
    "Rigor tier",
    "Mission",
    "Primary evaluator",
    "Mission success",
    "Primary success metrics",
    "Primary risks",
    "Human-owned decisions",
    "Agent-owned execution",
    "Proof shape",
    "In scope",
    "Out of scope",
    "Partial-coverage rule",
)
GOAL_WORKSTREAM_COLUMNS = (
    "Goal / Workstream",
    "Type",
    "Priority",
    "Success Signal",
    "Evaluator",
    "Scale / Scope",
)
ASSUMPTION_COLUMNS = (
    "ID",
    "Assumption",
    "Category",
    "Risk",
    "Validation Method",
    "Owner",
    "Target Phase/Gate",
    "Status",
    "Evidence / Resolution",
)
PROOF_STRATEGY_FIELDS = (
    "Rigor tier",
    "Evaluator lens",
    "Proof posture",
    "Primary evidence modes",
    "False-pass risks",
    "Adversarial / skeptical checks",
    "Rehearsal lenses",
    "Drift sentinels",
    "Supplement trigger",
    "Gate impact",
)
VALID_RIGOR_TIERS = {"lightweight", "standard", "frontier"}
VALID_ASSUMPTION_STATUSES = {
    "open",
    "validating",
    "partial",
    "validated",
    "resolved",
    "accepted-risk",
    "deferred",
    "invalidated",
}
HIGH_RISK_VALUES = {"high", "critical"}
ACTIVE_ASSUMPTION_STATUSES = {"open", "validating", "partial"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-file", required=True, help="Project markdown path.")
    parser.add_argument("--project-plan", required=True, help="Project plan markdown path.")
    parser.add_argument("--brief", action="append", default=[], help="Brief path(s) to validate.")
    parser.add_argument("--json-out", help="Optional JSON output path.")
    parser.add_argument("--markdown-out", help="Optional markdown output path.")
    return parser.parse_args()


def now() -> str:
    return datetime.now().astimezone().strftime(TIMESTAMP_FMT)


def split_frontmatter(text: str) -> tuple[str, str]:
    if not text.startswith("---\n"):
        return "", text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return "", text
    return parts[1].strip(), parts[2].lstrip("\n")


def normalize_label(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def normalize_key(value: object) -> str:
    return normalize_label(value).rstrip(":")


def extract_section(body: str, heading: str) -> str:
    target = normalize_label(heading)
    matches = list(SECTION_RE.finditer(body))
    for index, match in enumerate(matches):
        if normalize_label(match.group(1)) != target:
            continue
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
        return body[start:end].strip()
    return ""


def parse_labeled_bullets(section_text: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    lines = section_text.splitlines()
    current_key: str | None = None
    current_value_lines: list[str] = []
    for raw_line in lines:
        line = raw_line.strip()
        match = BULLET_FIELD_RE.match(line)
        if match:
            if current_key is not None:
                parsed[current_key] = "\n".join(current_value_lines).strip()
            current_key = normalize_key(match.group(1))
            inline_val = (match.group(2) or "").strip()
            current_value_lines = [inline_val] if inline_val else []
        elif current_key is not None and raw_line.startswith("  "):
            current_value_lines.append(line)
    if current_key is not None:
        parsed[current_key] = "\n".join(current_value_lines).strip()
    return parsed


def parse_markdown_table_text(text: str) -> list[dict[str, str]]:
    lines = text.splitlines()
    table_lines: list[str] = []
    started = False
    for raw in lines:
        line = raw.rstrip()
        if not line and started:
            break
        if line.startswith("|"):
            started = True
            table_lines.append(line)
        elif started:
            break
    if len(table_lines) < 2:
        return []
    headers = [cell.strip() for cell in table_lines[0].strip("|").split("|")]
    rows: list[dict[str, str]] = []
    for raw in table_lines[2:]:
        cells = [cell.strip() for cell in raw.strip("|").split("|")]
        if len(cells) != len(headers):
            continue
        rows.append({headers[idx]: cells[idx] for idx in range(len(headers))})
    return rows


def extract_traces(plan_body: str) -> list[str]:
    traces: list[str] = []
    for match in TRACE_RE.finditer(plan_body):
        values = match.group(1).split(",")
        traces.extend(value.strip() for value in values if value.strip())
    deduped: list[str] = []
    seen: set[str] = set()
    for trace in traces:
        norm = normalize_label(trace)
        if not norm or norm in seen:
            continue
        seen.add(norm)
        deduped.append(trace.strip())
    return deduped


def infer_rigor_tier(project_frontmatter: dict[str, Any], plan_frontmatter: dict[str, Any], fields: dict[str, str]) -> str | None:
    explicit = normalize_label(fields.get("rigor tier"))
    if explicit:
        return explicit
    execution_model = normalize_label(plan_frontmatter.get("execution_model"))
    raw_tags = project_frontmatter.get("tags") or []
    if isinstance(raw_tags, str):
        raw_tags = [raw_tags]
    tags = {normalize_label(tag) for tag in raw_tags}
    if execution_model == "capability-waves" or "admin-priority" in tags or "frontier" in tags:
        return "frontier"
    if normalize_label(project_frontmatter.get("status")) == "planning":
        return "standard"
    return None


def goal_labels_from_rows(rows: list[dict[str, str]]) -> list[str]:
    labels = [row.get("Goal / Workstream", "").strip() for row in rows if row.get("Goal / Workstream", "").strip()]
    deduped: list[str] = []
    seen: set[str] = set()
    for label in labels:
        norm = normalize_label(label)
        if not norm or norm in seen:
            continue
        seen.add(norm)
        deduped.append(label)
    return deduped


def trace_is_covered(trace: str, goal_labels: list[str]) -> bool:
    normalized_trace = normalize_label(trace)
    for label in goal_labels:
        normalized_label = normalize_label(label)
        if normalized_trace == normalized_label or normalized_trace in normalized_label or normalized_label in normalized_trace:
            return True
    return False


def build_check(name: str, ok: bool, details: str) -> dict[str, Any]:
    return {"name": name, "ok": ok, "details": details}


def validate_plan(project_file: Path, plan_path: Path) -> dict[str, Any]:
    project_frontmatter = parse_frontmatter_map(project_file)
    plan_text = plan_path.read_text(encoding="utf-8")
    plan_frontmatter = parse_frontmatter_map(plan_path)
    _, plan_body = split_frontmatter(plan_text)

    goal_contract_section = extract_section(plan_body, "Goal Contract")
    assumption_section = extract_section(plan_body, "Assumption Register")
    goal_fields = parse_labeled_bullets(goal_contract_section)
    goal_rows = parse_markdown_table_text(goal_contract_section)
    assumption_rows = parse_markdown_table_text(assumption_section)
    rigor_tier = infer_rigor_tier(project_frontmatter, plan_frontmatter, goal_fields)
    traces = extract_traces(plan_body)
    goal_labels = goal_labels_from_rows(goal_rows)

    checks: list[dict[str, Any]] = []
    checks.append(
        build_check(
            "goal_contract_present",
            bool(goal_contract_section),
            "Goal Contract section present." if goal_contract_section else "Missing ## Goal Contract section.",
        )
    )
    missing_goal_fields = [
        field for field in GOAL_CONTRACT_FIELDS if normalize_key(field) not in goal_fields
    ]
    checks.append(
        build_check(
            "goal_contract_fields",
            not missing_goal_fields,
            "Goal Contract fields complete."
            if not missing_goal_fields
            else f"Missing Goal Contract fields: {', '.join(missing_goal_fields)}",
        )
    )
    checks.append(
        build_check(
            "goal_contract_rigor_tier",
            rigor_tier in VALID_RIGOR_TIERS,
            f"Rigor tier: {rigor_tier or 'missing'}" if rigor_tier in VALID_RIGOR_TIERS else "Goal Contract is missing a valid rigor tier.",
        )
    )
    checks.append(
        build_check(
            "goal_contract_ownership_split",
            bool(goal_fields.get("human-owned decisions", "").strip()) and bool(goal_fields.get("agent-owned execution", "").strip()),
            "Goal Contract defines a real human/agent ownership split."
            if goal_fields.get("human-owned decisions", "").strip() and goal_fields.get("agent-owned execution", "").strip()
            else "Goal Contract must define both Human-owned decisions and Agent-owned execution.",
        )
    )
    checks.append(
        build_check(
            "goal_contract_success_metrics",
            bool(goal_fields.get("primary success metrics", "").strip()),
            "Goal Contract defines primary success metrics."
            if goal_fields.get("primary success metrics", "").strip()
            else "Goal Contract must define primary success metrics.",
        )
    )
    checks.append(
        build_check(
            "goal_contract_proof_shape",
            bool(goal_fields.get("proof shape", "").strip()),
            "Goal Contract defines the expected proof shape."
            if goal_fields.get("proof shape", "").strip()
            else "Goal Contract must define the expected proof shape.",
        )
    )
    checks.append(
        build_check(
            "goal_contract_primary_risks",
            bool(goal_fields.get("primary risks", "").strip()),
            "Goal Contract identifies primary risks."
            if goal_fields.get("primary risks", "").strip()
            else "Goal Contract must identify primary risks.",
        )
    )
    missing_goal_columns = [
        column for column in GOAL_WORKSTREAM_COLUMNS if not goal_rows or column not in goal_rows[0]
    ]
    checks.append(
        build_check(
            "goal_workstreams_table",
            bool(goal_rows) and not missing_goal_columns,
            "Goal Workstreams table present."
            if goal_rows and not missing_goal_columns
            else "Goal Contract must include a Goal Workstreams table with the required columns.",
        )
    )
    checks.append(
        build_check(
            "goal_workstreams_nonempty",
            bool(goal_labels),
            "Goal Workstreams table has labeled rows." if goal_labels else "Goal Workstreams table has no usable rows.",
        )
    )
    uncovered_traces = [trace for trace in traces if not trace_is_covered(trace, goal_labels)]
    checks.append(
        build_check(
            "trace_coverage",
            not uncovered_traces,
            "All [TRACES:] labels map back to Goal Workstreams."
            if not uncovered_traces
            else f"Uncovered [TRACES:] labels: {', '.join(uncovered_traces)}",
        )
    )

    checks.append(
        build_check(
            "assumption_register_present",
            bool(assumption_section),
            "Assumption Register section present." if assumption_section else "Missing ## Assumption Register section.",
        )
    )
    missing_assumption_columns = [
        column for column in ASSUMPTION_COLUMNS if not assumption_rows or column not in assumption_rows[0]
    ]
    checks.append(
        build_check(
            "assumption_register_columns",
            bool(assumption_rows) and not missing_assumption_columns,
            "Assumption Register table present."
            if assumption_rows and not missing_assumption_columns
            else "Assumption Register must include the required columns.",
        )
    )
    has_assumptions = bool(assumption_rows)
    checks.append(
        build_check(
            "assumption_register_nonempty",
            has_assumptions,
            "Assumption Register has rows." if has_assumptions else "Assumption Register has no rows.",
        )
    )

    invalid_status_rows = [
        row.get("ID", "?")
        for row in assumption_rows
        if normalize_label(row.get("Status")) not in VALID_ASSUMPTION_STATUSES
    ]
    checks.append(
        build_check(
            "assumption_status_values",
            not invalid_status_rows,
            "Assumption statuses are valid."
            if not invalid_status_rows
            else f"Assumptions with invalid status: {', '.join(invalid_status_rows)}",
        )
    )

    high_risk_gaps = [
        row.get("ID", "?")
        for row in assumption_rows
        if normalize_label(row.get("Risk")) in HIGH_RISK_VALUES
        and (
            not row.get("Validation Method", "").strip()
            or not row.get("Target Phase/Gate", "").strip()
        )
    ]
    checks.append(
        build_check(
            "high_risk_assumptions_actionable",
            not high_risk_gaps,
            "High-risk assumptions have validation and gate targets."
            if not high_risk_gaps
            else f"High-risk assumptions missing validation/target: {', '.join(high_risk_gaps)}",
        )
    )

    if rigor_tier == "frontier":
        active_rows = [
            row
            for row in assumption_rows
            if normalize_label(row.get("Status")) in ACTIVE_ASSUMPTION_STATUSES
        ]
        checks.append(
            build_check(
                "frontier_assumptions_explicit",
                bool(active_rows),
                "Frontier plan has explicit unresolved assumptions."
                if active_rows
                else "Frontier plans must surface at least one explicit unresolved/validating assumption or consciously downgrade the rigor tier.",
            )
        )

    return {
        "goal_contract_fields": goal_fields,
        "goal_workstreams": goal_rows,
        "assumptions": assumption_rows,
        "rigor_tier": rigor_tier,
        "traces": traces,
        "checks": checks,
    }


def validate_brief(brief_path: Path, inherited_rigor_tier: str | None) -> dict[str, Any]:
    brief_text = brief_path.read_text(encoding="utf-8")
    brief_frontmatter = parse_frontmatter_map(brief_path)
    _, brief_body = split_frontmatter(brief_text)

    proof_strategy_section = extract_section(brief_body, "Proof Strategy")
    proof_fields = parse_labeled_bullets(proof_strategy_section)
    proof_rigor_tier = normalize_label(proof_fields.get("rigor tier")) or inherited_rigor_tier or ""

    checks: list[dict[str, Any]] = []
    checks.append(
        build_check(
            "proof_strategy_present",
            bool(proof_strategy_section),
            "Proof Strategy section present." if proof_strategy_section else "Missing ## Proof Strategy section.",
        )
    )
    missing_fields = [field for field in PROOF_STRATEGY_FIELDS if normalize_key(field) not in proof_fields]
    checks.append(
        build_check(
            "proof_strategy_fields",
            not missing_fields,
            "Proof Strategy fields complete."
            if not missing_fields
            else f"Missing Proof Strategy fields: {', '.join(missing_fields)}",
        )
    )
    checks.append(
        build_check(
            "proof_strategy_rigor_tier",
            proof_rigor_tier in VALID_RIGOR_TIERS,
            f"Proof Strategy rigor tier: {proof_rigor_tier}"
            if proof_rigor_tier in VALID_RIGOR_TIERS
            else "Proof Strategy is missing a valid rigor tier.",
        )
    )
    checks.append(
        build_check(
            "proof_strategy_rehearsal_lenses",
            bool(proof_fields.get("rehearsal lenses", "").strip()),
            "Proof Strategy defines rehearsal lenses."
            if proof_fields.get("rehearsal lenses", "").strip()
            else "Proof Strategy must define rehearsal lenses.",
        )
    )
    checks.append(
        build_check(
            "proof_strategy_drift_sentinels",
            bool(proof_fields.get("drift sentinels", "").strip()),
            "Proof Strategy defines drift sentinels."
            if proof_fields.get("drift sentinels", "").strip()
            else "Proof Strategy must define drift sentinels.",
        )
    )
    checks.append(
        build_check(
            "proof_strategy_supplement_trigger",
            bool(proof_fields.get("supplement trigger", "").strip()),
            "Proof Strategy defines when a narrower phase/wave supplement is required."
            if proof_fields.get("supplement trigger", "").strip()
            else "Proof Strategy must define when a narrower phase or wave supplement is required.",
        )
    )

    if proof_rigor_tier == "frontier":
        adversarial = proof_fields.get("adversarial / skeptical checks", "").strip()
        checks.append(
            build_check(
                "frontier_proof_strategy_adversarial",
                bool(adversarial) and normalize_label(adversarial) not in {"none", "n/a", "not needed"},
                "Frontier brief has explicit adversarial/skeptical checks."
                if adversarial and normalize_label(adversarial) not in {"none", "n/a", "not needed"}
                else "Frontier proof strategy must define a real adversarial or skeptical check, not omit it.",
            )
        )

    return {
        "path": str(brief_path),
        "scope": normalize_label(brief_frontmatter.get("brief_scope") or "project"),
        "proof_strategy_fields": proof_fields,
        "rigor_tier": proof_rigor_tier or None,
        "checks": checks,
    }


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    project_file = Path(args.project_file).expanduser().resolve()
    plan_path = Path(args.project_plan).expanduser().resolve()
    plan_report = validate_plan(project_file, plan_path)
    brief_reports = [
        validate_brief(Path(raw).expanduser().resolve(), plan_report.get("rigor_tier"))
        for raw in args.brief
    ]

    all_checks = list(plan_report["checks"])
    for brief_report in brief_reports:
        for check in brief_report["checks"]:
            all_checks.append(
                {
                    **check,
                    "name": f"{Path(brief_report['path']).name}:{check['name']}",
                }
            )

    failed = [check for check in all_checks if not check["ok"]]
    verdict = "PASS" if not failed else "FAIL"
    return {
        "generated_at": now(),
        "project_file": str(project_file),
        "project_plan": str(plan_path),
        "verdict": verdict,
        "plan": plan_report,
        "briefs": brief_reports,
        "checks": all_checks,
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Quality Contract Report",
        "",
        f"- Generated: {report['generated_at']}",
        f"- Verdict: **{report['verdict']}**",
        f"- Project file: `{report['project_file']}`",
        f"- Project plan: `{report['project_plan']}`",
        "",
        "## Plan Checks",
        "",
    ]
    for check in report["plan"]["checks"]:
        prefix = "PASS" if check["ok"] else "FAIL"
        lines.append(f"- **{prefix}** `{check['name']}` — {check['details']}")

    if report.get("briefs"):
        lines.extend(["", "## Brief Checks", ""])
        for brief_report in report["briefs"]:
            lines.append(f"### `{Path(brief_report['path']).name}`")
            lines.append("")
            for check in brief_report["checks"]:
                prefix = "PASS" if check["ok"] else "FAIL"
                lines.append(f"- **{prefix}** `{check['name']}` — {check['details']}")
            lines.append("")

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
    write_output(args.json_out, json.dumps(report, indent=2))
    write_output(args.markdown_out, render_markdown(report))
    if report["verdict"] != "PASS":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
