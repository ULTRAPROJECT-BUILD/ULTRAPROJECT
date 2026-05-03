#!/usr/bin/env python3
"""
Validate research-context snapshots for citation freshness and ledger presence.

The checker is an offline mechanical guardrail. It verifies claim syntax,
citation dates, inferred-claim ratio, and reservation-ledger usage without
performing any live network calls.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any


CLAIM_ID_RE = re.compile(r"\bRC-\d{3,}\b")
URL_RE = re.compile(r"https?://[^\s)\]|]+")
DATE_RE = re.compile(r"\b(20\d{2}-\d{2}-\d{2})\b")


@dataclass
class Claim:
    claim_id: str
    category: str
    claim: str
    citation_url: str
    citation_date: str
    status: str
    confidence: str
    implication: str
    source_line: int
    raw: str

    @property
    def inferred(self) -> bool:
        return "inferred" in self.status.lower() or "[inferred:" in self.raw.lower()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", required=True, help="Research-context markdown snapshot to validate.")
    parser.add_argument("--ledger", required=True, help="Research-context usage JSON ledger.")
    parser.add_argument("--today", required=True, help="Machine-local date as YYYY-MM-DD.")
    parser.add_argument("--max-source-age-days", required=True, type=int, help="Maximum cited source age.")
    parser.add_argument("--max-inferred-ratio", required=True, type=float, help="Low-confidence threshold.")
    parser.add_argument("--markdown-out", required=True, help="Path for markdown check report.")
    parser.add_argument("--json-out", required=True, help="Path for JSON check report.")
    return parser.parse_args()


def parse_today(value: str) -> date:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError(f"--today must be YYYY-MM-DD, got {value!r}") from exc


def split_table_row(line: str) -> list[str]:
    text = line.strip()
    if text.startswith("|"):
        text = text[1:]
    if text.endswith("|"):
        text = text[:-1]
    return [cell.strip() for cell in text.split("|")]


def is_separator_row(cells: list[str]) -> bool:
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", cell.strip()) for cell in cells)


def parse_table_claims(lines: list[str]) -> list[Claim]:
    claims: list[Claim] = []
    headers: list[str] | None = None
    in_claim_ledger = False
    for index, line in enumerate(lines, start=1):
        if re.match(r"^##\s+Claim Ledger\s*$", line.strip(), re.IGNORECASE):
            in_claim_ledger = True
            headers = None
            continue
        if in_claim_ledger and re.match(r"^##\s+", line.strip()):
            break
        if not in_claim_ledger or not line.lstrip().startswith("|"):
            continue
        cells = split_table_row(line)
        if is_separator_row(cells):
            continue
        normalized = [cell.lower() for cell in cells]
        if "claim id" in normalized and "claim" in normalized:
            headers = normalized
            continue
        if headers is None or len(cells) < len(headers):
            continue
        row = dict(zip(headers, cells))
        claim_id = row.get("claim id", "")
        claim_text = row.get("claim", "")
        raw = line.rstrip("\n")
        claims.append(
            Claim(
                claim_id=claim_id,
                category=row.get("category", ""),
                claim=claim_text,
                citation_url=row.get("citation url", ""),
                citation_date=row.get("citation date", ""),
                status=row.get("status", ""),
                confidence=row.get("confidence", ""),
                implication=row.get("implication", ""),
                source_line=index,
                raw=raw,
            )
        )
    return claims


def parse_bullet_claims(lines: list[str]) -> list[Claim]:
    claims: list[Claim] = []
    for index, line in enumerate(lines, start=1):
        if not line.lstrip().startswith("- **RC-"):
            continue
        raw = line.rstrip("\n")
        claim_id_match = CLAIM_ID_RE.search(raw)
        url_match = URL_RE.search(raw)
        date_match = DATE_RE.search(raw)
        inferred = "[INFERRED:" in raw
        claims.append(
            Claim(
                claim_id=claim_id_match.group(0) if claim_id_match else "",
                category="",
                claim=raw,
                citation_url=url_match.group(0) if url_match else "",
                citation_date=date_match.group(1) if date_match else "",
                status="inferred" if inferred else "cited",
                confidence="",
                implication="",
                source_line=index,
                raw=raw,
            )
        )
    return claims


def parse_claims(snapshot_text: str) -> list[Claim]:
    lines = snapshot_text.splitlines()
    table_claims = parse_table_claims(lines)
    if table_claims:
        return table_claims
    return parse_bullet_claims(lines)


def parse_claim_date(value: str) -> date | None:
    match = DATE_RE.search(value or "")
    if not match:
        return None
    try:
        return datetime.strptime(match.group(1), "%Y-%m-%d").date()
    except ValueError:
        return None


def validate_claims(
    claims: list[Claim],
    *,
    today: date,
    max_source_age_days: int,
    max_inferred_ratio: float,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    cited = 0
    inferred = 0
    malformed = 0
    for claim in claims:
        claim_failures: list[str] = []
        if not CLAIM_ID_RE.fullmatch(claim.claim_id.strip()):
            claim_failures.append("malformed_claim_id")
        if claim.inferred:
            inferred += 1
        else:
            cited += 1
            if not URL_RE.search(claim.citation_url):
                claim_failures.append("missing_citation_url")
            citation_date = parse_claim_date(claim.citation_date)
            if citation_date is None:
                claim_failures.append("missing_or_malformed_citation_date")
            else:
                age_days = (today - citation_date).days
                if age_days < 0:
                    claim_failures.append("future_citation_date")
                elif age_days > max_source_age_days:
                    claim_failures.append("stale_citation_date")
        if claim_failures:
            malformed += 1
            failures.append(
                {
                    "claim_id": claim.claim_id,
                    "line": claim.source_line,
                    "failures": claim_failures,
                    "raw": claim.raw,
                }
            )
    total = len(claims)
    inferred_ratio = (inferred / total) if total else 0.0
    counts = {
        "total": total,
        "cited": cited,
        "inferred": inferred,
        "malformed": malformed,
        "inferred_ratio": round(inferred_ratio, 4),
        "low_confidence": inferred_ratio > max_inferred_ratio,
    }
    return failures, counts


def load_ledger(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"ledger not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"ledger is not valid JSON: {exc}") from exc


def ledger_count(ledger: dict[str, Any], kind: str, category: str | None = None) -> int:
    count = 0
    for item in ledger.get("reservations", []):
        if item.get("kind") != kind:
            continue
        if category is not None and item.get("category") != category:
            continue
        count += 1
    return count


def validate_ledger(ledger: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    categories = ledger.get("categories", [])
    totals = {
        "WebSearch": ledger_count(ledger, "WebSearch"),
        "WebFetch": ledger_count(ledger, "WebFetch"),
    }
    category_usage: dict[str, dict[str, int]] = {}
    for category in categories:
        usage = {
            "WebSearch": ledger_count(ledger, "WebSearch", category),
            "WebFetch": ledger_count(ledger, "WebFetch", category),
        }
        category_usage[category] = usage
    summary = {
        "categories": categories,
        "annotations": ledger.get("annotations", {}),
        "totals": totals,
        "category_usage": category_usage,
        "reservation_count": len(ledger.get("reservations", [])),
    }
    return failures, summary


def build_check(name: str, ok: bool, details: str) -> dict[str, Any]:
    return {"name": name, "ok": ok, "details": details}


def write_report(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Research Context Check",
        "",
        f"- **Verdict:** {report['verdict']}",
        f"- **Low confidence:** {str(report['low_confidence']).lower()}",
        f"- **Claims:** {report['claim_counts']['total']} total, {report['claim_counts']['cited']} cited, {report['claim_counts']['inferred']} inferred",
        "",
        "## Checks",
        "",
    ]
    for check in report["checks"]:
        status = "PASS" if check["ok"] else "FAIL"
        lines.append(f"- **{status}:** {check['name']} - {check['details']}")
    if report["failures"]:
        lines.extend(["", "## Failures", ""])
        for failure in report["failures"]:
            lines.append(f"- `{failure.get('type', failure.get('claim_id', 'failure'))}`: {failure}")
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    failures: list[dict[str, Any]] = []
    checks: list[dict[str, Any]] = []
    try:
        today = parse_today(args.today)
        snapshot_path = Path(args.snapshot).expanduser().resolve()
        ledger_path = Path(args.ledger).expanduser().resolve()
        snapshot_text = snapshot_path.read_text(encoding="utf-8")
        claims = parse_claims(snapshot_text)
        claim_failures, claim_counts = validate_claims(
            claims,
            today=today,
            max_source_age_days=args.max_source_age_days,
            max_inferred_ratio=args.max_inferred_ratio,
        )
        failures.extend(claim_failures)
        checks.append(
            build_check(
                "claim_citation_contract",
                not claim_failures,
                f"{claim_counts['cited']} cited, {claim_counts['inferred']} inferred, {claim_counts['malformed']} malformed",
            )
        )
        ledger = load_ledger(ledger_path)
        ledger_failures, budget_summary = validate_ledger(ledger)
        failures.extend(ledger_failures)
        checks.append(
            build_check(
                "budget_ledger",
                not ledger_failures,
                f"{budget_summary['totals']['WebSearch']} WebSearch, {budget_summary['totals']['WebFetch']} WebFetch",
            )
        )
        verdict = "pass" if not failures else "fail"
        report = {
            "verdict": verdict,
            "snapshot": str(snapshot_path),
            "ledger": str(ledger_path),
            "today": args.today,
            "max_source_age_days": args.max_source_age_days,
            "max_inferred_ratio": args.max_inferred_ratio,
            "low_confidence": claim_counts["low_confidence"],
            "claim_counts": claim_counts,
            "budget_summary": budget_summary,
            "checks": checks,
            "failures": failures,
        }
    except Exception as exc:  # noqa: BLE001 - this is a CLI guardrail.
        report = {
            "verdict": "fail",
            "snapshot": str(Path(args.snapshot).expanduser()),
            "ledger": str(Path(args.ledger).expanduser()),
            "today": args.today,
            "low_confidence": False,
            "claim_counts": {
                "total": 0,
                "cited": 0,
                "inferred": 0,
                "malformed": 0,
                "inferred_ratio": 0.0,
                "low_confidence": False,
            },
            "budget_summary": {},
            "checks": [build_check("checker_runtime", False, str(exc))],
            "failures": [{"type": "checker_runtime", "details": str(exc)}],
        }
    json_out = Path(args.json_out).expanduser().resolve()
    markdown_out = Path(args.markdown_out).expanduser().resolve()
    write_report(json_out, json.dumps(report, indent=2, sort_keys=True) + "\n")
    write_report(markdown_out, render_markdown(report))
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["verdict"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
