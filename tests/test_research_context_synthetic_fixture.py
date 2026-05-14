"""
Test type: deterministic synthetic fixture for research-context output structure.

This test uses fake search-result inputs, writes a synthetic snapshot, and runs
the offline self-check. It makes no network calls and does not invoke Codex.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BUDGET_SCRIPT = REPO_ROOT / "scripts" / "research_context_budget.py"
CHECK_SCRIPT = REPO_ROOT / "scripts" / "check_research_context.py"
CATEGORIES = [
    "Recent launches in genre",
    "Current tool/library versions",
    "Deprecated patterns",
    "New capabilities since cutoff",
    "Current best practices in domain",
]
FAKE_RESULTS = [
    {
        "id": "RC-001",
        "category": "Recent launches in genre",
        "claim": "AI developer-tool launch videos in the fixture emphasize short proof loops and visible product output.",
        "url": "https://example.com/ai-dev-tool-launch-video",
        "date": "2026-04-10",
        "confidence": "high",
        "implication": "Open the plan with concrete product proof, not abstract positioning.",
    },
    {
        "id": "RC-002",
        "category": "Current tool/library versions",
        "claim": "The fixture treats Remotion as the current video-rendering implementation path.",
        "url": "https://example.com/remotion-release-2026",
        "date": "2026-03-18",
        "confidence": "high",
        "implication": "Plan Remotion-based composition tickets and verification.",
    },
    {
        "id": "RC-003",
        "category": "Deprecated patterns",
        "claim": "The fixture marks vague AI montage claims as stale for 2026 launch references.",
        "url": "https://example.com/deprecated-ai-video-patterns",
        "date": "2026-02-20",
        "confidence": "medium",
        "implication": "Add anti-patterns against generic montage and unsupported capability claims.",
    },
    {
        "id": "RC-004",
        "category": "New capabilities since cutoff",
        "claim": "The fixture includes post-cutoff tool capability claims only as cited planning inputs.",
        "url": "https://example.com/codex-cli-2026-capability",
        "date": "2026-04-22",
        "confidence": "medium",
        "implication": "Route capability claims through the Executability Audit before production use.",
    },
    {
        "id": "RC-005",
        "category": "Current best practices in domain",
        "claim": "The fixture expects 2026 developer-tool launch content to show developer workflow evidence.",
        "url": "https://example.com/developer-tool-launch-best-practices",
        "date": "2026-03-30",
        "confidence": "high",
        "implication": "Require visible workflow proof in creative-brief references.",
    },
]


def run_json(*args: str) -> tuple[subprocess.CompletedProcess[str], dict]:
    result = subprocess.run(args, text=True, capture_output=True, check=False)
    payload = json.loads(result.stdout)
    return result, payload


def reserve_and_record(ledger: Path, category: str, kind: str, value: str, result_count: int) -> None:
    command = [
        sys.executable,
        str(BUDGET_SCRIPT),
        "reserve",
        "--ledger",
        str(ledger),
        "--category",
        category,
        "--kind",
        kind,
    ]
    if kind == "WebSearch":
        command.extend(["--query", value])
        record_url = ""
    else:
        command.extend(["--url", value])
        record_url = value
    result, payload = run_json(*command)
    assert result.returncode == 0
    record, record_payload = run_json(
        sys.executable,
        str(BUDGET_SCRIPT),
        "record",
        "--ledger",
        str(ledger),
        "--reservation-id",
        payload["reservation_id"],
        "--status",
        "ok",
        "--result-count",
        str(result_count),
        "--url",
        record_url,
    )
    assert record.returncode == 0
    assert record_payload["ok"] is True


def write_synthetic_snapshot(path: Path, ledger: Path, check_json: Path) -> None:
    rows = "\n".join(
        "| {id} | {category} | {claim} | {url} | {date} | cited | {confidence} | {implication} |".format(
            **claim
        )
        for claim in FAKE_RESULTS
    )
    path.write_text(
        f"""---
type: snapshot
subtype: research-context
title: "Research Context - Synthetic Fixture"
project: "research-context-synthetic-current-ai-video"
client: "_platform"
captured: 2026-05-01T13:00
agent: research-context
trigger_reason: "synthetic-fixture"
model_cutoff: "2026-01"
research_window_months: 12
domain: "developer tooling"
deliverable_type: "video"
genre: "AI developer-tool launch video"
total_websearch: 5
total_webfetch: 3
per_category_websearch_count:
  "Recent launches in genre": 1
  "Current tool/library versions": 1
  "Deprecated patterns": 1
  "New capabilities since cutoff": 1
  "Current best practices in domain": 1
