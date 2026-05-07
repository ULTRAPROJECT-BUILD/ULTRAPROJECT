#!/usr/bin/env python3
"""
Fail governed UI delivery readiness when the authoritative visual review is weak or missing.

This script is the mechanical checker for the Claude-owned visual review gate.
It expects:

- ticket/brief metadata describing the visual contract
- QC reports that reference concrete runtime screenshot filenames
- a visual review report with structured frontmatter + sections

The visual review report is the place where the orchestrator/Claude lane makes
the actual screenshot/design judgment. This checker verifies that the report is
present, concrete, and strong enough to trust mechanically.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

TIMESTAMP_FMT = "%Y-%m-%dT%H:%M:%S"
SCREENSHOT_REF_RE = re.compile(r"\b([A-Za-z0-9._-]+\.(?:png|jpg|jpeg|webp|gif|svg))\b", re.IGNORECASE)
QC_SCREENSHOT_HINT_RE = re.compile(r"\b(qc-screenshot-|qc-slides/|walkthrough|playthrough)\b", re.IGNORECASE)
VISUAL_VERDICT_HEADING_RE = re.compile(r"^##\s+Visual Verdict\b", re.IGNORECASE | re.MULTILINE)
EVIDENCE_REVIEWED_HEADING_RE = re.compile(r"^##\s+Evidence Reviewed\b", re.IGNORECASE | re.MULTILINE)
FINDINGS_HEADING_RE = re.compile(r"^##\s+Findings\b", re.IGNORECASE | re.MULTILINE)
REQUIRED_FIXES_HEADING_RE = re.compile(r"^##\s+Required Fixes\b", re.IGNORECASE | re.MULTILINE)
STITCH_FIDELITY_HEADING_RE = re.compile(r"^##\s+Stitch Fidelity\b", re.IGNORECASE | re.MULTILINE)
VERDICT_HEADING_RE = re.compile(r"^##\s+Verdict:\s*(.+?)\s*$", re.IGNORECASE | re.MULTILINE)
VERDICT_BOLD_RE = re.compile(r"\*\*Verdict:\s*\*?\*?([A-Z]+)\*?\*?\*\*", re.IGNORECASE)
ROUTE_FAMILY_HINT_RE = re.compile(
    r"\b("
    r"pending review|handoff|memory browser|memory page|trust ledger|audit timeline|audit page|"
    r"live watch|agent console|retrieval / context|retrieval and context|knowledge graph|teach mode|"
    r"comments|feedback page|approvals page|operator console|operator surface|primary route|"
    r"top-level route|top level route|left-rail destination|nav destination"
    r")\b",
    re.IGNORECASE,
)
PAGE_CONTRACT_HINT_RE = re.compile(
    r"\b(account|settings|billing|dashboard|profile|admin panel|admin page)\b",
    re.IGNORECASE,
)
PUBLIC_SURFACE_HINT_RE = re.compile(
    r"\b(landing page|homepage|home page|pricing page|marketing site|marketing page|public-facing|public surface|hero section|hero)\b",
    re.IGNORECASE,
)
SKIP_DIR_NAMES = {".git", "node_modules", "dist", "build", ".next", ".nuxt", "__pycache__", "coverage", ".venv", "venv"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--brief",
        action="append",
        default=[],
        help="Creative brief path(s). Repeat in project -> phase -> ticket order when a brief stack exists.",
    )
    parser.add_argument("--qc-report", action="append", default=[], required=True, help="QC report path(s).")
    parser.add_argument("--ticket-path", help="Optional ticket markdown path with UI metadata.")
    parser.add_argument("--visual-review-report", required=True, help="Claude visual-review markdown artifact.")
    parser.add_argument("--deliverables-root", required=True, help="Root of the deliverable or repo being shipped.")
    parser.add_argument("--json-out", required=True, help="Where to write the visual-gate JSON report.")
    parser.add_argument("--markdown-out", required=True, help="Where to write the visual-gate markdown report.")
    return parser.parse_args()


def split_frontmatter(text: str) -> tuple[str, str]:
    if not text.startswith("---\n"):
        return "", text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return "", text
    return parts[1].strip(), parts[2].lstrip("\n")


def parse_frontmatter_map(path: Path) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return {}
    frontmatter_text, _ = split_frontmatter(text)
    if not frontmatter_text:
        return {}
    data = yaml.safe_load(frontmatter_text)
    return data if isinstance(data, dict) else {}


def walk_dirs(root: Path, max_depth: int = 6) -> list[Path]:
    discovered = []
    stack = [(root, 0)]
    while stack:
        current, depth = stack.pop()
        discovered.append(current)
        if depth >= max_depth:
            continue
        try:
            children = sorted(current.iterdir(), key=lambda child: child.name, reverse=True)
        except OSError:
            continue
        for child in children:
            if child.is_dir() and child.name not in SKIP_DIR_NAMES:
                stack.append((child, depth + 1))
    return discovered


def find_files_by_name(root: Path, names: list[str]) -> list[Path]:
    wanted = {name.lower() for name in names}
    matches = []
    if not wanted:
        return matches
    for directory in walk_dirs(root):
        try:
            children = sorted(directory.iterdir(), key=lambda child: child.name)
        except OSError:
            continue
        for child in children:
            if child.is_file() and child.name.lower() in wanted:
                matches.append(child.resolve())
    seen: set[str] = set()
    unique: list[Path] = []
    for path in matches:
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        unique.append(path)
    return unique


def coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value or "").strip().lower()
    return text in {"true", "yes", "y", "1", "pass", "passed"}


def coerce_string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, tuple):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value or "").strip()
    if not text:
        return []
    if text.startswith("[") and text.endswith("]"):
        try:
            parsed = yaml.safe_load(text)
        except yaml.YAMLError:
            parsed = None
        else:
            if isinstance(parsed, list):
                return [str(item).strip() for item in parsed if str(item).strip()]
    return [part.strip() for part in re.split(r"[\n,]+", text) if part.strip()]


def normalize_verdict(value: Any) -> str:
    text = str(value or "").strip().strip("*").upper()
    if text.startswith("PASS"):
        return "PASS"
    if text.startswith("REVISE"):
        return "REVISE"
    if text.startswith("FAIL"):
        return "FAIL"
    return text or "UNKNOWN"


def normalize_pass_fail(value: Any) -> str:
    if isinstance(value, bool):
        return "pass" if value else "fail"
    text = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    if text in {"pass", "passed", "ok", "yes", "true"}:
        return "pass"
    if text in {"fail", "failed", "no", "false"}:
        return "fail"
    if text in {"n/a", "na", "not_applicable", "not-applicable"}:
        return "not_applicable"
    return text or "unknown"


def normalize_yes_no(value: Any) -> str:
    if isinstance(value, bool):
        return "yes" if value else "no"
    text = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    if text in {"yes", "true"}:
        return "yes"
    if text in {"no", "false"}:
        return "no"
    if text in {"n/a", "na", "not_applicable", "not-applicable"}:
        return "not_applicable"
    return text or "unknown"


def detect_report_verdict(frontmatter: dict[str, Any], text: str) -> str:
    verdict = normalize_verdict(frontmatter.get("verdict"))
    if verdict != "UNKNOWN":
        return verdict
    match = VERDICT_HEADING_RE.search(text)
    if match:
        return normalize_verdict(match.group(1))
    match = VERDICT_BOLD_RE.search(text)
    if match:
        return normalize_verdict(match.group(1))
    return "UNKNOWN"


def read_report(path: Path) -> tuple[dict[str, Any], str]:
    text = path.read_text(encoding="utf-8")
    frontmatter_text, body = split_frontmatter(text)
    if not frontmatter_text:
        return {}, body
    data = yaml.safe_load(frontmatter_text)
    return (data if isinstance(data, dict) else {}), body


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    deliverables_root = Path(args.deliverables_root).expanduser().resolve()
    ticket_path = Path(args.ticket_path).expanduser().resolve() if args.ticket_path else None
    ticket_data = parse_frontmatter_map(ticket_path) if ticket_path and ticket_path.exists() else {}
    brief_paths = [Path(path).expanduser().resolve() for path in args.brief]
    qc_paths = [Path(path).expanduser().resolve() for path in args.qc_report]
    visual_review_path = Path(args.visual_review_report).expanduser().resolve()

    brief_text = "\n".join(path.read_text(encoding="utf-8") for path in brief_paths if path.exists())
    qc_text = "\n".join(path.read_text(encoding="utf-8") for path in qc_paths if path.exists())
    review_frontmatter, review_body = read_report(visual_review_path)
    review_text = review_body

    design_mode = str(ticket_data.get("design_mode", "")).strip()
    public_surface = bool(ticket_data.get("public_surface", False)) or bool(PUBLIC_SURFACE_HINT_RE.search(brief_text))
    page_contract_required = bool(ticket_data.get("page_contract_required", False)) or bool(
        PAGE_CONTRACT_HINT_RE.search(brief_text)
    )
    route_family_required = bool(ticket_data.get("route_family_required", False)) or bool(
        ROUTE_FAMILY_HINT_RE.search(brief_text)
    )
    existing_surface_redesign = bool(ticket_data.get("existing_surface_redesign", False))
    ui_work = bool(ticket_data.get("ui_work", False)) or design_mode in {"stitch_required", "concept_required", "implementation_only"}
    stitch_required = bool(ticket_data.get("stitch_required", False)) or design_mode == "stitch_required"

    qc_screenshot_refs = sorted(set(match.group(1) for match in SCREENSHOT_REF_RE.finditer(qc_text)))
    visual_gate_required = ui_work or stitch_required or public_surface or page_contract_required or route_family_required or bool(qc_screenshot_refs)

    screenshot_files = coerce_string_list(review_frontmatter.get("screenshot_files"))
    resolved_review_paths: list[Path] = []
    search_roots = [deliverables_root] + [path.parent for path in qc_paths]
    seen_paths: set[str] = set()
    for root in search_roots:
        for path in find_files_by_name(root, screenshot_files):
            key = str(path)
            if key in seen_paths:
                continue
            seen_paths.add(key)
            resolved_review_paths.append(path)

    review_files_lower = {name.lower() for name in screenshot_files}
    qc_refs_lower = {name.lower() for name in qc_screenshot_refs}
    covered_qc_refs = sorted(review_files_lower & qc_refs_lower)

    verdict = detect_report_verdict(review_frontmatter, review_text)
    composition_anchor_parity = normalize_pass_fail(review_frontmatter.get("composition_anchor_parity"))
    route_family_parity = normalize_pass_fail(review_frontmatter.get("route_family_parity"))
    page_contract_parity = normalize_pass_fail(review_frontmatter.get("page_contract_parity"))
    visual_quality_bar = normalize_pass_fail(review_frontmatter.get("visual_quality_bar"))
    generic_admin_drift = normalize_yes_no(review_frontmatter.get("generic_admin_drift"))
    duplicate_shell_chrome = normalize_yes_no(review_frontmatter.get("duplicate_shell_chrome"))
    stitch_runtime_parity = normalize_pass_fail(review_frontmatter.get("stitch_runtime_parity"))
    stitch_surface_traceability = normalize_pass_fail(review_frontmatter.get("stitch_surface_traceability"))
    token_only_basis = normalize_yes_no(review_frontmatter.get("token_only_basis"))
    inspected_images = coerce_bool(review_frontmatter.get("inspected_images"))

    checks: list[dict[str, Any]] = [
        {
            "name": "visual_gate_required",
            "ok": True,
            "details": "Governed UI/image-facing review detected." if visual_gate_required else "No governed UI/image-facing review requirement detected.",
        }
    ]

    if visual_gate_required:
        checks.extend(
            [
                {
                    "name": "visual_review_pass",
                    "ok": verdict == "PASS",
                    "details": f"Visual review verdict: {verdict}",
                },
                {
                    "name": "visual_review_inspected_images",
                    "ok": inspected_images,
                    "details": (
                        "Visual review frontmatter declares `inspected_images: true`."
                        if inspected_images
                        else "Visual review frontmatter does not declare `inspected_images: true`."
                    ),
                },
                {
                    "name": "visual_review_has_visual_verdict_section",
                    "ok": bool(VISUAL_VERDICT_HEADING_RE.search(review_text)),
                    "details": (
                        "Visual review includes `## Visual Verdict`."
                        if VISUAL_VERDICT_HEADING_RE.search(review_text)
                        else "Visual review is missing `## Visual Verdict`."
                    ),
                },
                {
                    "name": "visual_review_has_evidence_reviewed_section",
                    "ok": bool(EVIDENCE_REVIEWED_HEADING_RE.search(review_text)),
                    "details": (
                        "Visual review includes `## Evidence Reviewed`."
                        if EVIDENCE_REVIEWED_HEADING_RE.search(review_text)
                        else "Visual review is missing `## Evidence Reviewed`."
                    ),
                },
                {
                    "name": "visual_review_has_findings_section",
                    "ok": bool(FINDINGS_HEADING_RE.search(review_text)),
                    "details": (
                        "Visual review includes `## Findings`."
                        if FINDINGS_HEADING_RE.search(review_text)
                        else "Visual review is missing `## Findings`."
                    ),
                },
                {
                    "name": "visual_review_has_required_fixes_section",
                    "ok": bool(REQUIRED_FIXES_HEADING_RE.search(review_text)),
                    "details": (
                        "Visual review includes `## Required Fixes`."
                        if REQUIRED_FIXES_HEADING_RE.search(review_text)
                        else "Visual review is missing `## Required Fixes`."
                    ),
                },
                {
                    "name": "visual_review_references_runtime_screenshots",
                    "ok": bool(screenshot_files) and len(resolved_review_paths) == len(set(screenshot_files)),
                    "details": (
                        f"Visual review references {len(screenshot_files)} screenshot file(s); {len(resolved_review_paths)} resolved."
                        if screenshot_files
                        else "Visual review frontmatter does not list any `screenshot_files`."
                    ),
                },
                {
                    "name": "visual_review_covers_qc_runtime_screenshots",
                    "ok": bool(covered_qc_refs) if qc_screenshot_refs else True,
                    "details": (
                        f"Visual review covers {len(covered_qc_refs)} of {len(qc_screenshot_refs)} QC screenshot reference(s)."
                        if qc_screenshot_refs
                        else "QC report does not reference concrete screenshot filenames."
                    ),
                },
            ]
        )

        if stitch_required:
            checks.extend(
                [
                    {
                        "name": "visual_review_has_stitch_fidelity_section",
                        "ok": bool(STITCH_FIDELITY_HEADING_RE.search(review_text)),
                        "details": (
                            "Visual review includes `## Stitch Fidelity`."
                            if STITCH_FIDELITY_HEADING_RE.search(review_text)
                            else "Visual review is missing `## Stitch Fidelity`."
                        ),
                    },
                    {
                        "name": "visual_review_clears_stitch_runtime_parity",
                        "ok": stitch_runtime_parity == "pass",
                        "details": f"stitch_runtime_parity={stitch_runtime_parity}",
                    },
                    {
                        "name": "visual_review_clears_stitch_surface_traceability",
                        "ok": stitch_surface_traceability == "pass",
                        "details": f"stitch_surface_traceability={stitch_surface_traceability}",
                    },
                    {
                        "name": "visual_review_rejects_token_only_stitch_basis",
                        "ok": token_only_basis == "no",
                        "details": f"token_only_basis={token_only_basis}",
                    },
                ]
            )

        if public_surface:
            checks.extend(
                [
                    {
                        "name": "visual_review_clears_visual_quality_bar",
                        "ok": visual_quality_bar == "pass",
                        "details": f"visual_quality_bar={visual_quality_bar}",
                    },
                    {
                        "name": "visual_review_clears_composition_anchor_parity",
                        "ok": composition_anchor_parity == "pass",
                        "details": f"composition_anchor_parity={composition_anchor_parity}",
                    },
                ]
            )

        if page_contract_required:
            checks.append(
                {
                    "name": "visual_review_clears_page_contract_parity",
                    "ok": page_contract_parity == "pass",
                    "details": f"page_contract_parity={page_contract_parity}",
                }
            )

        if route_family_required:
            checks.extend(
                [
                    {
                        "name": "visual_review_clears_route_family_parity",
                        "ok": route_family_parity == "pass",
                        "details": f"route_family_parity={route_family_parity}",
                    },
                    {
                        "name": "visual_review_rejects_generic_admin_drift",
                        "ok": generic_admin_drift == "no",
                        "details": f"generic_admin_drift={generic_admin_drift}",
                    },
                    {
                        "name": "visual_review_rejects_duplicate_shell_chrome",
                        "ok": duplicate_shell_chrome == "no",
                        "details": f"duplicate_shell_chrome={duplicate_shell_chrome}",
                    },
                ]
            )

        if existing_surface_redesign and (public_surface or route_family_required):
            checks.append(
                {
                    "name": "visual_review_clears_existing_surface_composition_parity",
                    "ok": composition_anchor_parity == "pass",
                    "details": f"composition_anchor_parity={composition_anchor_parity}",
                }
            )

    final_verdict = "PASS" if all(check["ok"] for check in checks) else "FAIL"

    return {
        "generated_at": datetime.now().strftime(TIMESTAMP_FMT),
        "ticket_path": str(ticket_path) if ticket_path else "",
        "deliverables_root": str(deliverables_root),
        "visual_review_report": str(visual_review_path),
        "briefs": [str(path) for path in brief_paths],
        "qc_reports": [str(path) for path in qc_paths],
        "brief_analysis": {
            "ui_work": ui_work,
            "design_mode": design_mode,
            "stitch_required": stitch_required,
            "public_surface": public_surface,
            "page_contract_required": page_contract_required,
            "route_family_required": route_family_required,
            "existing_surface_redesign": existing_surface_redesign,
            "visual_gate_required": visual_gate_required,
        },
        "qc_analysis": {
            "screenshot_refs": qc_screenshot_refs,
            "mentions_qc_visual_evidence": bool(QC_SCREENSHOT_HINT_RE.search(qc_text)),
        },
        "review_analysis": {
            "verdict": verdict,
            "inspected_images": inspected_images,
            "screenshot_files": screenshot_files,
            "resolved_screenshot_paths": [str(path) for path in resolved_review_paths],
            "composition_anchor_parity": composition_anchor_parity,
            "route_family_parity": route_family_parity,
            "page_contract_parity": page_contract_parity,
            "visual_quality_bar": visual_quality_bar,
            "generic_admin_drift": generic_admin_drift,
            "duplicate_shell_chrome": duplicate_shell_chrome,
            "stitch_runtime_parity": stitch_runtime_parity,
            "stitch_surface_traceability": stitch_surface_traceability,
            "token_only_basis": token_only_basis,
        },
        "checks": checks,
        "verdict": final_verdict,
    }


def render_markdown(report: dict[str, Any]) -> str:
    def escape_cell(value: str) -> str:
        return value.replace("|", "\\|")

    lines = [
        "# Visual Gate Report",
        "",
        f"**Generated:** {report['generated_at']}",
        f"**Visual review report:** {report['visual_review_report']}",
        f"**Deliverables root:** {report['deliverables_root']}",
        f"**Verdict:** {report['verdict']}",
        "",
        "## Visual Review Summary",
        "",
        f"- UI work detected: {'yes' if report['brief_analysis']['ui_work'] else 'no'}",
        f"- Design mode: {report['brief_analysis']['design_mode'] or 'none'}",
        f"- Public surface: {'yes' if report['brief_analysis']['public_surface'] else 'no'}",
        f"- Page contracts required: {'yes' if report['brief_analysis']['page_contract_required'] else 'no'}",
        f"- Route family required: {'yes' if report['brief_analysis']['route_family_required'] else 'no'}",
        f"- Existing-surface redesign: {'yes' if report['brief_analysis']['existing_surface_redesign'] else 'no'}",
        f"- Visual gate required: {'yes' if report['brief_analysis']['visual_gate_required'] else 'no'}",
        "",
        f"- Visual review verdict: {report['review_analysis']['verdict']}",
        f"- Inspected images: {'yes' if report['review_analysis']['inspected_images'] else 'no'}",
        f"- Screenshot files listed: {len(report['review_analysis']['screenshot_files'])}",
    ]
    if report["brief_analysis"]["stitch_required"]:
        lines.extend(
            [
                f"- Stitch runtime parity: {report['review_analysis']['stitch_runtime_parity']}",
                f"- Stitch surface traceability: {report['review_analysis']['stitch_surface_traceability']}",
                f"- Token-only Stitch basis: {report['review_analysis']['token_only_basis']}",
            ]
        )
    lines.extend(
        [
            "",
            "## Checks",
            "",
            "| Check | Status | Details |",
            "|------|--------|---------|",
        ]
    )
    for check in report["checks"]:
        lines.append(
            f"| {check['name']} | {'PASS' if check['ok'] else 'FAIL'} | {escape_cell(check['details'])} |"
        )

    lines.extend(["", "## Resolved Screenshot Paths", ""])
    resolved_paths = report["review_analysis"].get("resolved_screenshot_paths") or []
    if resolved_paths:
        for path in resolved_paths:
            lines.append(f"- {path}")
    else:
        lines.append("- None")
    lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    args = parse_args()
    json_out = Path(args.json_out).expanduser().resolve()
    markdown_out = Path(args.markdown_out).expanduser().resolve()
    json_out.parent.mkdir(parents=True, exist_ok=True)
    markdown_out.parent.mkdir(parents=True, exist_ok=True)

    report = build_report(args)
    json_out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    markdown_out.write_text(render_markdown(report), encoding="utf-8")

    print(f"verdict={report['verdict']}")
    for check in report["checks"]:
        print(f"{check['name']}={'PASS' if check['ok'] else 'FAIL'}")
    print(f"json_report={json_out}")
    print(f"markdown_report={markdown_out}")
    return 0 if report["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
