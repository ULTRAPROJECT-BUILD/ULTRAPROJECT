#!/usr/bin/env python3
"""Fail fast when frontier planning artifacts lean on playbooks too heavily."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple


def read_text(path: Optional[str]) -> str:
    if not path:
        return ""
    return Path(path).read_text(encoding="utf-8")


def has_heading(text: str, heading: str) -> bool:
    pattern = rf"(?m)^##\s+{re.escape(heading)}\s*$"
    return bool(re.search(pattern, text))


def extract_section(text: str, heading: str) -> str:
    pattern = rf"(?ms)^##\s+{re.escape(heading)}\s*$\n(.*?)(?=^##\s+|\Z)"
    match = re.search(pattern, text)
    return match.group(1).strip() if match else ""


def determine_frontier(text: str, explicit: bool) -> bool:
    if explicit:
        return True
    lowered = text.lower()
    signals = [
        "billion-line",
        "billion line",
        "fortune 100",
        "enterprise infrastructure",
        "admin-priority",
        "extreme scale",
        "platform engineering",
        "resumable refactor",
    ]
    hit_count = sum(1 for signal in signals if signal in lowered)
    return "admin-priority" in lowered or hit_count >= 2


def architecture_playbook_ratio(plan_text: str) -> Tuple[int, int, float]:
    match = re.search(
        r"(?ms)^##\s+Architecture Decisions\s*$\n(.*?)(?=^##\s+|\Z)", plan_text
    )
    if not match:
        return 0, 0, 0.0
    section = match.group(1)
    rows = []
    for line in section.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        if set(stripped.replace("|", "").strip()) == {"-"}:
            continue
        if "Decision" in stripped and "Rationale" in stripped:
            continue
        rows.append(stripped)
    if not rows:
        return 0, 0, 0.0
    playbook_rows = [row for row in rows if "playbook" in row.lower()]
    ratio = len(playbook_rows) / len(rows)
    return len(playbook_rows), len(rows), ratio


def suspicious_playbook_proof_lines(text: str) -> List[str]:
    allowed_markers = (
        "not proof",
        "prior art",
        "re-prove",
        "re-proven",
        "does not prove",
        "not as proof",
        "must prove",
        "may not be used as proof",
        "do not use it as proof",
    )
    findings: List[str] = []
    for line in text.splitlines():
        lowered = line.lower()
        if "playbook" not in lowered:
            continue
        if not re.search(r"\b(prove|proved|proven|proof)\b", lowered):
            continue
        if any(marker in lowered for marker in allowed_markers):
            continue
        if re.search(r"\bnot\b.{0,60}\b(prove|proved|proven|proof)\b", lowered):
            continue
        if re.search(r"\b(prove|proved|proven|proof)\b.{0,60}\bnot\b", lowered):
            continue
        findings.append(line.strip())
    return findings


def find_reuse_mode(section_text: str) -> Optional[str]:
    lowered = section_text.lower()
    for mode in ("pattern_only", "component_reuse", "template_allowed"):
        if mode in lowered:
            return mode
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", required=True)
    parser.add_argument("--brief")
    parser.add_argument("--project")
    parser.add_argument("--frontier", action="store_true")
    parser.add_argument("--budget-pct", type=float, default=30.0)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    artifacts: Dict[str, str] = {
        "plan": read_text(args.plan),
        "brief": read_text(args.brief),
        "project": read_text(args.project),
    }
    combined = "\n".join(text for text in artifacts.values() if text)
    frontier = determine_frontier(combined, args.frontier)

    errors: List[str] = []
    warnings: List[str] = []

    if frontier:
        plan_usage = extract_section(artifacts["plan"], "Playbook Usage Contract")
        plan_why = extract_section(artifacts["plan"], "Why This Cannot Just Be The Playbook")
        if not plan_usage:
            errors.append("Plan is missing required section: ## Playbook Usage Contract")
        if not plan_why:
            errors.append(
                "Plan is missing required section: ## Why This Cannot Just Be The Playbook"
            )
        if plan_usage and not find_reuse_mode(plan_usage):
            errors.append(
                "Plan Playbook Usage Contract does not declare a reuse mode (pattern_only, component_reuse, or template_allowed)"
            )

        if artifacts["brief"]:
            brief_usage = extract_section(artifacts["brief"], "Playbook Usage Contract")
            brief_why = extract_section(
                artifacts["brief"], "Why This Cannot Just Be The Playbook"
            )
            if not brief_usage:
                errors.append(
                    "Brief is missing required section: ## Playbook Usage Contract"
                )
            if not brief_why:
                errors.append(
                    "Brief is missing required section: ## Why This Cannot Just Be The Playbook"
                )

    suspicious = suspicious_playbook_proof_lines(combined)
    if suspicious:
        errors.append(
            "Playbook is being cited with proof language without an explicit prior-art disclaimer"
        )

    referenced_rows, total_rows, ratio = architecture_playbook_ratio(artifacts["plan"])
    if frontier and total_rows:
        budget = args.budget_pct / 100.0
        if ratio > budget:
            errors.append(
                f"Architecture Decisions over-reference playbooks ({referenced_rows}/{total_rows} rows, {ratio:.0%}) beyond the frontier budget of {budget:.0%}"
            )
        elif ratio > budget * 0.75:
            warnings.append(
                f"Architecture Decisions are close to the playbook-reference budget ({referenced_rows}/{total_rows} rows, {ratio:.0%})"
            )

    result = {
        "ok": not errors,
        "frontier": frontier,
        "errors": errors,
        "warnings": warnings,
        "suspicious_lines": suspicious,
        "architecture_playbook_rows": referenced_rows,
        "architecture_total_rows": total_rows,
        "architecture_playbook_ratio": ratio,
    }

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        verdict = "PASS" if result["ok"] else "FAIL"
        print(f"Verdict: {verdict}")
        print(f"Frontier project: {'yes' if frontier else 'no'}")
        print(
            f"Architecture playbook references: {referenced_rows}/{total_rows} ({ratio:.0%})"
        )
        if errors:
            print("Errors:")
            for error in errors:
                print(f"- {error}")
        if warnings:
            print("Warnings:")
            for warning in warnings:
                print(f"- {warning}")
        if suspicious:
            print("Suspicious lines:")
            for line in suspicious:
                print(f"- {line}")

    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
