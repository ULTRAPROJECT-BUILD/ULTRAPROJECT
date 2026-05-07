#!/usr/bin/env python3
from __future__ import annotations

"""
Build a scenario-based rehearsal packet for a project transition.
"""

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

from build_project_context import build_report as build_project_context_report, discover_project_layout, extract_section, parse_labeled_bullets

UI_HINT_RE = re.compile(r"\b(dashboard|console|control platform|screen|ui|ux|web app|website|app|approval|onboarding)\b", re.IGNORECASE)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-file", required=True, help="Project markdown path.")
    parser.add_argument("--project-plan", help="Optional explicit project plan path.")
    parser.add_argument("--transition", help="Optional explicit transition name (delivery, phase_gate, review, execution).")
    parser.add_argument("--json-out", help="Optional JSON output path.")
    parser.add_argument("--markdown-out", help="Optional markdown output path.")
    return parser.parse_args()


def now() -> str:
    return datetime.now().astimezone().strftime("%Y-%m-%dT%H:%M:%S %Z %z")


def write_output(path: str | None, content: str) -> None:
    if not path:
        return
    target = Path(path).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def split_items(value: str) -> list[str]:
    raw = re.split(r"[;\n,]+", value or "")
    seen: set[str] = set()
    items: list[str] = []
    for item in raw:
        cleaned = item.strip().strip("-").strip()
        if not cleaned:
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)
        items.append(cleaned)
    return items


def load_proof_strategy_fields(report: dict[str, Any], platform_root: Path) -> dict[str, str]:
    ordered = ((report.get("briefs") or {}).get("ordered") or [])
    for brief in reversed(ordered):
        rel_path = str(brief.get("path") or "").strip()
        if not rel_path:
            continue
        brief_path = (platform_root / rel_path).resolve()
        if not brief_path.exists():
            continue
        text = brief_path.read_text(encoding="utf-8")
        _, body = text.split("---", 2)[1:] if text.startswith("---\n") else ("", text)
        section = extract_section(body, "Proof Strategy")
        fields = parse_labeled_bullets(section)
        if fields:
            return fields
    return {}


def infer_transition(report: dict[str, Any], explicit: str | None) -> str:
    if explicit:
        return explicit.strip().lower()
    current_review = ((report.get("reviews") or {}).get("current_review") or {}).get("kind", "")
    phase_title = str(report.get("current_phase_title") or "")
    if "delivery" in current_review or "delivery" in phase_title.lower():
        return "delivery"
    if "phase-gate" in current_review:
        return "phase_gate"
    if "review" in current_review or "polish" in phase_title.lower():
        return "review"
    return "execution"


