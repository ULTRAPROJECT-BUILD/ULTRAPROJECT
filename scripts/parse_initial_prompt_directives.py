#!/usr/bin/env python3
"""Parse operator override directives from an initial orchestrator prompt."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

PHASE_ALIASES = {
    "brief": "brief",
    "vs lock": "vs_lock",
    "vs_lock": "vs_lock",
    "vs-lock": "vs_lock",
    "build": "build",
    "qc": "qc",
    "polish": "polish",
    "delivery": "delivery",
}
ALERT_ALIASES = {
    "waiver_yellow": "waiver_yellow",
    "waiver-yellow": "waiver_yellow",
    "waiver yellow": "waiver_yellow",
    "waiver_red": "waiver_red",
    "waiver-red": "waiver_red",
    "waiver red": "waiver_red",
    "unsupported_medium": "unsupported_medium",
    "unsupported-medium": "unsupported_medium",
    "unsupported medium": "unsupported_medium",
}
PHASE_PATTERN = r"(brief|vs(?:[_ -]?lock)|build|qc|polish|delivery)"
ALERT_PATTERN = r"(waiver(?:[_ -]?yellow)|waiver(?:[_ -]?red)|unsupported(?:[_ -]?medium))"


def local_now() -> str:
    """Return a local ISO-8601 timestamp with timezone."""
    return datetime.now().astimezone().isoformat(timespec="seconds")


def normalize_phase(value: str) -> str:
    """Normalize a phase token."""
    return PHASE_ALIASES[re.sub(r"\s+", " ", value.strip().lower())]


def normalize_alert(value: str) -> str:
    """Normalize an alert token."""
    return ALERT_ALIASES[re.sub(r"\s+", " ", value.strip().lower())]


def dedupe_ordered(items: list[Any]) -> list[Any]:
    """Deduplicate JSON-like items while preserving order."""
    seen: set[str] = set()
    result: list[Any] = []
    for item in items:
        key = json.dumps(item, sort_keys=True)
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def load_prompt_text(prompt_text: str | None, prompt_file: str | None) -> str:
    """Combine prompt text and prompt file contents."""
    parts: list[str] = []
    if prompt_text:
        parts.append(prompt_text)
    if prompt_file:
        parts.append(Path(prompt_file).expanduser().resolve().read_text(encoding="utf-8"))
    return "\n".join(part for part in parts if part).strip()


def parse_directives(text: str) -> dict[str, Any]:
    """Parse supported directives from free-form prompt text."""
    directives: list[dict[str, Any]] = []
    raw_matches: list[str] = []
    stop_after_phases: list[str] = []
    confirm_before_phases: list[str] = []
    operator_review_phases: list[str] = []
    block_on_alerts: list[str] = []

    for match in re.finditer(rf"\bSTOP\s+AFTER\s+{PHASE_PATTERN}\b", text, flags=re.I):
        phase = normalize_phase(match.group(1))
        directives.append({"directive": "stop_after", "phase": phase})
        stop_after_phases.append(phase)
        raw_matches.append(match.group(0))

    for match in re.finditer(rf"\bCONFIRM\s+BEFORE\s+{PHASE_PATTERN}\b", text, flags=re.I):
        phase = normalize_phase(match.group(1))
        directives.append({"directive": "confirm_before", "phase": phase})
        confirm_before_phases.append(phase)
        raw_matches.append(match.group(0))

    for match in re.finditer(rf"\bOPERATOR\s+REVIEW\s+{PHASE_PATTERN}\b", text, flags=re.I):
        phase = normalize_phase(match.group(1))
        directives.append({"directive": "operator_review", "phase": phase})
        operator_review_phases.append(phase)
        raw_matches.append(match.group(0))

    for match in re.finditer(rf"\bBLOCK\s+ON\s+{ALERT_PATTERN}\b", text, flags=re.I):
        alert = normalize_alert(match.group(1))
        directives.append({"directive": "block_on", "alert": alert})
        block_on_alerts.append(alert)
        raw_matches.append(match.group(0))

    if re.search(r"\bAPPROVE\s+WAIVER\s+MANUALLY\b", text, flags=re.I):
        directives.append({"directive": "approve_waiver_manually"})
        raw_matches.extend(match.group(0) for match in re.finditer(r"\bAPPROVE\s+WAIVER\s+MANUALLY\b", text, flags=re.I))

    if re.search(r"\bOPERATOR_CONFIRM_BRIEF_THIN\s*:\s*true\b", text, flags=re.I):
        directives.append({"directive": "operator_confirm_brief_thin"})
        raw_matches.extend(
            match.group(0)
            for match in re.finditer(r"\bOPERATOR_CONFIRM_BRIEF_THIN\s*:\s*true\b", text, flags=re.I)
        )

    return {
        "parsed_at": local_now(),
        "directives": dedupe_ordered(directives),
        "stop_after_phases": dedupe_ordered(stop_after_phases),
        "confirm_before_phases": dedupe_ordered(confirm_before_phases),
        "operator_review_phases": dedupe_ordered(operator_review_phases),
        "block_on_alerts": dedupe_ordered(block_on_alerts),
        "raw_directives_found": dedupe_ordered(raw_matches),
    }


def write_json(data: dict[str, Any], json_out: str | None = None) -> None:
    """Write JSON to stdout and optionally to a file."""
    text = json.dumps(data, indent=2, sort_keys=True) + "\n"
    sys.stdout.write(text)
    if json_out:
        target = Path(json_out).expanduser().resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prompt-text", help="Inline initial prompt text.")
    parser.add_argument("--prompt-file", help="Optional file containing the initial prompt.")
    parser.add_argument("--json-out", help="Optional JSON output path.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    prompt = load_prompt_text(args.prompt_text, args.prompt_file)
    result = parse_directives(prompt)
    write_json(result, args.json_out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