per_category_webfetch_count:
  "Recent launches in genre": 1
  "Current tool/library versions": 1
  "Deprecated patterns": 1
  "New capabilities since cutoff": 0
  "Current best practices in domain": 0
cited_claim_count: 5
inferred_claim_count: 0
inferred_claim_ratio: 0.0
low_confidence: false
budget_ledger: "{ledger}"
self_check_json: "{check_json}"
tags: [research-context, external-research, currentness]
---

# Research Context - Synthetic Fixture

## Research Scope
Fake search-result inputs covering current launch video planning.

## Budget Ledger
Five WebSearch reservations and three WebFetch reservations are recorded in the fixture ledger.

## Executive Synthesis
Use current, cited launch and tooling claims as planning inputs, then verify run-local capability separately.

## Recent launches in genre
- **RC-001:** {FAKE_RESULTS[0]["claim"]}. ([Fixture launch page, {FAKE_RESULTS[0]["date"]}]({FAKE_RESULTS[0]["url"]}))
  **Implication:** {FAKE_RESULTS[0]["implication"]}

## Current tool/library versions
- **RC-002:** {FAKE_RESULTS[1]["claim"]}. ([Fixture Remotion release, {FAKE_RESULTS[1]["date"]}]({FAKE_RESULTS[1]["url"]}))
  **Implication:** {FAKE_RESULTS[1]["implication"]}

## Deprecated patterns
- **RC-003:** {FAKE_RESULTS[2]["claim"]}. ([Fixture pattern note, {FAKE_RESULTS[2]["date"]}]({FAKE_RESULTS[2]["url"]}))
  **Implication:** {FAKE_RESULTS[2]["implication"]}

## New capabilities since cutoff
- **RC-004:** {FAKE_RESULTS[3]["claim"]}. ([Fixture capability note, {FAKE_RESULTS[3]["date"]}]({FAKE_RESULTS[3]["url"]}))
  **Implication:** {FAKE_RESULTS[3]["implication"]}

## Current best practices in domain
- **RC-005:** {FAKE_RESULTS[4]["claim"]}. ([Fixture best-practices note, {FAKE_RESULTS[4]["date"]}]({FAKE_RESULTS[4]["url"]}))
  **Implication:** {FAKE_RESULTS[4]["implication"]}

## Claim Ledger

| Claim ID | Category | Claim | Citation URL | Citation Date | Status | Confidence | Implication |
|----------|----------|-------|--------------|---------------|--------|------------|-------------|
{rows}

## Low-Confidence Handling
low_confidence is false because all fixture claims are cited and current.

## Downstream Use
Project-plan may use these cited claims as currentness inputs; creative-brief must still audit availability in this run.

## Self-Check
Run scripts/check_research_context.py against this snapshot and ledger.
""",
        encoding="utf-8",
    )


def test_synthetic_fixture_matches_expected_output_structure(tmp_path):
    ledger = tmp_path / "2026-05-01-research-context-budget-research-context-synthetic-current-ai-video.json"
    snapshot = tmp_path / "2026-05-01-research-context-research-context-synthetic-current-ai-video.md"
    check_json = tmp_path / "2026-05-01-research-context-check-research-context-synthetic-current-ai-video.json"
    check_md = tmp_path / "2026-05-01-research-context-check-research-context-synthetic-current-ai-video.md"

    init, init_payload = run_json(
        sys.executable,
        str(BUDGET_SCRIPT),
        "init",
        "--ledger",
        str(ledger),
        "--project",
        "research-context-synthetic-current-ai-video",
        "--categories",
        *CATEGORIES,
    )
    assert init.returncode == 0
    assert init_payload["ok"] is True
    for category in CATEGORIES:
        reserve_and_record(ledger, category, "WebSearch", f"{category} 2026", 4)
    for claim in FAKE_RESULTS[:3]:
        reserve_and_record(ledger, claim["category"], "WebFetch", claim["url"], 1)

    write_synthetic_snapshot(snapshot, ledger, check_json)

    result = subprocess.run(
        [
            sys.executable,
            str(CHECK_SCRIPT),
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
            str(check_md),
            "--json-out",
            str(check_json),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    check_payload = json.loads(check_json.read_text(encoding="utf-8"))

    assert result.returncode == 0
    assert check_payload["verdict"] == "pass"
    assert check_payload["low_confidence"] is False
    text = snapshot.read_text(encoding="utf-8")
    for heading in [
        "Research Scope",
        "Budget Ledger",
        "Executive Synthesis",
        *CATEGORIES,
        "Claim Ledger",
        "Low-Confidence Handling",
        "Downstream Use",
        "Self-Check",
    ]:
        assert f"## {heading}" in text
    assert text.count("RC-") >= 10
    assert "paid X API" not in text
    assert "browser login" not in text
