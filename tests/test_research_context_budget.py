"""
Test type: behavior fixture tests for the Python research-context usage ledger helper.

These tests use temporary JSON ledgers and no live network calls.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "research_context_budget.py"
CATEGORIES = [
    "Recent launches in genre",
    "Current tool/library versions",
    "Deprecated patterns",
    "New capabilities since cutoff",
    "Current best practices in domain",
]


def run_budget(*args: str) -> tuple[subprocess.CompletedProcess[str], dict]:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        text=True,
        capture_output=True,
        check=False,
    )
    payload = json.loads(result.stdout)
    return result, payload


def init_ledger(path: Path) -> None:
    result, payload = run_budget(
        "init",
        "--ledger",
        str(path),
        "--project",
        "research-context-test",
        "--categories",
        *CATEGORIES,
    )
    assert result.returncode == 0
    assert payload["ok"] is True


def reserve(path: Path, category: str, kind: str, value: str) -> tuple[subprocess.CompletedProcess[str], dict]:
    if kind == "WebSearch":
        return run_budget(
            "reserve",
            "--ledger",
            str(path),
            "--category",
            category,
            "--kind",
            kind,
            "--query",
            value,
        )
    return run_budget(
        "reserve",
        "--ledger",
        str(path),
        "--category",
        category,
        "--kind",
        kind,
        "--url",
        value,
    )


def test_reserve_always_allows_and_records_every_call(tmp_path):
    ledger = tmp_path / "budget.json"
    init_ledger(ledger)

    reservation_ids = []
    for index in range(8):
        result, payload = reserve(ledger, CATEGORIES[0], "WebSearch", f"query {index}")
        assert result.returncode == 0
        assert payload["allowed"] is True
        reservation_ids.append(payload["reservation_id"])

    for index in range(5):
        result, payload = reserve(ledger, CATEGORIES[1], "WebFetch", f"https://example.com/{index}")
        assert result.returncode == 0
        assert payload["allowed"] is True
        reservation_ids.append(payload["reservation_id"])

    data = json.loads(ledger.read_text(encoding="utf-8"))
    assert len(data["reservations"]) == 13
    assert [item["reservation_id"] for item in data["reservations"]] == reservation_ids

    result, summary = run_budget("summary", "--ledger", str(ledger))
    assert result.returncode == 0
    assert summary["ok"] is True
    assert summary["totals"]["WebSearch"] == 8
    assert summary["totals"]["WebFetch"] == 5
    assert summary["reservation_count"] == 13


def test_record_and_summary_report_totals(tmp_path):
    ledger = tmp_path / "budget.json"
    init_ledger(ledger)
    result, payload = reserve(ledger, CATEGORIES[0], "WebSearch", "latest launch video 2026")
    assert result.returncode == 0
    reservation_id = payload["reservation_id"]

    result, record = run_budget(
        "record",
        "--ledger",
        str(ledger),
        "--reservation-id",
        reservation_id,
        "--status",
        "ok",
        "--result-count",
        "4",
        "--url",
        "",
    )
    assert result.returncode == 0
    assert record["ok"] is True

    result, summary = run_budget("summary", "--ledger", str(ledger))
    assert result.returncode == 0
    assert summary["ok"] is True
    assert summary["totals"]["WebSearch"] == 1
    assert summary["totals"]["WebFetch"] == 0
    assert summary["category_usage"][CATEGORIES[0]]["WebSearch"] == 1
