"""
Test type: behavior fixture tests for the research-context self-check helper.

These tests use synthetic markdown snapshots and JSON ledgers with no live
network calls.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "check_research_context.py"
CATEGORIES = [
    "Recent launches in genre",
    "Current tool/library versions",
    "Deprecated patterns",
    "New capabilities since cutoff",
    "Current best practices in domain",
]


def write_ledger(path: Path, reservations: list[dict]) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "project": "research-context-test",
                "categories": CATEGORIES,
                "annotations": {
                    "websearch_per_category": None,
                    "webfetch_per_category": None,
                },
                "reservations": reservations,
            }
        ),
        encoding="utf-8",
    )


def write_snapshot(path: Path, rows: str) -> None:
    path.write_text(
        f"""---
type: snapshot
subtype: research-context
project: research-context-test
low_confidence: false
---

## Claim Ledger

| Claim ID | Category | Claim | Citation URL | Citation Date | Status | Confidence | Implication |
|----------|----------|-------|--------------|---------------|--------|------------|-------------|
{rows}
""",
        encoding="utf-8",
    )


def run_check(snapshot: Path, ledger: Path, tmp_path: Path) -> tuple[subprocess.CompletedProcess[str], dict]:
    json_out = tmp_path / "check.json"
    markdown_out = tmp_path / "check.md"
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--snapshot",
            str(snapshot),
            "--ledger",
            str(ledger),
            "--today",
            "2026-05-01",
            "--max-source-age-days",
            "366",
            "--max-inferred-ratio",
            "0.30",
            "--markdown-out",
            str(markdown_out),
            "--json-out",
            str(json_out),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    return result, json.loads(json_out.read_text(encoding="utf-8"))


def test_checker_passes_fresh_cited_and_inferred_claims(tmp_path):
    snapshot = tmp_path / "research.md"
    ledger = tmp_path / "budget.json"
    write_snapshot(
        snapshot,
        "| RC-001 | Recent launches in genre | A current launch happened. | https://example.com/launch | 2026-04-10 | cited | high | Use it as a reference. |\n"
        "| RC-002 | Deprecated patterns | Use the older claim only as a hypothesis. |  |  | inferred [INFERRED: blocked fetch] | low | Track as assumption. |",
    )
    write_ledger(
        ledger,
        [
            {"reservation_id": "one", "category": CATEGORIES[0], "kind": "WebSearch"},
            {"reservation_id": "two", "category": CATEGORIES[2], "kind": "WebFetch"},
        ],
    )

    result, payload = run_check(snapshot, ledger, tmp_path)

    assert result.returncode == 0
    assert payload["verdict"] == "pass"
    assert payload["claim_counts"]["cited"] == 1
    assert payload["claim_counts"]["inferred"] == 1
    assert payload["low_confidence"] is True


def test_checker_fails_uncited_non_inferred_claim(tmp_path):
    snapshot = tmp_path / "research.md"
    ledger = tmp_path / "budget.json"
    write_snapshot(
        snapshot,
        "| RC-001 | Recent launches in genre | A current launch happened. |  |  | cited | high | Use it as a reference. |",
    )
    write_ledger(ledger, [])

    result, payload = run_check(snapshot, ledger, tmp_path)

    assert result.returncode == 1
    assert payload["verdict"] == "fail"
    assert payload["failures"][0]["failures"] == [
        "missing_citation_url",
        "missing_or_malformed_citation_date",
    ]


def test_checker_allows_any_ledger_usage_count(tmp_path):
    snapshot = tmp_path / "research.md"
    ledger = tmp_path / "budget.json"
    write_snapshot(
        snapshot,
        "| RC-001 | Recent launches in genre | A current launch happened. | https://example.com/launch | 2026-04-10 | cited | high | Use it as a reference. |",
    )
    write_ledger(
        ledger,
        [
            {"reservation_id": str(index), "category": CATEGORIES[0], "kind": "WebSearch"}
            for index in range(6)
        ],
    )

    result, payload = run_check(snapshot, ledger, tmp_path)

    assert result.returncode == 0
    assert payload["verdict"] == "pass"
    assert payload["budget_summary"]["totals"]["WebSearch"] == 6
    assert payload["budget_summary"]["category_usage"][CATEGORIES[0]]["WebSearch"] == 6
