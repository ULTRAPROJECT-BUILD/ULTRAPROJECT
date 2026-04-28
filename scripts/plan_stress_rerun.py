#!/usr/bin/env python3
"""
Recommend the next clean-room stress-test rerun scope from a stress-test report.

This helper turns the current ad hoc rerun pattern into a mechanical planning
step the orchestrator can rely on:

- initial/full clean-room FAIL -> fix tickets + targeted rerun pack
- narrow rerun FAIL -> smallest trustworthy rerun scope
- clean targeted rerun PASS -> one final broader confirmation pass
- clean final/full pass -> phase can complete
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

import yaml


SEVERITY_ORDER = {"blocker": 3, "major": 2, "minor": 1}
SECTION_HEADING_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
TITLE_RE = re.compile(r'^title:\s*"?(.*?)"?\s*$', re.MULTILINE)
VERDICT_LINE_RE = re.compile(r"^\*\*(PASS(?: WITH CAVEATS)?|FAIL)\*\*$", re.MULTILINE | re.IGNORECASE)
COUNT_RE = re.compile(r"-\s+(Blockers?|Majors?|Minors?|New issues.*?):\s*`?(\d+)`?", re.IGNORECASE)
FAILING_SCENARIO_LINE_RE = re.compile(r"-\s+Failing scenario:\s*`?([A-Z]+-\d+)`?", re.IGNORECASE)
HEADING_SEVERITY_RE = re.compile(r"^###\s+(Blocker|Major|Minor)\b", re.IGNORECASE | re.MULTILINE)
SCENARIO_ID_RE = re.compile(r"\b([A-Z]{1,2}-\d+)\b")

CURRENT_SCOPE_ALIASES = {
    "full_catalog": "full_catalog",
    "full-catalog": "full_catalog",
    "full": "full_catalog",
    "targeted_findings": "targeted_findings",
    "targeted-findings": "targeted_findings",
    "targeted_plus_regressions": "targeted_plus_regressions",
    "targeted-plus-regressions": "targeted_plus_regressions",
    "targeted": "targeted_plus_regressions",
    "rerun": "targeted_plus_regressions",
    "final_confirmation": "final_confirmation",
    "final-confirmation": "final_confirmation",
}

SCENARIO_FAMILY_OVERRIDES = {
    "A-1": "build_chain",
    "A-2": "build_chain",
    "A-3": "build_chain",
    "A-5": "build_chain",
    "B-5": "approvals_state_consistency",
    "B-6": "approvals_state_consistency",
    "B-7": "approvals_state_consistency",
    "C-6": "handoff_degraded_state",
    "CF-2": "approvals_state_consistency",
    "CF-3": "approvals_state_consistency",
    "D-3": "admin_command_guardrails",
    "D-4": "admin_command_guardrails",
    "D-10": "admin_command_guardrails",
    "D-11": "admin_command_guardrails",
    "D-12": "admin_command_guardrails",
    "E-3": "approvals_state_consistency",
}

PREFIX_FAMILIES = {
    "A": "build_chain",
    "B": "runtime_surface_coherency",
    "C": "corrupt_data_degraded_state",
    "D": "security_write_guards",
    "E": "concurrency_idempotence",
    "CF": "core_flow_state",
}

FAMILY_SENTINELS = {
    "build_chain": ["A-1", "A-2", "A-3", "A-5"],
    "approvals_state_consistency": ["B-5", "B-6", "B-7", "CF-2", "CF-3", "E-3"],
    "handoff_degraded_state": ["C-6", "C-7", "C-8", "C-9", "C-10"],
    "corrupt_data_degraded_state": ["C-2", "C-3", "C-4", "C-5", "C-6", "C-7", "C-8", "C-9", "C-10"],
    "admin_command_guardrails": ["D-3", "D-4", "D-10", "D-11", "D-12"],
    "security_write_guards": ["D-3", "D-4", "D-10", "D-11", "D-12"],
    "core_flow_state": ["CF-2", "CF-3", "B-5", "B-6", "B-7", "E-3"],
    "runtime_surface_coherency": ["B-5", "B-6", "B-7"],
    "concurrency_idempotence": ["E-3"],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stress-report", required=True, help="Stress test report markdown path.")
    parser.add_argument("--json-out", required=True, help="Where to write the JSON planning report.")
    parser.add_argument("--markdown-out", required=True, help="Where to write the markdown planning report.")
    return parser.parse_args()


def split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    if not text.startswith("---\n"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    frontmatter_text = parts[1].strip()
    body = parts[2].lstrip("\n")
    data = yaml.safe_load(frontmatter_text) if frontmatter_text else {}
    return (data if isinstance(data, dict) else {}), body


def parse_markdown_table(lines: list[str], start: int) -> tuple[list[dict[str, str]], int]:
    table_lines: list[str] = []
    idx = start
    while idx < len(lines):
        line = lines[idx]
        if not line.strip().startswith("|"):
            break
        table_lines.append(line.rstrip())
        idx += 1
    if len(table_lines) < 2:
        return [], start
    headers = [cell.strip() for cell in table_lines[0].strip().strip("|").split("|")]
    rows: list[dict[str, str]] = []
    for row_line in table_lines[2:]:
        cells = [cell.strip() for cell in row_line.strip().strip("|").split("|")]
        if len(cells) != len(headers):
            continue
        rows.append(dict(zip(headers, cells)))
    return rows, idx


def collect_tables(body: str) -> list[dict[str, Any]]:
    lines = body.splitlines()
    tables: list[dict[str, Any]] = []
    idx = 0
    current_section = ""
    while idx < len(lines):
        line = lines[idx]
        if line.startswith("## "):
            current_section = line[3:].strip()
        if line.strip().startswith("|"):
            rows, next_idx = parse_markdown_table(lines, idx)
            if rows:
                tables.append({"section": current_section, "rows": rows})
                idx = next_idx
                continue
        idx += 1
    return tables


def normalize_verdict(value: str) -> str:
    text = (value or "").strip().upper()
    if text.startswith("PASS WITH CAVEATS"):
        return "PASS WITH CAVEATS"
    if text.startswith("PASS"):
        return "PASS"
    if text.startswith("FAIL"):
        return "FAIL"
    return text or "UNKNOWN"


def extract_scenario_id(value: str) -> str:
    match = SCENARIO_ID_RE.search(value or "")
    return match.group(1) if match else (value or "").strip().strip("`")


def infer_current_scope(frontmatter: dict[str, Any], title: str, body: str) -> str:
    frontmatter_scope = str(frontmatter.get("rerun_scope", "")).strip().lower()
    if frontmatter_scope:
        return CURRENT_SCOPE_ALIASES.get(frontmatter_scope, frontmatter_scope)

    lowered = f"{title}\n{body}".lower()
    if "final confirmation" in lowered:
        return "final_confirmation"
    if "full 61-scenario replay" in lowered or "all 61 catalog scenarios" in lowered:
        if "not a full 61-scenario replay" not in lowered and "it does not re-run the full 61-scenario catalog" not in lowered:
            return "full_catalog"
    if "stress test rerun" in lowered or "targeted rerun" in lowered or "not a full 61-scenario replay" in lowered:
        return "targeted_plus_regressions"
    return "full_catalog"


def parse_counts(body: str) -> dict[str, int]:
    counts = {"blockers": 0, "majors": 0, "minors": 0, "new_issues": 0}
    for label, value in COUNT_RE.findall(body):
        key = label.lower()
        if key.startswith("blocker"):
            counts["blockers"] = int(value)
        elif key.startswith("major"):
            counts["majors"] = int(value)
        elif key.startswith("minor"):
            counts["minors"] = int(value)
        elif key.startswith("new issues"):
            counts["new_issues"] = int(value)
    return counts


def scenario_family(scenario_id: str) -> str:
    if scenario_id in SCENARIO_FAMILY_OVERRIDES:
        return SCENARIO_FAMILY_OVERRIDES[scenario_id]
    prefix = scenario_id.split("-", 1)[0]
    return PREFIX_FAMILIES.get(prefix, "miscellaneous")


def parse_report(report_path: Path) -> dict[str, Any]:
    text = report_path.read_text(encoding="utf-8")
    frontmatter, body = split_frontmatter(text)
    title = str(frontmatter.get("title", "")).strip()
    if not title:
        match = TITLE_RE.search(text)
        title = match.group(1).strip() if match else report_path.stem

    verdict = normalize_verdict(str(frontmatter.get("verdict", "")).strip())
    if verdict == "UNKNOWN":
        match = VERDICT_LINE_RE.search(body)
        if match:
            verdict = normalize_verdict(match.group(1))

    counts = parse_counts(body)
    tables = collect_tables(body)

    findings: list[dict[str, str]] = []
    scenario_results: list[dict[str, str]] = []
    for table in tables:
        rows = table["rows"]
        if not rows:
            continue
        keys = {key.lower(): key for key in rows[0].keys()}
        if "severity" in keys and "scenario" in keys:
            for row in rows:
                severity = row.get(keys["severity"], "").strip().lower()
                scenario = extract_scenario_id(row.get(keys["scenario"], ""))
                verdict_value = row.get(keys.get("verdict", ""), "").strip().strip("`")
                note = row.get(keys.get("note", ""), "").strip()
                findings.append(
                    {
                        "severity": severity,
                        "scenario": scenario,
                        "verdict": normalize_verdict(verdict_value or "FAIL"),
                        "note": note,
                        "family": scenario_family(scenario) if scenario else "miscellaneous",
                    }
                )
        if "scenario" in keys and "verdict" in keys:
            for row in rows:
                scenario = extract_scenario_id(row.get(keys["scenario"], ""))
                verdict_value = row.get(keys["verdict"], "").strip().strip("`")
                note = row.get(keys.get("note", ""), "").strip() or row.get(keys.get("notes", ""), "").strip()
                scenario_results.append(
                    {
                        "scenario": scenario,
                        "verdict": normalize_verdict(verdict_value),
                        "note": note,
                        "family": scenario_family(scenario) if scenario else "miscellaneous",
                    }
                )

    if not findings:
        for match in HEADING_SEVERITY_RE.finditer(body):
            severity = match.group(1).lower()
            window = body[match.end() : match.end() + 400]
            scenario_match = SCENARIO_ID_RE.search(window)
            scenario = scenario_match.group(1) if scenario_match else ""
            findings.append(
                {
                    "severity": severity,
                    "scenario": scenario,
                    "verdict": "FAIL",
                    "note": "",
                    "family": scenario_family(scenario) if scenario else "miscellaneous",
                }
            )

    if counts["blockers"] == counts["majors"] == counts["minors"] == 0 and findings:
        for finding in findings:
            severity = finding["severity"]
            if severity.startswith("blocker"):
                counts["blockers"] += 1
            elif severity.startswith("major"):
                counts["majors"] += 1
            elif severity.startswith("minor"):
                counts["minors"] += 1

    current_scope = infer_current_scope(frontmatter, title, body)
    if current_scope != "full_catalog" and counts["new_issues"] == 0:
        new_issue_section = extract_section(body, "New Issues In This Scope")
        if new_issue_section:
            bullet_count = sum(1 for line in new_issue_section.splitlines() if line.strip().startswith("- "))
            if bullet_count:
                counts["new_issues"] = bullet_count

    failing_scenarios = [row["scenario"] for row in scenario_results if row["scenario"] and row["verdict"] == "FAIL"]
    if not failing_scenarios:
        failing_scenarios = [finding["scenario"] for finding in findings if finding["scenario"]]
    deduped_failing = list(dict.fromkeys(failing_scenarios))

    severe_families = list(
        dict.fromkeys(
            finding["family"]
            for finding in findings
            if finding["severity"] in {"blocker", "major"} and finding["family"] != "miscellaneous"
        )
    )
    if not severe_families:
        severe_families = list(dict.fromkeys(scenario_family(scenario) for scenario in deduped_failing if scenario))

    return {
        "title": title,
        "verdict": verdict,
        "current_scope": current_scope,
        "counts": counts,
        "findings": findings,
        "scenario_results": scenario_results,
        "failing_scenarios": deduped_failing,
        "severe_families": severe_families,
        "frontmatter": frontmatter,
        "body": body,
    }


def extract_section(body: str, section_name: str) -> str:
    lines = body.splitlines()
    capture = False
    captured: list[str] = []
    for line in lines:
        if line.startswith("## "):
            if capture:
                break
            capture = line[3:].strip().lower() == section_name.lower()
            continue
        if capture:
            captured.append(line)
    return "\n".join(captured).strip()


def build_target_scenarios(report: dict[str, Any], next_scope: str) -> list[str]:
    failing = report["failing_scenarios"]
    if next_scope == "full_catalog":
        return []

    families = report["severe_families"] or [scenario_family(scenario) for scenario in failing]
    if not families:
        families = list(
            dict.fromkeys(
                row["family"]
                for row in report["scenario_results"]
                if row["scenario"] and row["family"] != "miscellaneous"
            )
        )
    sentinel_candidates: list[str] = []
    for family in families:
        sentinel_candidates.extend(FAMILY_SENTINELS.get(family, []))

    pass_results = [
        row["scenario"]
        for row in report["scenario_results"]
        if row["scenario"] and row["verdict"] == "PASS" and row["family"] in families
    ]

    ordered = list(dict.fromkeys([*failing, *pass_results, *sentinel_candidates]))
    if next_scope == "targeted_findings":
        return ordered[: max(1, len(failing) + len(pass_results))]
    if next_scope == "final_confirmation":
        broad_confirmation: list[str] = []
        for family in families:
            broad_confirmation.extend(FAMILY_SENTINELS.get(family, []))
        broad_confirmation.extend(["A-3", "D-10"])
        return list(dict.fromkeys([*ordered, *broad_confirmation]))
    return ordered


def determine_recommendation(report: dict[str, Any]) -> dict[str, Any]:
    verdict = report["verdict"]
    current_scope = report["current_scope"]
    blockers = report["counts"]["blockers"]
    majors = report["counts"]["majors"]
    severe_count = blockers + majors
    family_count = len(report["severe_families"])
    new_issues = report["counts"]["new_issues"]

    if verdict == "PASS WITH CAVEATS":
        verdict = "FAIL"

    if verdict == "PASS":
        if current_scope in {"full_catalog", "final_confirmation"}:
            next_scope = "phase_complete"
            next_action = "complete_phase"
            rationale = "A clean broad stress pass already exists, so the phase can advance."
        else:
            next_scope = "final_confirmation"
            next_action = "run_final_confirmation"
            rationale = "The targeted rerun is clean; preserve trust with one final broader clean-room confirmation before declaring Phase 5 done."
    else:
        if current_scope == "full_catalog":
            next_scope = "targeted_plus_regressions"
            next_action = "create_fix_tickets_then_rerun"
            rationale = "The initial broad stress run has already found the failure field. The next efficient step is a clean-room targeted rerun pack covering the failed scenarios plus their nearby regressions."
        elif severe_count <= 1 and family_count <= 1 and new_issues == 0:
            next_scope = "targeted_findings"
            next_action = "create_fix_tickets_then_rerun"
            rationale = "Only one severe family remains and no new issues surfaced, so the smallest trustworthy rerun is the exact failing scenario set."
        elif severe_count <= 3 and family_count <= 2:
            next_scope = "targeted_plus_regressions"
            next_action = "create_fix_tickets_then_rerun"
            rationale = "The failures are still narrow enough to re-test surgically, but they touch enough neighboring behavior that the rerun should include the relevant regression family pack."
        else:
            next_scope = "full_catalog"
            next_action = "create_fix_tickets_then_rerun"
            rationale = "Multiple severe families are unstable again, so the next trustworthy check has to widen back to a full clean-room catalog run."

    target_scenarios = build_target_scenarios(report, next_scope)
    severe_families = report["severe_families"]
    suggested_title = suggest_title(next_scope, target_scenarios)

    return {
        "next_scope": next_scope,
        "next_action": next_action,
        "target_scenarios": target_scenarios,
        "defect_families": severe_families,
        "rationale": rationale,
        "suggested_title": suggested_title,
        "final_confirmation_required": next_scope == "final_confirmation",
    }


def suggest_title(next_scope: str, target_scenarios: list[str]) -> str:
    if next_scope == "phase_complete":
        return "Phase 5 complete — no additional rerun required"
    if next_scope == "final_confirmation":
        return "Stress test final confirmation — clean-room broad verification after targeted fixes"
    if next_scope == "targeted_findings":
        scenarios = " and ".join(target_scenarios[:3]) if target_scenarios else "targeted fixes"
        return f"Stress test targeted rerun — verify {scenarios}"
    if next_scope == "targeted_plus_regressions":
        if target_scenarios:
            lead = ", ".join(target_scenarios[:4])
            return f"Stress test rerun — verify {lead} plus related regressions"
        return "Stress test rerun — targeted fixes plus related regressions"
    return "Stress test full rerun — clean-room full catalog confirmation"


def build_markdown(report: dict[str, Any], recommendation: dict[str, Any]) -> str:
    counts = report["counts"]
    lines = [
        "---",
        "type: snapshot",
        "subtype: stress-rerun-plan",
        f'title: "Stress Rerun Plan — {report["title"]}"',
        f'verdict: "{report["verdict"]}"',
        f'current_scope: "{report["current_scope"]}"',
        f'next_scope: "{recommendation["next_scope"]}"',
        "---",
        "",
        "# Stress Rerun Plan",
        "",
        f"- Source report: `{report['title']}`",
        f"- Current scope: `{report['current_scope']}`",
        f"- Verdict: `{report['verdict']}`",
        f"- Blockers: `{counts['blockers']}`",
        f"- Majors: `{counts['majors']}`",
        f"- Minors: `{counts['minors']}`",
        f"- New issues in scope: `{counts['new_issues']}`",
        "",
        "## Recommendation",
        "",
        f"- Next action: `{recommendation['next_action']}`",
        f"- Recommended rerun scope: `{recommendation['next_scope']}`",
        f"- Suggested ticket title: `{recommendation['suggested_title']}`",
        f"- Rationale: {recommendation['rationale']}",
        "",
        "## Defect Families",
        "",
    ]
    if recommendation["defect_families"]:
        for family in recommendation["defect_families"]:
            lines.append(f"- `{family}`")
    else:
        lines.append("- None")

    lines.extend(["", "## Target Scenarios", ""])
    if recommendation["target_scenarios"]:
        for scenario in recommendation["target_scenarios"]:
            lines.append(f"- `{scenario}`")
    else:
        lines.append("- Full clean-room catalog rerun required")

    lines.extend(["", "## Failing Scenarios", ""])
    if report["failing_scenarios"]:
        for scenario in report["failing_scenarios"]:
            lines.append(f"- `{scenario}`")
    else:
        lines.append("- None")
    return "\n".join(lines) + "\n"


def write_outputs(report: dict[str, Any], recommendation: dict[str, Any], json_out: Path, markdown_out: Path) -> None:
    payload = {
        "source_title": report["title"],
        "verdict": report["verdict"],
        "current_scope": report["current_scope"],
        "counts": report["counts"],
        "failing_scenarios": report["failing_scenarios"],
        "recommendation": recommendation,
    }
    json_out.parent.mkdir(parents=True, exist_ok=True)
    markdown_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    markdown_out.write_text(build_markdown(report, recommendation), encoding="utf-8")


def main() -> int:
    args = parse_args()
    report_path = Path(args.stress_report).expanduser().resolve()
    json_out = Path(args.json_out).expanduser().resolve()
    markdown_out = Path(args.markdown_out).expanduser().resolve()

    if not report_path.exists():
        print(f"Stress report not found: {report_path}", file=sys.stderr)
        return 2

    report = parse_report(report_path)
    recommendation = determine_recommendation(report)
    write_outputs(report, recommendation, json_out, markdown_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
