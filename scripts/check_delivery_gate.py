#!/usr/bin/env python3
"""
Fail delivery when required trust artifacts are missing or non-passing.

This script is the mechanical pre-delivery blocker. It reads generated trust
artifacts rather than agent summaries and exits non-zero unless the delivery is
backed by passing evidence.

Usage:
    python3 scripts/check_delivery_gate.py \
      --verification-profile software \
      --claim-ledger-json claim-ledger.json \
      --credibility-report credibility-gate.md \
      --polish-gate-json polish-gate.json \
      --fresh-checkout-json fresh-checkout.json \
      --verification-results-report verification-results.md \
      --deliverables-root /path/to/deliverable \
      --fresh-checkout-mode auto \
      --json-out delivery-gate.json \
      --markdown-out delivery-gate.md
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

TIMESTAMP_FMT = "%Y-%m-%dT%H:%M:%S"
VERIFICATION_PROFILES = ("general", "software", "data", "research", "static", "media")
FRESH_CHECKOUT_MODES = ("auto", "required", "skip")
VERIFICATION_REPORT_MODES = ("auto", "required", "skip")
VERDICT_FRONTMATTER_RE = re.compile(r"^verdict:\s*\"?([^\n\"]+)\"?\s*$", re.IGNORECASE | re.MULTILINE)
VERDICT_HEADING_RE = re.compile(r"^## Verdict:\s*(.+?)\s*$", re.IGNORECASE | re.MULTILINE)
VERDICT_BOLD_RE = re.compile(r"\*\*Verdict:\s*\*?\*?([A-Z]+)\*?\*?\*\*", re.IGNORECASE)
VERDICT_SIMPLE_BOLD_RE = re.compile(r"\*\*Verdict:\*\*\s*([A-Z]+)\b", re.IGNORECASE)
LIMITATIONS_HEADING_RE = re.compile(r"^##\s+(Known\s+)?Limitations\b", re.IGNORECASE | re.MULTILINE)
RESULT_ITEM_HEADING_RE = re.compile(r"^###\s+([A-Z]{2,}-\d+):\s*(.+?)\s+—\s+(.+?)\s*$", re.MULTILINE)
FULL_RESULTS_HEADING_RE = re.compile(r"^##\s+Full Results\b", re.IGNORECASE | re.MULTILINE)
TABLE_ROW_RE = re.compile(r"^\|(.+)\|\s*$")
PROOF_TYPES = (
    "automated_test",
    "build_check",
    "runtime_proof",
    "inspection_check",
    "artifact_check",
    "external_validation",
    "manual_review",
)
EXECUTION_CLASSES = ("EXECUTABLE", "INFRASTRUCTURE-DEPENDENT", "MANUAL")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--verification-profile",
        choices=VERIFICATION_PROFILES,
        default="general",
        help="Verification profile that determines required proof.",
    )
    parser.add_argument("--claim-ledger-json", required=True, help="Path to build_claim_ledger JSON output.")
    parser.add_argument("--credibility-report", required=True, help="Path to the credibility gate markdown report.")
    parser.add_argument(
        "--polish-gate-json",
        action="append",
        default=[],
        help="check_polish_gate JSON output(s). Required when --require-polish-gate is set.",
    )
    parser.add_argument(
        "--stitch-gate-json",
        action="append",
        default=[],
        help="check_stitch_gate JSON output(s). Required when --require-stitch-gate is set.",
    )
    parser.add_argument(
        "--visual-gate-json",
        action="append",
        default=[],
        help="check_visual_gate JSON output(s). Required when --require-visual-gate is set.",
    )
    parser.add_argument(
        "--fresh-checkout-json",
        action="append",
        default=[],
        help="verify_release JSON output(s). Required when --require-fresh-checkout is set.",
    )
    parser.add_argument(
        "--verification-results-report",
        action="append",
        default=[],
        help="Verification results report(s) in markdown or JSON. Accepts legacy test-manifest results artifacts too.",
    )
    parser.add_argument("--deliverables-root", required=True, help="Root of the deliverable or repo being shipped.")
    parser.add_argument(
        "--require-polish-gate",
        action="store_true",
        help="Require at least one PASS artifact polish gate report.",
    )
    parser.add_argument(
        "--require-stitch-gate",
        action="store_true",
        help="Require at least one PASS stitch gate report for Stitch-governed UI work.",
    )
    parser.add_argument(
        "--require-visual-gate",
        action="store_true",
        help="Require at least one PASS visual gate report for governed UI/image-facing work.",
    )
    parser.add_argument(
        "--fresh-checkout-mode",
        choices=FRESH_CHECKOUT_MODES,
        default="auto",
        help="Whether fresh-checkout PASS evidence is required.",
    )
    parser.add_argument(
        "--verification-report-mode",
        choices=VERIFICATION_REPORT_MODES,
        default="auto",
        help="Whether verification-results proof evidence is required.",
    )
    parser.add_argument("--max-unverified", type=int, default=None, help="Allowed UNVERIFIED claims. Defaults by profile.")
    parser.add_argument("--max-contradicted", type=int, default=None, help="Allowed CONTRADICTED claims. Defaults by profile.")
    parser.add_argument("--max-stale", type=int, default=None, help="Allowed STALE claims. Defaults by profile.")
    parser.add_argument("--json-out", required=True, help="Where to write the gate JSON report.")
    parser.add_argument("--markdown-out", required=True, help="Where to write the gate markdown report.")
    return parser.parse_args()


def read_json(path_str: str) -> dict:
    path = Path(path_str).expanduser().resolve()
    return json.loads(path.read_text(encoding="utf-8"))


def detect_report_verdict(text: str) -> str | None:
    for regex in (VERDICT_FRONTMATTER_RE, VERDICT_HEADING_RE, VERDICT_BOLD_RE, VERDICT_SIMPLE_BOLD_RE):
        match = regex.search(text)
        if match:
            groups = [group for group in match.groups() if group]
            if groups:
                return groups[0].strip().strip("*")
    return None


def profile_threshold_defaults(profile: str) -> dict[str, int | None]:
    if profile == "software":
        return {
            "max_unverified": 0,
            "max_contradicted": 0,
            "max_stale": 0,
        }
    return {
        "max_unverified": None,
        "max_contradicted": 0,
        "max_stale": 0,
    }


def resolve_fresh_checkout_requirement(profile: str, mode: str) -> bool:
    if mode == "required":
        return True
    if mode == "skip":
        return False
    return profile == "software"


def resolve_verification_report_requirement(profile: str, mode: str) -> bool:
    if mode == "required":
        return True
    if mode == "skip":
        return False
    return profile in {"software", "data", "research", "static", "media"}


def threshold_ok(actual: int, maximum: int | None) -> bool:
    if maximum is None:
        return True
    return actual <= maximum


def threshold_label(maximum: int | None) -> str:
    return "ignored" if maximum is None else str(maximum)


def split_markdown_row(line: str) -> list[str]:
    match = TABLE_ROW_RE.match(line.strip())
    if not match:
        return []
    return [cell.strip() for cell in match.group(1).split("|")]


def normalize_status(value: str) -> str:
    text = value.strip().strip("*_").strip().upper()
    if text.startswith("PASS"):
        return "PASS"
    if "CODE_DEFECT" in text:
        return "CODE_DEFECT"
    if "INFRA_MISSING" in text:
        return "INFRA_MISSING"
    if "HARNESS_FLAKY" in text:
        return "HARNESS_FLAKY"
    if "SPEC_AMBIGUOUS" in text:
        return "SPEC_AMBIGUOUS"
    if "MANUAL" in text:
        return "MANUAL"
    if "FAIL" in text:
        return "FAIL"
    if "SKIP" in text:
        return "SKIPPED"
    return text or "UNKNOWN"


def infer_proof_type(title: str, body: str) -> str:
    haystack = f"{title}\n{body}".lower()
    if any(token in haystack for token in ("voiceover", "screen reader", "manual review", "manual item", "human judgment")):
        return "manual_review"
    if any(token in haystack for token in ("ground truth", "citation", "doi", "cms", "bls", "external source", "reference checking", "schema authority")):
        return "external_validation"
    if any(token in haystack for token in ("readme", "deployment guide", "supporting artifacts", "limitations", "artifact", "screenshot evidence", "exported file")):
        return "artifact_check"
    if any(token in haystack for token in ("build", "install", "compile", "typecheck", "lint", "npm audit", "pnpm audit", "cargo audit", "prisma generate")):
        return "build_check"
    if any(token in haystack for token in (".test.", "vitest", "jest", "pytest", "playwright", "cargo test", "unit test", "integration test", "test suite", "dedicated test file")):
        return "automated_test"
    if any(token in haystack for token in ("signup", "login", "user flow", "critical flow", "browser testing", "network throttle", "launch verification", "smoke test", "playthrough", "running application")):
        return "runtime_proof"
    return "inspection_check"


def empty_proof_summary() -> dict:
    return {
        "total_items": 0,
        "passed_items": 0,
        "non_pass_items": 0,
        "execution_class_counts": {
            execution_class: 0 for execution_class in EXECUTION_CLASSES
        },
        "by_type": {
            proof_type: {"total": 0, "passed": 0, "non_pass": 0}
            for proof_type in PROOF_TYPES
        },
    }


def normalize_execution_class(value: str) -> str | None:
    text = value.strip().upper().replace("_", "-")
    if "INFRA" in text:
        return "INFRASTRUCTURE-DEPENDENT"
    if "MANUAL" in text:
        return "MANUAL"
    if "EXECUTABLE" in text:
        return "EXECUTABLE"
    return None


def accumulate_proof(summary: dict, proof_type: str, status: str, execution_class: str | None = None) -> None:
    if proof_type not in summary["by_type"]:
        return
    summary["total_items"] += 1
    summary["by_type"][proof_type]["total"] += 1
    if execution_class in summary["execution_class_counts"]:
        summary["execution_class_counts"][execution_class] += 1
    if status == "PASS":
        summary["passed_items"] += 1
        summary["by_type"][proof_type]["passed"] += 1
    else:
        summary["non_pass_items"] += 1
        summary["by_type"][proof_type]["non_pass"] += 1


def parse_full_results_table(text: str) -> dict | None:
    match = FULL_RESULTS_HEADING_RE.search(text)
    if not match:
        return None
    lines = text[match.end():].splitlines()
    header = None
    summary = empty_proof_summary()
    for line in lines:
        if line.startswith("## ") and not line.startswith("## Full Results"):
            break
        if not line.strip().startswith("|"):
            continue
        cells = split_markdown_row(line)
        if not cells:
            continue
        if set(cells[0]) == {"-"}:
            continue
        if header is None:
            header = [cell.lower() for cell in cells]
            continue
        row = dict(zip(header, cells))
        proof_type = row.get("proof type") or row.get("proof_type")
        result = row.get("result") or row.get("status") or row.get("classification")
        execution_class = (
            row.get("executability")
            or row.get("execution class")
            or row.get("execution_class")
        )
        if proof_type and result:
            accumulate_proof(
                summary,
                proof_type.strip(),
                normalize_status(result),
                normalize_execution_class(execution_class) if execution_class else None,
            )
    return None if summary["total_items"] == 0 else summary


def parse_legacy_heading_results(text: str) -> dict:
    summary = empty_proof_summary()
    matches = list(RESULT_ITEM_HEADING_RE.finditer(text))
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        title = match.group(2).strip()
        status = normalize_status(match.group(3))
        body = text[start:end]
        proof_type = infer_proof_type(title, body)
        execution_class = None
        upper_body = body.upper()
        if "INFRA_MISSING" in upper_body or "INFRASTRUCTURE-DEPENDENT" in upper_body:
            execution_class = "INFRASTRUCTURE-DEPENDENT"
        elif "MANUAL" in upper_body:
            execution_class = "MANUAL"
        elif "EXECUTABLE" in upper_body:
            execution_class = "EXECUTABLE"
        accumulate_proof(summary, proof_type, status, execution_class)
    return summary


def parse_verification_results_report(path_str: str) -> dict:
    path = Path(path_str).expanduser().resolve()
    if path.suffix.lower() == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        summary = payload.get("proof_summary") or payload.get("summary", {}).get("proof_summary")
        if summary is None:
            raise ValueError(f"{path} does not contain proof_summary")
        parsed_summary = empty_proof_summary()
        parsed_summary["total_items"] = int(summary.get("total_items", 0))
        parsed_summary["passed_items"] = int(summary.get("passed_items", 0))
        parsed_summary["non_pass_items"] = int(summary.get("non_pass_items", 0))
        for proof_type in PROOF_TYPES:
            source_row = summary.get("by_type", {}).get(proof_type, {})
            parsed_summary["by_type"][proof_type]["total"] = int(source_row.get("total", 0))
            parsed_summary["by_type"][proof_type]["passed"] = int(source_row.get("passed", 0))
            parsed_summary["by_type"][proof_type]["non_pass"] = int(source_row.get("non_pass", 0))
        for execution_class in EXECUTION_CLASSES:
            parsed_summary["execution_class_counts"][execution_class] = int(
                summary.get("execution_class_counts", {}).get(execution_class, 0)
            )
        summary = parsed_summary
    else:
        text = path.read_text(encoding="utf-8")
        summary = parse_full_results_table(text) or parse_legacy_heading_results(text)
    return {
        "path": str(path),
        "summary": summary,
    }


def aggregate_proof_summaries(reports: list[dict]) -> dict:
    aggregate = empty_proof_summary()
    for report in reports:
        summary = report["summary"]
        aggregate["total_items"] += summary["total_items"]
        aggregate["passed_items"] += summary["passed_items"]
        aggregate["non_pass_items"] += summary["non_pass_items"]
        for execution_class in EXECUTION_CLASSES:
            aggregate["execution_class_counts"][execution_class] += summary.get(
                "execution_class_counts", {}
            ).get(execution_class, 0)
        for proof_type in PROOF_TYPES:
            aggregate["by_type"][proof_type]["total"] += summary["by_type"][proof_type]["total"]
            aggregate["by_type"][proof_type]["passed"] += summary["by_type"][proof_type]["passed"]
            aggregate["by_type"][proof_type]["non_pass"] += summary["by_type"][proof_type]["non_pass"]
    return aggregate


def proof_requirements_for_profile(profile: str) -> list[dict]:
    if profile == "software":
        return [
            {"name": "build_checks_present", "proof_types": ["build_check"], "min_pass": 1},
            {"name": "automated_tests_present", "proof_types": ["automated_test"], "min_pass": 1},
            {
                "name": "structural_or_runtime_proof_present",
                "proof_types": ["runtime_proof", "inspection_check", "artifact_check"],
                "min_pass": 1,
            },
        ]
    if profile == "data":
        return [
            {"name": "artifact_checks_present", "proof_types": ["artifact_check"], "min_pass": 1},
            {
                "name": "validation_proof_present",
                "proof_types": ["inspection_check", "external_validation"],
                "min_pass": 1,
            },
        ]
    if profile == "research":
        return [
            {"name": "inspection_checks_present", "proof_types": ["inspection_check"], "min_pass": 1},
            {"name": "external_validation_present", "proof_types": ["external_validation"], "min_pass": 1},
        ]
    if profile in {"static", "media"}:
        return [
            {"name": "artifact_checks_present", "proof_types": ["artifact_check"], "min_pass": 1},
            {
                "name": "review_or_inspection_present",
                "proof_types": ["manual_review", "inspection_check"],
                "min_pass": 1,
            },
        ]
    return []


def has_limitations(deliverables_root: Path) -> tuple[bool, list[str]]:
    found = []

    limitations_file = deliverables_root / "LIMITATIONS.md"
    if limitations_file.exists():
        found.append(str(limitations_file))

    for markdown_path in sorted(deliverables_root.rglob("*.md")):
        if not markdown_path.is_file():
            continue
        try:
            text = markdown_path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if LIMITATIONS_HEADING_RE.search(text):
            found.append(f"{markdown_path}#Limitations")

    return bool(found), found


def build_report(args: argparse.Namespace) -> dict:
    claim_ledger = read_json(args.claim_ledger_json)
    credibility_path = Path(args.credibility_report).expanduser().resolve()
    credibility_text = credibility_path.read_text(encoding="utf-8")
    credibility_verdict = detect_report_verdict(credibility_text)

    deliverables_root = Path(args.deliverables_root).expanduser().resolve()
    limitations_ok, limitations_evidence = has_limitations(deliverables_root)

    threshold_defaults = profile_threshold_defaults(args.verification_profile)
    max_unverified = args.max_unverified if args.max_unverified is not None else threshold_defaults["max_unverified"]
    max_contradicted = args.max_contradicted if args.max_contradicted is not None else threshold_defaults["max_contradicted"]
    max_stale = args.max_stale if args.max_stale is not None else threshold_defaults["max_stale"]

    fresh_reports = [read_json(path) for path in args.fresh_checkout_json]
    fresh_failures = [report for report in fresh_reports if report.get("verdict") != "PASS"]
    fresh_checkout_required = resolve_fresh_checkout_requirement(args.verification_profile, args.fresh_checkout_mode)
    fresh_required_ok = True
    if fresh_checkout_required:
        fresh_required_ok = bool(fresh_reports) and not fresh_failures

    verification_reports = [parse_verification_results_report(path) for path in args.verification_results_report]
    verification_required = resolve_verification_report_requirement(
        args.verification_profile, args.verification_report_mode
    )
    verification_required_ok = True
    if verification_required:
        verification_required_ok = bool(verification_reports)
    proof_summary = aggregate_proof_summaries(verification_reports) if verification_reports else empty_proof_summary()
    proof_requirement_results = []
    if verification_reports:
        for requirement in proof_requirements_for_profile(args.verification_profile):
            passed = sum(proof_summary["by_type"][proof_type]["passed"] for proof_type in requirement["proof_types"])
            proof_requirement_results.append(
                {
                    "name": requirement["name"],
                    "ok": passed >= requirement["min_pass"],
                    "details": (
                        f"proof_types={','.join(requirement['proof_types'])}; "
                        f"passed={passed}; required>={requirement['min_pass']}"
                    ),
                }
            )

    stitch_reports = [read_json(path) for path in args.stitch_gate_json]
    stitch_failures = [report for report in stitch_reports if report.get("verdict") != "PASS"]
    stitch_required_ok = True
    if args.require_stitch_gate:
        stitch_required_ok = bool(stitch_reports) and not stitch_failures

    visual_reports = [read_json(path) for path in args.visual_gate_json]
    visual_failures = [report for report in visual_reports if report.get("verdict") != "PASS"]
    visual_required_ok = True
    if args.require_visual_gate:
        visual_required_ok = bool(visual_reports) and not visual_failures

    polish_reports = [read_json(path) for path in args.polish_gate_json]
    polish_failures = [report for report in polish_reports if report.get("verdict") != "PASS"]
    polish_required_ok = True
    if args.require_polish_gate:
        polish_required_ok = bool(polish_reports) and not polish_failures

    summary = claim_ledger.get("summary", {})
    contradicted = int(summary.get("CONTRADICTED", 0))
    unverified = int(summary.get("UNVERIFIED", 0))
    stale = int(summary.get("STALE", 0))

    checks = [
        {
            "name": "credibility_report_pass",
            "ok": credibility_verdict == "PASS",
            "details": f"Credibility verdict: {credibility_verdict or 'missing'}",
        },
        {
            "name": "claim_ledger_thresholds",
            "ok": (
                threshold_ok(contradicted, max_contradicted)
                and threshold_ok(unverified, max_unverified)
                and threshold_ok(stale, max_stale)
            ),
            "details": (
                f"CONTRADICTED={contradicted} (max {threshold_label(max_contradicted)}), "
                f"UNVERIFIED={unverified} (max {threshold_label(max_unverified)}), "
                f"STALE={stale} (max {threshold_label(max_stale)})"
            ),
        },
        {
            "name": "limitations_present",
            "ok": limitations_ok,
            "details": ", ".join(limitations_evidence) if limitations_evidence else "No LIMITATIONS.md or README limitations section found.",
        },
        {
            "name": "verification_results_present",
            "ok": verification_required_ok,
            "details": (
                "Not required."
                if not verification_required
                else (
                    f"{len(verification_reports)} verification report(s) parsed."
                    if verification_required_ok
                    else "Missing verification-results PASS evidence."
                )
            ),
        },
        {
            "name": "polish_gate_pass",
            "ok": polish_required_ok,
            "details": (
                "Not required."
                if not args.require_polish_gate
                else (
                    "All polish gate reports passed."
                    if polish_required_ok
                    else "Missing artifact-polish PASS evidence."
                )
            ),
        },
        {
            "name": "stitch_gate_pass",
            "ok": stitch_required_ok,
            "details": (
                "Not required."
                if not args.require_stitch_gate
                else (
                    "All stitch gate reports passed."
                    if stitch_required_ok
                    else "Missing Stitch PASS evidence."
                )
            ),
        },
        {
            "name": "visual_gate_pass",
            "ok": visual_required_ok,
            "details": (
                "Not required."
                if not args.require_visual_gate
                else (
                    "All visual gate reports passed."
                    if visual_required_ok
                    else "Missing visual-review PASS evidence."
                )
            ),
        },
        {
            "name": "fresh_checkout_pass",
            "ok": fresh_required_ok,
            "details": (
                "Not required."
                if not fresh_checkout_required
                else (
                    "All fresh-checkout reports passed."
                    if fresh_required_ok
                    else "Missing fresh-checkout PASS evidence."
                )
            ),
        },
    ]
    checks.extend(proof_requirement_results)

    verdict = "PASS" if all(check["ok"] for check in checks) else "FAIL"

    return {
        "generated_at": datetime.now().strftime(TIMESTAMP_FMT),
        "verification_profile": args.verification_profile,
        "deliverables_root": str(deliverables_root),
        "claim_ledger_json": str(Path(args.claim_ledger_json).expanduser().resolve()),
        "credibility_report": str(credibility_path),
        "polish_gate_reports": [str(Path(path).expanduser().resolve()) for path in args.polish_gate_json],
        "require_polish_gate": bool(args.require_polish_gate),
        "stitch_gate_reports": [str(Path(path).expanduser().resolve()) for path in args.stitch_gate_json],
        "require_stitch_gate": bool(args.require_stitch_gate),
        "visual_gate_reports": [str(Path(path).expanduser().resolve()) for path in args.visual_gate_json],
        "require_visual_gate": bool(args.require_visual_gate),
        "fresh_checkout_reports": [str(Path(path).expanduser().resolve()) for path in args.fresh_checkout_json],
        "fresh_checkout_mode": args.fresh_checkout_mode,
        "require_fresh_checkout": fresh_checkout_required,
        "verification_results_reports": [report["path"] for report in verification_reports],
        "verification_report_mode": args.verification_report_mode,
        "require_verification_results": verification_required,
        "proof_summary": proof_summary,
        "thresholds": {
            "max_unverified": max_unverified,
            "max_contradicted": max_contradicted,
            "max_stale": max_stale,
        },
        "checks": checks,
        "verdict": verdict,
    }


def render_markdown(report: dict) -> str:
    def escape_cell(value: str) -> str:
        return value.replace("|", "\\|")

    lines = [
        "# Delivery Gate Report",
        "",
        f"**Generated:** {report['generated_at']}",
        f"**Verification profile:** {report['verification_profile']}",
        f"**Deliverables root:** {report['deliverables_root']}",
        f"**Verdict:** {report['verdict']}",
        "",
        "## Proof Summary",
        "",
        f"**Verification reports:** {len(report['verification_results_reports'])}",
        f"**Total proof items parsed:** {report['proof_summary']['total_items']}",
        f"**PASS proof items:** {report['proof_summary']['passed_items']}",
        f"**Non-PASS proof items:** {report['proof_summary']['non_pass_items']}",
        f"**Executable items:** {report['proof_summary']['execution_class_counts']['EXECUTABLE']}",
        f"**Infra-dependent items:** {report['proof_summary']['execution_class_counts']['INFRASTRUCTURE-DEPENDENT']}",
        f"**Manual items:** {report['proof_summary']['execution_class_counts']['MANUAL']}",
        "",
        "| Proof Type | Total | PASS | Non-PASS |",
        "|-----------|-------|------|----------|",
    ]
    for proof_type in PROOF_TYPES:
        proof_row = report["proof_summary"]["by_type"][proof_type]
        lines.append(
            f"| {proof_type} | {proof_row['total']} | {proof_row['passed']} | {proof_row['non_pass']} |"
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
        details = escape_cell(check["details"])
        lines.append(
            f"| {check['name']} | {'PASS' if check['ok'] else 'FAIL'} | {details} |"
        )
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
