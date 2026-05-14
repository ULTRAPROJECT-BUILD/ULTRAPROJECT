#!/usr/bin/env python3
"""Audit aesthetic-default-wrong override tags with an independent LLM pass."""

from __future__ import annotations

import argparse
import math
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from visual_spec_telemetry_common import (
    extract_json_object,
    load_outcomes_with_metadata,
    platform_value,
    repo_relative,
    utc_now_iso,
    write_json,
)

REASON = "aesthetic-default-wrong"
CLASSIFICATIONS = {"aesthetic-default-wrong", "project-specific-brand", "operator-taste"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--outcomes-dir", required=True, help="Directory containing visual-spec-outcome-*.json files.")
    parser.add_argument("--preset", required=True, help="Preset name to audit.")
    parser.add_argument("--sample-pct", type=int, default=20, help="Percentage of override items to sample. Default: 20.")
    parser.add_argument(
        "--min-items",
        type=int,
        default=int(platform_value("visual_spec_telemetry_audit_min_items", 3)),
        help="Minimum sample size floor. Default comes from platform.md.",
    )
    parser.add_argument("--llm-mode", choices=["claude", "codex", "stub"], default="stub", help="Auditor backend.")
    parser.add_argument("--json-out", help="Optional path to write JSON output.")
    return parser.parse_args()


def collect_override_items(outcomes: list[dict[str, Any]], preset: str) -> list[dict[str, Any]]:
    """Collect override items for a preset."""
    items: list[dict[str, Any]] = []
    for outcome in outcomes:
        if outcome.get("visual_quality_target_preset") != preset:
            continue
        overrides = outcome.get("preset_default_overrides")
        if not isinstance(overrides, list):
            continue
        for override in overrides:
            if not isinstance(override, dict):
                continue
            if override.get("override_reason") != REASON:
                continue
            items.append(
                {
                    "project": str(outcome.get("project") or ""),
                    "client_id": str(outcome.get("client_id") or ""),
                    "client_organization_id": str(outcome.get("client_organization_id") or ""),
                    "client_domain": str(outcome.get("client_domain") or ""),
                    "preset": preset,
                    "axis_or_token": str(override.get("axis_or_token") or ""),
                    "preset_default": override.get("preset_default"),
                    "project_value": override.get("project_value"),
                    "operator_approved": bool(override.get("operator_approved")),
                    "reviewer_sessions": [
                        str(item.get("reviewer_session_id") or "")
                        for item in outcome.get("reviewer_grades", [])
                        if isinstance(item, dict) and str(item.get("reviewer_session_id") or "").strip()
                    ],
                    "visual_gate_first_attempt": outcome.get("visual_gate_first_attempt"),
                    "visual_gate_final": outcome.get("visual_gate_final"),
                    "visual_gate_revision_rounds": outcome.get("visual_gate_revision_rounds"),
                    "operator_acceptance": outcome.get("operator_acceptance"),
                    "revision_count_during_build": outcome.get("revision_count_during_build"),
                    "delivery_review_grade": outcome.get("delivery_review_grade"),
                    "source_path": str(outcome.get("_source_path") or ""),
                }
            )
    items.sort(key=lambda item: (item["project"], item["axis_or_token"], str(item["project_value"])))
    return items


def choose_sample(items: list[dict[str, Any]], sample_pct: int, min_items: int) -> list[dict[str, Any]]:
    """Choose a deterministic sample."""
    if not items:
        return []
    target = max(int(math.ceil(len(items) * max(sample_pct, 0) / 100.0)), max(min_items, 0))
    target = min(len(items), target)
    if target >= len(items):
        return items
    stride = max(1, len(items) // target)
    sampled = [items[index] for index in range(0, len(items), stride)]
    return sampled[:target]


def auditor_prompt(item: dict[str, Any]) -> str:
    """Build the re-classification prompt."""
    payload = {
        "project": item["project"],
        "preset": item["preset"],
        "axis_or_token": item["axis_or_token"],
        "preset_default": item["preset_default"],
        "project_value": item["project_value"],
        "operator_approved": item["operator_approved"],
        "client_domain": item["client_domain"],
        "client_organization_id": item["client_organization_id"],
        "visual_gate_first_attempt": item["visual_gate_first_attempt"],
        "visual_gate_final": item["visual_gate_final"],
        "visual_gate_revision_rounds": item["visual_gate_revision_rounds"],
        "operator_acceptance": item["operator_acceptance"],
        "revision_count_during_build": item["revision_count_during_build"],
        "delivery_review_grade": item["delivery_review_grade"],
    }
    return (
        "You are independently auditing a Visual Specification telemetry tag.\n"
        "The existing override_reason is aesthetic-default-wrong.\n"
        "Re-classify the override using only these labels:\n"
        "- aesthetic-default-wrong\n"
        "- project-specific-brand\n"
        "- operator-taste\n\n"
        "Return JSON only with exactly these keys:\n"
        "{\"classification\": \"...\", \"confidence\": 0.0, \"rationale\": \"...\"}\n\n"
        "Confidence must be a number from 0.0 to 1.0.\n"
        "If the evidence does not clearly support brand- or taste-specific reasoning, keep aesthetic-default-wrong.\n\n"
        f"Outcome summary:\n{payload}\n"
    )


def run_claude(prompt: str) -> dict[str, Any]:
    """Run Claude in JSON output mode."""
    completed = subprocess.run(
        ["claude", "-p", "--output-format", "json"],
        input=prompt,
        text=True,
        capture_output=True,
        check=False,
        timeout=300,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"claude exited {completed.returncode}: {completed.stderr.strip()}")
    return extract_json_object(completed.stdout)


def run_codex(prompt: str) -> dict[str, Any]:
    """Run Codex in JSON mode."""
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix="-override-audit.txt", delete=False) as handle:
        handle.write(prompt)
        temp_path = Path(handle.name)
    try:
        completed = subprocess.run(
            ["codex", "exec", "--skip-git-repo-check"],
            input=temp_path.read_text(encoding="utf-8"),
            text=True,
            capture_output=True,
            check=False,
            timeout=300,
            cwd=SCRIPT_DIR.parent,
        )
    finally:
        try:
            temp_path.unlink()
        except OSError:
            pass
    if completed.returncode != 0:
        raise RuntimeError(f"codex exited {completed.returncode}: {completed.stderr.strip()}")
    return extract_json_object(completed.stdout)


def normalize_result(item: dict[str, Any], raw: dict[str, Any]) -> dict[str, Any]:
    """Normalize auditor output."""
    classification = str(raw.get("classification") or raw.get("auditor_classification") or "").strip()
    if classification not in CLASSIFICATIONS:
        classification = REASON
    try:
        confidence = float(raw.get("confidence", 0.0))
    except (TypeError, ValueError):
        confidence = 0.0
    confidence = max(0.0, min(confidence, 1.0))
    return {
        "project": item["project"],
        "axis_or_token": item["axis_or_token"],
        "tag_in_outcome": REASON,
        "auditor_classification": classification,
        "confidence": round(confidence, 3),
        "source_path": repo_relative(Path(item["source_path"])) if item.get("source_path") else "",
    }


def audit_item(item: dict[str, Any], llm_mode: str) -> dict[str, Any]:
    """Audit one sampled override."""
    if llm_mode == "stub":
        return {
            "project": item["project"],
            "axis_or_token": item["axis_or_token"],
            "tag_in_outcome": REASON,
            "auditor_classification": REASON,
            "confidence": 0.85,
            "source_path": repo_relative(Path(item["source_path"])) if item.get("source_path") else "",
        }
    prompt = auditor_prompt(item)
    raw = run_claude(prompt) if llm_mode == "claude" else run_codex(prompt)
    return normalize_result(item, raw)


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    outcomes, invalid_outcomes = load_outcomes_with_metadata(Path(args.outcomes_dir).expanduser().resolve())
    items = collect_override_items(outcomes, args.preset)
    sampled = choose_sample(items, args.sample_pct, args.min_items)
    if not sampled:
        return {
            "preset": args.preset,
            "audited_at": utc_now_iso(),
            "sample_size": 0,
            "audit_disagreement_count": 0,
            "audit_disagreement_pct": 0.0,
            "average_confidence": 0.0,
            "items": [],
            "verdict": "no_data_yet",
            "fail_reason": "No aesthetic-default-wrong overrides found for this preset.",
            "invalid_outcomes": invalid_outcomes,
        }

    results = [audit_item(item, args.llm_mode) for item in sampled]
    disagreements = [item for item in results if item["auditor_classification"] != REASON]
    disagreement_pct = round((len(disagreements) / len(results)) * 100.0, 2)
    average_confidence = round(sum(item["confidence"] for item in results) / len(results), 3)

    fail_reasons: list[str] = []
    if disagreement_pct >= 30.0:
        fail_reasons.append(f"disagreement rate {disagreement_pct:.2f}% is at or above 30%")
    if average_confidence < 0.8:
        fail_reasons.append(f"average confidence {average_confidence:.3f} is below 0.8")

    return {
        "preset": args.preset,
        "audited_at": utc_now_iso(),
        "sample_size": len(results),
        "audit_disagreement_count": len(disagreements),
        "audit_disagreement_pct": disagreement_pct,
        "average_confidence": average_confidence,
        "items": results,
        "verdict": "pass" if not fail_reasons else "fail",
        "fail_reason": "; ".join(fail_reasons),
        "invalid_outcomes": invalid_outcomes,
    }


def main() -> int:
    args = parse_args()
    try:
        payload = build_payload(args)
        write_json(payload, args.json_out)
        return 0 if payload["verdict"] in {"pass", "no_data_yet"} else 1
    except Exception as exc:
        write_json(
            {
                "preset": args.preset,
                "audited_at": utc_now_iso(),
                "sample_size": 0,
                "audit_disagreement_count": 0,
                "audit_disagreement_pct": 0.0,
                "average_confidence": 0.0,
                "items": [],
                "verdict": "fail",
                "fail_reason": str(exc),
            },
            args.json_out,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
