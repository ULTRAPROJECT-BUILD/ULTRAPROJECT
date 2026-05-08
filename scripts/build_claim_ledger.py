#!/usr/bin/env python3
"""
Build a deterministic claim ledger from claim-bearing docs and verifier output.

This script is intentionally conservative. It extracts obvious readiness and
verification claims from docs, then attempts to match them against fresh-copy
verification evidence. Claims that cannot be grounded are left UNVERIFIED
instead of being guessed into a passing state.

Usage:
    python3 scripts/build_claim_ledger.py \
      --verification-profile software \
      --doc README.md \
      --fresh-checkout-json fresh-checkout.json \
      --json-out claim-ledger.json \
      --markdown-out claim-ledger.md
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

BASE_CLAIM_PATTERNS = [
    (re.compile(r"\bready to ship\b", re.IGNORECASE), "readiness"),
    (re.compile(r"\bready for delivery\b", re.IGNORECASE), "readiness"),
    (re.compile(r"\bproduction[- ]ready\b", re.IGNORECASE), "readiness"),
    (re.compile(r"\benterprise[- ]grade\b", re.IGNORECASE), "readiness"),
]

PROFILE_CLAIM_PATTERNS = {
    "software": [
        (re.compile(r"\ball tests? passing\b", re.IGNORECASE), "tests"),
        (re.compile(r"\bfresh (?:clone|checkout|copy) workflow verified\b", re.IGNORECASE), "fresh_checkout"),
        (re.compile(r"\bfresh[- ]checkout verified\b", re.IGNORECASE), "fresh_checkout"),
        (re.compile(r"\bzero warnings\b", re.IGNORECASE), "warnings"),
        (re.compile(r"\bzero crashes\b", re.IGNORECASE), "stability"),
        (re.compile(r"\b\d+\s*/\s*\d+\s+tests?\s+passing\b", re.IGNORECASE), "tests"),
        (re.compile(r"\bcoverage\b[^\n]*\b\d+(?:\.\d+)?%", re.IGNORECASE), "coverage"),
        (
            re.compile(
                r"\b(?:startup|response|latency|performance)\b[^\n]*\b\d+(?:\.\d+)?(?:\s*(?:ms|s|sec|seconds|min|minutes|hours))?",
                re.IGNORECASE,
            ),
            "metric",
        ),
        (
            re.compile(
                r"\bzero (?:critical|high)(?: and (?:critical|high))? (?:dependency )?vulnerabilities\b",
                re.IGNORECASE,
            ),
            "security",
        ),
    ],
    "data": [
        (re.compile(r"\bcoverage\b[^\n]*\b\d+(?:\.\d+)?%", re.IGNORECASE), "coverage"),
        (re.compile(r"\bcompleteness\b[^\n]*\b\d+(?:\.\d+)?%", re.IGNORECASE), "coverage"),
        (re.compile(r"\bschema (?:validated|validation)\b", re.IGNORECASE), "schema"),
        (re.compile(r"\b(?:anomal(?:y|ies)|outlier(?:s)?)\b[^\n]*\b\d+\b", re.IGNORECASE), "quality"),
        (
            re.compile(
                r"\b(?:rows|records|entities|relationships)\b[^\n]*\b\d+(?:,\d{3})*(?:\.\d+)?\b",
                re.IGNORECASE,
            ),
            "metric",
        ),
    ],
    "research": [
        (re.compile(r"\b(?:sources?|citations?|references?)\b[^\n]*\b\d+(?:,\d{3})*(?:\.\d+)?\b", re.IGNORECASE), "sources"),
        (re.compile(r"\bmethodolog(?:y|ical)\b", re.IGNORECASE), "methodology"),
        (re.compile(r"\bconfidence\b[^\n]*\b(?:high|medium|low|\d+(?:\.\d+)?%)", re.IGNORECASE), "confidence"),
    ],
    "static": [
        (re.compile(r"\b(?:exported|rendered|print-ready|ready for print)\b", re.IGNORECASE), "artifact"),
        (re.compile(r"\b\d{3,5}\s*[x×]\s*\d{3,5}\b", re.IGNORECASE), "metric"),
    ],
    "media": [
        (re.compile(r"\b(?:rendered|exported)\b", re.IGNORECASE), "artifact"),
        (re.compile(r"\b(?:duration|runtime)\b[^\n]*\b\d+(?::\d{2}){1,2}\b", re.IGNORECASE), "metric"),
        (re.compile(r"\b\d{3,5}\s*[x×]\s*\d{3,5}\b", re.IGNORECASE), "metric"),
        (re.compile(r"\b\d+(?:\.\d+)?\s*fps\b", re.IGNORECASE), "metric"),
    ],
    "general": [],
}

FENCE_RE = re.compile(r"^\s*```")
WHITESPACE_RE = re.compile(r"\s+")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--verification-profile",
        choices=VERIFICATION_PROFILES,
        default="general",
        help="Verification profile for claim extraction and classification.",
    )
    parser.add_argument("--doc", action="append", default=[], help="Claim-bearing doc to scan. Repeat as needed.")
    parser.add_argument(
        "--fresh-checkout-json",
        action="append",
        default=[],
        help="verify_release JSON report. Repeat as needed.",
    )
    parser.add_argument("--json-out", required=True, help="Path to write ledger JSON.")
    parser.add_argument("--markdown-out", required=True, help="Path to write ledger markdown.")
    return parser.parse_args()


def claim_patterns_for_profile(profile: str) -> list[tuple[re.Pattern[str], str]]:
    return BASE_CLAIM_PATTERNS + PROFILE_CLAIM_PATTERNS.get(profile, [])


def normalize_space(text: str) -> str:
    return WHITESPACE_RE.sub(" ", text.strip())


def read_doc_claims(path: Path, claim_patterns: list[tuple[re.Pattern[str], str]]) -> list[dict]:
    claims = []
    text = path.read_text(encoding="utf-8")
    in_code_fence = False
    seen = set()

    for line_no, raw_line in enumerate(text.splitlines(), start=1):
        if FENCE_RE.match(raw_line):
            in_code_fence = not in_code_fence
            continue
        if in_code_fence:
            continue

        line = normalize_space(raw_line)
        if not line:
            continue

        for pattern, claim_type in claim_patterns:
            if not pattern.search(line):
                continue
            key = (line.lower(), line_no)
            if key in seen:
                continue
            seen.add(key)
            claims.append(
                {
                    "claim": line,
                    "claim_type": claim_type,
                    "source_file": str(path.resolve()),
                    "line": line_no,
                }
            )
            break
    return claims


def load_verifier_reports(paths: list[str]) -> list[dict]:
    reports = []
    for raw_path in paths:
        path = Path(raw_path).expanduser().resolve()
        data = json.loads(path.read_text(encoding="utf-8"))
        data["_path"] = str(path)
        reports.append(data)
    return reports


def collect_verifier_context(reports: list[dict]) -> dict:
    combined_outputs = []
    any_fail = False
    any_test_fail = False
    any_test_pass = False
    all_pass = bool(reports)
    total_warning_lines = 0

    for report in reports:
        if report.get("verdict") != "PASS":
            any_fail = True
            all_pass = False
        total_warning_lines += int(report.get("summary", {}).get("total_warning_lines", 0))
        for command in report.get("commands", []):
            merged = "\n".join(
                part for part in (command.get("stdout_tail", ""), command.get("stderr_tail", "")) if part
            )
            if merged:
                combined_outputs.append(merged.lower())
            command_text = (command.get("command") or "").lower()
            if "test" in command_text:
                if int(command.get("exit_code", 1)) == 0:
                    any_test_pass = True
                else:
                    any_test_fail = True

    return {
        "combined_output": "\n".join(combined_outputs),
        "any_fail": any_fail,
        "any_test_fail": any_test_fail,
        "any_test_pass": any_test_pass,
        "all_pass": all_pass,
        "total_warning_lines": total_warning_lines,
        "report_paths": [report["_path"] for report in reports],
    }


def classify_claim(claim: dict, verifier_context: dict, profile: str) -> tuple[str, str, str]:
    claim_text = claim["claim"]
    lowered = claim_text.lower()
    evidence = "No matching verifier evidence."

    if claim["claim_type"] == "fresh_checkout":
        if verifier_context["all_pass"]:
            return "VERIFIED", f"Fresh-checkout PASS in {', '.join(verifier_context['report_paths'])}", "Keep claim."
        if verifier_context["any_fail"]:
            return "CONTRADICTED", f"Fresh-checkout FAIL in {', '.join(verifier_context['report_paths'])}", "Fix docs or workflow."
        return "UNVERIFIED", evidence, "Add fresh-checkout evidence or remove claim."

    if claim["claim_type"] == "tests":
        if verifier_context["any_test_fail"]:
            return "CONTRADICTED", "A test command failed in fresh-checkout verification.", "Fix tests or remove claim."
        if lowered in verifier_context["combined_output"]:
            return "VERIFIED", "Exact test-pass claim appears in verifier command output.", "Keep claim."
        if "all tests passing" in lowered and verifier_context["all_pass"] and verifier_context["any_test_pass"]:
            return "VERIFIED", "Fresh-checkout verifier shows test commands passed.", "Keep claim."
        return "UNVERIFIED", evidence, "Add exact test evidence or remove claim."

    if claim["claim_type"] == "warnings":
        if verifier_context["total_warning_lines"] == 0 and verifier_context["all_pass"]:
            return "VERIFIED", "Verifier reports zero warning lines.", "Keep claim."
        if verifier_context["total_warning_lines"] > 0:
            return "CONTRADICTED", f"Verifier counted {verifier_context['total_warning_lines']} warning lines.", "Fix warnings or remove claim."
        return "UNVERIFIED", evidence, "Add warning evidence or remove claim."

    if claim["claim_type"] == "metric":
        if lowered in verifier_context["combined_output"]:
            return "VERIFIED", "Exact metric text appears in verifier output.", "Keep claim."
        return "UNVERIFIED", evidence, "Add exact metric evidence or remove claim."

    if claim["claim_type"] == "coverage":
        if lowered in verifier_context["combined_output"]:
            return "VERIFIED", "Exact coverage claim appears in verifier output.", "Keep claim."
        return "UNVERIFIED", evidence, "Add exact coverage evidence or remove claim."

    if claim["claim_type"] == "readiness":
        if profile == "software" and verifier_context["any_fail"]:
            return "CONTRADICTED", "Fresh-checkout verification failed, so readiness language is overstated.", "Remove readiness claim or fix underlying failures."
        if profile == "software":
            return "UNVERIFIED", "Fresh-checkout alone does not prove broad readiness language.", "Replace with specific evidence-backed language."
        return "UNVERIFIED", "Broad readiness language is not deterministically proven for this profile.", "Prefer specific evidence-backed language over generic readiness claims."

    if claim["claim_type"] in {"stability", "security"}:
        if lowered in verifier_context["combined_output"]:
            return "VERIFIED", "Exact claim appears in verifier output.", "Keep claim."
        return "UNVERIFIED", evidence, "Add explicit evidence or remove claim."

    if claim["claim_type"] in {"schema", "quality", "sources", "methodology", "confidence", "artifact"}:
        return "UNVERIFIED", "This profile requires explicit evidence artifacts beyond fresh-checkout output.", "Add a concrete evidence artifact or soften the claim."

    return "UNVERIFIED", evidence, "Add evidence or remove claim."


def build_ledger(claims: list[dict], verifier_reports: list[dict], profile: str) -> dict:
    verifier_context = collect_verifier_context(verifier_reports)
    rows = []
    counts = {"VERIFIED": 0, "STALE": 0, "CONTRADICTED": 0, "UNVERIFIED": 0}

    for claim in claims:
        status, evidence, action = classify_claim(claim, verifier_context, profile)
        counts[status] += 1
        rows.append(
            {
                "claim": claim["claim"],
                "claim_type": claim["claim_type"],
                "source_file": claim["source_file"],
                "line": claim["line"],
                "evidence": evidence,
                "status": status,
                "action": action,
            }
        )

    return {
        "generated_at": datetime.now().strftime(TIMESTAMP_FMT),
        "verification_profile": profile,
        "docs_scanned": sorted({claim["source_file"] for claim in claims}),
        "fresh_checkout_reports": verifier_context["report_paths"],
        "summary": {
            "total_claims": len(rows),
            **counts,
        },
        "claims": rows,
    }


def render_markdown(report: dict) -> str:
    def escape_cell(value: str) -> str:
        return value.replace("|", "\\|")

    lines = [
        "# Claim Ledger",
        "",
        f"**Generated:** {report['generated_at']}",
        f"**Verification profile:** {report['verification_profile']}",
        f"**Docs scanned:** {', '.join(report['docs_scanned']) if report['docs_scanned'] else '—'}",
        f"**Fresh-checkout reports:** {', '.join(report['fresh_checkout_reports']) if report['fresh_checkout_reports'] else '—'}",
        "",
        "## Summary",
        "",
        f"- Total claims: {report['summary']['total_claims']}",
        f"- VERIFIED: {report['summary']['VERIFIED']}",
        f"- STALE: {report['summary']['STALE']}",
        f"- CONTRADICTED: {report['summary']['CONTRADICTED']}",
        f"- UNVERIFIED: {report['summary']['UNVERIFIED']}",
        "",
        "## Ledger",
        "",
        "| Claim | Source File | Evidence | Status | Action |",
        "|-------|-------------|----------|--------|--------|",
    ]
    for row in report["claims"]:
        source = escape_cell(f"{row['source_file']}:{row['line']}")
        claim_text = escape_cell(row["claim"])
        evidence = escape_cell(row["evidence"])
        action = escape_cell(row["action"])
        lines.append(
            f"| {claim_text} | {source} | {evidence} | {row['status']} | {action} |"
        )
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    args = parse_args()
    if not args.doc:
        print("Provide at least one --doc.", file=sys.stderr)
        return 2

    docs = [Path(path).expanduser().resolve() for path in args.doc]
    missing = [str(path) for path in docs if not path.exists()]
    if missing:
        print(f"Missing doc path(s): {', '.join(missing)}", file=sys.stderr)
        return 2

    verifier_reports = load_verifier_reports(args.fresh_checkout_json)
    claim_patterns = claim_patterns_for_profile(args.verification_profile)
    claims = []
    for doc in docs:
        claims.extend(read_doc_claims(doc, claim_patterns))

    report = build_ledger(claims, verifier_reports, args.verification_profile)

    json_out = Path(args.json_out).expanduser().resolve()
    markdown_out = Path(args.markdown_out).expanduser().resolve()
    json_out.parent.mkdir(parents=True, exist_ok=True)
    markdown_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    markdown_out.write_text(render_markdown(report), encoding="utf-8")

    print(f"claims={report['summary']['total_claims']}")
    print(f"contradicted={report['summary']['CONTRADICTED']}")
    print(f"unverified={report['summary']['UNVERIFIED']}")
    print(f"json_report={json_out}")
    print(f"markdown_report={markdown_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