def infer_lenses(report: dict[str, Any], proof_fields: dict[str, str], transition: str) -> list[dict[str, Any]]:
    text_blob = " ".join(
        [
            str(report.get("title") or ""),
            str(report.get("goal") or ""),
            str(report.get("current_phase_title") or ""),
            str(report.get("current_wave") or ""),
        ]
    )
    uiish = bool(UI_HINT_RE.search(text_blob)) or bool((report.get("image_evidence") or {}).get("count"))
    declared_lenses = split_items(proof_fields.get("Rehearsal lenses", ""))

    labels = declared_lenses[:] if declared_lenses else []
    if "skeptical reviewer" not in [label.lower() for label in labels]:
        labels.append("skeptical reviewer")
    if transition == "delivery":
        labels.append("delivery receiver")
    if transition == "phase_gate":
        labels.append("gate reviewer")
    if uiish:
        labels.extend(["tired operator", "manager giving feedback", "skeptical stakeholder"])

    deduped: list[str] = []
    seen: set[str] = set()
    for label in labels:
        key = label.strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(label.strip())

    library = {
        "skeptical reviewer": [
            "What would look complete here without actually closing the proof?",
            "Which files would I open first to verify the main claim?",
        ],
        "delivery receiver": [
            "Could I understand the handoff without builder context?",
            "What would confuse me in the first five minutes of review?",
        ],
        "gate reviewer": [
            "Which claim is still least well supported?",
            "What stale artifact would make the gate output untrustworthy?",
        ],
        "tired operator": [
            "Can I find the primary action quickly without hunting through the interface?",
            "Which trust or approval state would I misunderstand first?",
        ],
        "manager giving feedback": [
            "Can I leave correction or confirmation in the obvious place?",
            "What would happen after feedback lands, and is that visible?",
        ],
        "skeptical stakeholder": [
            "What is live versus merely planned or partially covered?",
            "Where does the product feel more confident than the proof actually supports?",
        ],
    }

    return [
        {
            "label": label,
            "questions": library.get(label.lower(), ["What would this persona misunderstand or distrust first?"]),
        }
        for label in deduped
    ]


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    project_file = Path(args.project_file).expanduser().resolve()
    layout = discover_project_layout(project_file)
    platform_root = Path(layout["platform_root"])
    context_report = build_project_context_report(
        argparse.Namespace(
            project_file=str(project_file),
            project_plan=args.project_plan,
            context_out=None,
            index_out=None,
        )
    )
    proof_fields = load_proof_strategy_fields(context_report, platform_root)
    transition = infer_transition(context_report, args.transition)
    lenses = infer_lenses(context_report, proof_fields, transition)

    likely_failures = []
    likely_failures.extend(split_items(proof_fields.get("False-pass risks", "")))
    likely_failures.extend(
        f"Assumption still unresolved: {row.get('Assumption', '').strip()}"
        for row in ((context_report.get("assumptions") or {}).get("active") or [])[:5]
        if row.get("Assumption")
    )
    likely_failures.extend(
        f"Active ticket still unresolved: {ticket.get('id')} {ticket.get('title')}"
        for ticket in (context_report.get("tickets", {}).get("blocked") or [])[:3]
    )

    deduped_failures: list[str] = []
    seen: set[str] = set()
    for item in likely_failures:
        cleaned = str(item).strip()
        if not cleaned:
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped_failures.append(cleaned)

    current_review = (context_report.get("reviews") or {}).get("current_review") or {}
    recommend_ticket = transition in {"delivery", "phase_gate"} or len(lenses) >= 3

    return {
        "generated_at": now(),
        "project": context_report.get("project"),
        "client": context_report.get("client"),
        "transition": transition,
        "rigor_tier": ((context_report.get("goal_contract") or {}).get("fields") or {}).get("Rigor tier", ""),
        "current_phase": context_report.get("current_phase"),
        "current_phase_display": context_report.get("current_phase_display"),
        "current_wave": context_report.get("current_wave", ""),
        "current_review": current_review,
        "proof_strategy": {
            "evaluator_lens": proof_fields.get("Evaluator lens", ""),
            "proof_posture": proof_fields.get("Proof posture", ""),
            "false_pass_risks": split_items(proof_fields.get("False-pass risks", "")),
            "rehearsal_lenses": split_items(proof_fields.get("Rehearsal lenses", "")),
            "drift_sentinels": split_items(proof_fields.get("Drift sentinels", "")),
            "supplement_trigger": proof_fields.get("Supplement trigger", ""),
        },
        "lenses": lenses,
        "likely_failures": deduped_failures,
        "recommended_task_type": "simulation_rehearsal" if recommend_ticket else "",
        "ticket_recommended": recommend_ticket,
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Project Rehearsal Packet",
        "",
        f"- Generated: {report['generated_at']}",
        f"- Project: `{report['project']}`",
        f"- Transition: `{report['transition']}`",
    ]
    if report.get("rigor_tier"):
        lines.append(f"- Rigor tier: `{report['rigor_tier']}`")
    current_review = report.get("current_review") or {}
    if current_review.get("kind_label"):
        lines.append(f"- Current review: {current_review['kind_label']}")
    if report.get("ticket_recommended"):
        lines.append(f"- Recommended task type: `{report['recommended_task_type']}`")

    lines.extend(["", "## Rehearsal Lenses", ""])
    for lens in report.get("lenses", []):
        lines.append(f"### {lens['label']}")
        lines.append("")
        for question in lens.get("questions", []):
            lines.append(f"- {question}")
        lines.append("")

    lines.extend(["## Likely Failure Hypotheses", ""])
    if not report.get("likely_failures"):
        lines.append("- None surfaced from the current contract.")
    else:
        for item in report["likely_failures"]:
            lines.append(f"- {item}")
    lines.append("")

    proof = report.get("proof_strategy") or {}
    lines.extend(["## Proof Hooks", ""])
    if proof.get("supplement_trigger"):
        lines.append(f"- Supplement trigger: {proof['supplement_trigger']}")
    for sentinel in proof.get("drift_sentinels", []):
        lines.append(f"- Drift sentinel: {sentinel}")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    report = build_report(args)
    write_output(args.json_out, json.dumps(report, indent=2))
    write_output(args.markdown_out, render_markdown(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
