#!/usr/bin/env python3
"""
Fail delivery readiness when the clean-room artifact polish review is missing or weak.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

TIMESTAMP_FMT = "%Y-%m-%dT%H:%M:%S"
VERDICT_FRONTMATTER_RE = re.compile(r"^verdict:\s*\"?([^\n\"]+)\"?\s*$", re.IGNORECASE | re.MULTILINE)
VERDICT_HEADING_RE = re.compile(r"^## Verdict:\s*(.+?)\s*$", re.IGNORECASE | re.MULTILINE)
GRADE_FRONTMATTER_RE = re.compile(r"^grade:\s*\"?([A-F][+-]?)\"?\s*$", re.IGNORECASE | re.MULTILINE)
GRADE_HEADING_RE = re.compile(r"^(?:##\s+)?\**Grade:?\**\s*([A-F][+-]?)\s*$", re.IGNORECASE | re.MULTILINE)
REQUIRED_SECTION_RES = {
    "findings": re.compile(r"^##\s+(Top\s+)?Findings\b", re.IGNORECASE | re.MULTILINE),
    "first_impression": re.compile(r"^##\s+First Impression\b", re.IGNORECASE | re.MULTILINE),
    "coherence": re.compile(r"^##\s+Coherence\b", re.IGNORECASE | re.MULTILINE),
    "specificity": re.compile(r"^##\s+Specificity\b", re.IGNORECASE | re.MULTILINE),
    "friction": re.compile(r"^##\s+Friction\b", re.IGNORECASE | re.MULTILINE),
    "edge_finish": re.compile(r"^##\s+Edge Finish\b", re.IGNORECASE | re.MULTILINE),
    "trust": re.compile(r"^##\s+Trust\b", re.IGNORECASE | re.MULTILINE),
    "delta_quality": re.compile(r"^##\s+Delta Quality\b", re.IGNORECASE | re.MULTILINE),
}
GRADE_ORDER = {"F": 0, "D": 1, "C": 2, "B": 3, "A": 4}


def basenames(items: list[dict]) -> list[str]:
    names = []
    seen = set()
    for item in items:
        candidate = Path(item.get("relative_path") or item.get("path") or "").name
        if not candidate:
            continue
        lowered = candidate.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        names.append(candidate)
    return names


def text_mentions_any_filename(text: str, names: list[str]) -> bool:
    lowered = text.lower()
    return any(name.lower() in lowered for name in names)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--polish-report", required=True, help="Artifact polish review markdown report.")
    parser.add_argument("--review-pack-json", required=True, help="Review-pack JSON output.")
    parser.add_argument("--required-grade", default="A", help="Minimum acceptable grade band (A-F).")
    parser.add_argument("--json-out", required=True, help="Where to write the polish-gate JSON report.")
    parser.add_argument("--markdown-out", required=True, help="Where to write the polish-gate markdown report.")
    return parser.parse_args()


def detect_with_regexes(text: str, regexes: list[re.Pattern[str]]) -> str | None:
    for regex in regexes:
        match = regex.search(text)
        if match:
            return match.group(1).strip()
    return None


def normalize_verdict(value: str | None) -> str:
    text = str(value or "").strip().upper()
    if text.startswith("PASS"):
        return "PASS"
    if text.startswith("REVISE"):
        return "REVISE"
    if text.startswith("FAIL"):
        return "FAIL"
    return text or "MISSING"


def normalize_grade(value: str | None) -> str:
    text = str(value or "").strip().upper()
    match = re.search(r"[A-F]", text)
    return match.group(0) if match else ""


def grade_meets_threshold(actual: str, required: str) -> bool:
    actual_band = normalize_grade(actual)
    required_band = normalize_grade(required)
    if not actual_band or not required_band:
        return False
    return GRADE_ORDER[actual_band] >= GRADE_ORDER[required_band]


def build_report(args: argparse.Namespace) -> dict:
    polish_path = Path(args.polish_report).expanduser().resolve()
    review_pack_path = Path(args.review_pack_json).expanduser().resolve()
    polish_text = polish_path.read_text(encoding="utf-8") if polish_path.exists() else ""
    review_pack = {}
    if review_pack_path.exists():
        try:
            review_pack = json.loads(review_pack_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            review_pack = {}

    verdict = normalize_verdict(detect_with_regexes(polish_text, [VERDICT_FRONTMATTER_RE, VERDICT_HEADING_RE]))
    grade = detect_with_regexes(polish_text, [GRADE_FRONTMATTER_RE, GRADE_HEADING_RE]) or ""
    spotlight_artifacts = review_pack.get("spotlight_artifacts", [])
    walkthrough_artifacts = review_pack.get("walkthrough_artifacts", [])
    walkthrough_requirement = review_pack.get("walkthrough_requirement", {})
    walkthrough_level = str(walkthrough_requirement.get("level", "not_needed")).lower()
    walkthrough_names = basenames(walkthrough_artifacts)

    checks = [
        {
            "name": "review_pack_present",
            "ok": review_pack_path.exists(),
            "details": str(review_pack_path),
        },
        {
            "name": "review_pack_has_spotlight",
            "ok": bool(spotlight_artifacts),
            "details": (
                f"{len(spotlight_artifacts)} spotlight artifact(s) found."
                if spotlight_artifacts
                else "Review pack contains no spotlight artifacts."
            ),
        },
        {
            "name": "review_pack_verdict_pass",
            "ok": review_pack.get("verdict") == "PASS",
            "details": f"Review pack verdict: {review_pack.get('verdict', 'missing')}",
        },
        {
            "name": "walkthrough_present_when_required",
            "ok": walkthrough_level != "required" or bool(walkthrough_artifacts),
            "details": (
                "Walkthrough video required and present."
                if walkthrough_level == "required" and walkthrough_artifacts
                else (
                    "Walkthrough video required but missing from review pack."
                    if walkthrough_level == "required"
                    else f"Walkthrough requirement level: {walkthrough_level or 'missing'}"
                )
            ),
        },
        {
            "name": "polish_references_walkthrough_when_present",
            "ok": True if not walkthrough_names else text_mentions_any_filename(polish_text, walkthrough_names),
            "details": (
                f"Walkthrough artifacts present ({', '.join(walkthrough_names)}); polish report references at least one."
                if walkthrough_names and text_mentions_any_filename(polish_text, walkthrough_names)
                else (
                    f"Walkthrough artifacts present ({', '.join(walkthrough_names)}) but polish report does not reference them."
                    if walkthrough_names
                    else "No walkthrough artifacts present."
                )
            ),
        },
        {
            "name": "polish_report_present",
            "ok": polish_path.exists(),
            "details": str(polish_path),
        },
        {
            "name": "polish_verdict_pass",
            "ok": verdict == "PASS",
            "details": f"Polish verdict: {verdict}",
        },
        {
            "name": "polish_grade_threshold",
            "ok": grade_meets_threshold(grade, args.required_grade),
            "details": f"Grade: {grade or 'missing'} (required >= {args.required_grade})",
        },
    ]

    for section_name, regex in REQUIRED_SECTION_RES.items():
        checks.append(
            {
                "name": f"section_{section_name}",
                "ok": bool(regex.search(polish_text)),
                "details": (
                    f"Section present: {section_name}"
                    if regex.search(polish_text)
                    else f"Missing section: {section_name}"
                ),
            }
        )

    verdict_out = "PASS" if all(check["ok"] for check in checks) else "FAIL"
    return {
        "generated_at": datetime.now().strftime(TIMESTAMP_FMT),
        "polish_report": str(polish_path),
        "review_pack_json": str(review_pack_path),
        "required_grade": args.required_grade,
        "detected_grade": grade,
        "detected_verdict": verdict,
        "spotlight_count": len(spotlight_artifacts),
        "walkthrough_count": len(walkthrough_artifacts),
        "walkthrough_requirement_level": walkthrough_level,
        "checks": checks,
        "verdict": verdict_out,
    }


def render_markdown(report: dict) -> str:
    lines = [
        "# Polish Gate Report",
        "",
        f"**Generated:** {report['generated_at']}",
        f"**Verdict:** {report['verdict']}",
        f"**Polish report:** {report['polish_report']}",
        f"**Review pack:** {report['review_pack_json']}",
        f"**Walkthrough videos:** {report['walkthrough_count']}",
        f"**Walkthrough requirement:** {report['walkthrough_requirement_level']}",
        "",
        "## Checks",
        "",
        "| Check | Status | Details |",
        "|------|--------|---------|",
    ]
    for check in report["checks"]:
        details = str(check["details"]).replace("|", "\\|")
        lines.append(
            f"| {check['name']} | {'PASS' if check['ok'] else 'FAIL'} | {details} |"
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    report = build_report(args)

    json_out = Path(args.json_out).expanduser().resolve()
    markdown_out = Path(args.markdown_out).expanduser().resolve()
    json_out.parent.mkdir(parents=True, exist_ok=True)
    markdown_out.parent.mkdir(parents=True, exist_ok=True)

    json_out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    markdown_out.write_text(render_markdown(report), encoding="utf-8")

    print(f"verdict={report['verdict']}")
    print(f"json_report={json_out}")
    print(f"markdown_report={markdown_out}")
    return 0 if report["verdict"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
