#!/usr/bin/env python3
"""
Recommend whether the current phase needs a lighter clean-room adversarial probe.

This is the complement to the full adversarial stress-test phase:

- risky feature-heavy phases should get a narrow phase-scoped probe pack
- review/polish/delivery phases should not pay that cost
- the planner can honor explicit brief contracts, but it also backstops them
  with heuristics when the phase clearly introduces new trust-sensitive risk
  surfaces
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import yaml


PHASE_HEADING_RE = re.compile(
    r"^###\s+Phase\s+(?P<number>\d+):\s+(?P<title>.+?)(?:\s+\((?P<status>[^)]+)\))?\s*$",
    re.MULTILINE,
)
BRIEF_PATH_RE = re.compile(r"→\s+`?((?:\/|[A-Za-z]:[\\/])[^\s`]+\.md)`?")
PROBE_SECTION_RE = re.compile(r"^##\s+(Phase-Level Adversarial Probe Pack|Adversarial Probe Pack)\s*$", re.IGNORECASE | re.MULTILINE)

EXPLICIT_TRUE_KEYS = (
    "phase_adversarial_probe_required",
    "adversarial_probe_required",
    "phase_probe_required",
)
EXPLICIT_FAMILY_KEYS = (
    "adversarial_probe_risk_families",
    "probe_risk_families",
    "risk_families",
)

PHASE_KIND_PATTERNS = {
    "stress": re.compile(r"\badversarial stress test|stress test\b", re.IGNORECASE),
    "review": re.compile(
        r"\bartifact polish review|artifact polish|admin usability review|usability review|self-review|self review|quality assurance|qc\b",
        re.IGNORECASE,
    ),
    "delivery": re.compile(r"\bdelivery|client acceptance|handoff\b", re.IGNORECASE),
}

RISK_FAMILY_PATTERNS = {
    "auth_security": re.compile(
        r"\bauth|authentication|authorization|permission|permissions|security|credential|credentials|secret|secrets|keychain|oauth|sso|vault\b",
        re.IGNORECASE,
    ),
    "runtime_permissions": re.compile(
        r"\btauri|native runtime|desktop runtime|macos|screen recording|accessibility api|input monitoring|full disk access|permission walkthrough|notarization|code signing|bootstrap|startup\b",
        re.IGNORECASE,
    ),
    "filesystem_mutation": re.compile(
        r"\bwrite path|mutation|mutations|governed write|admin-command|admin command|approve|deny|comment|correction|confirmation|queue processor|file-drop|file drop|canonical state\b",
        re.IGNORECASE,
    ),
    "ingestion_parsing": re.compile(
        r"\bupload|uploads|ingest|ingestion|parse|parser|frontmatter|yaml|jsonl|csv|malformed|corrupt|knowledge dump|onboarding|handoff\b",
        re.IGNORECASE,
    ),
    "retrieval_memory_sync": re.compile(
        r"\bretrieval|memory|semantic|embeddings|vector|knowledge graph|sync|storage|stale index|corpus|dream|reflection|archive|retention\b",
        re.IGNORECASE,
    ),
    "integrations_external_io": re.compile(
        r"\bintegration|integrations|mcp|plugin|tool access|external api|external service|rate limit|runner|adapter|managed agents|cloud|s3|b2|r2|dropbox|icloud|api key\b",
        re.IGNORECASE,
    ),
    "media_artifacts_live_watch": re.compile(
        r"\blive watch|artifact|artifacts|evidence|screenshot|screenshots|video|walkthrough|preview|media|stream|session replay|side panel\b",
        re.IGNORECASE,
    ),
}

PROBE_CATEGORIES = {
    "auth_security": [
        "revoked or missing credentials",
        "permission downgrade / denied action handling",
        "privilege-boundary enforcement",
    ],
    "runtime_permissions": [
        "denied native permission flow",
        "startup / bootstrap failure handling",
        "partial environment readiness",
    ],
    "filesystem_mutation": [
        "duplicate / replayed mutation attempts",
        "partial write or interrupted mutation flow",
        "governed-write boundary violations",
    ],
    "ingestion_parsing": [
        "malformed or corrupt input files",
        "empty / giant / unsupported input variants",
        "graceful degraded-state rendering",
    ],
    "retrieval_memory_sync": [
        "stale or contradictory memory state",
        "missing / unhealthy index fallbacks",
        "sync degradation without canonical-state corruption",
    ],
    "integrations_external_io": [
        "rate-limit / upstream failure handling",
        "missing credential or adapter outage",
        "unsafe cross-boundary requests",
    ],
    "media_artifacts_live_watch": [
        "missing / broken media references",
        "oversized or unsupported media artifacts",
        "live-watch degradation without crash",
    ],
}

HIGH_RISK_FAMILIES = {"auth_security", "runtime_permissions", "filesystem_mutation"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-plan", required=True, help="Project plan markdown path.")
    parser.add_argument("--phase", required=True, type=int, help="Phase number to assess.")
    parser.add_argument("--brief-resolution", help="Optional brief-resolution markdown path.")
    parser.add_argument("--json-out", required=True, help="Where to write the JSON report.")
    parser.add_argument("--markdown-out", required=True, help="Where to write the markdown report.")
    return parser.parse_args()


def split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    if not text.startswith("---\n"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    data = yaml.safe_load(parts[1].strip()) if parts[1].strip() else {}
    return (data if isinstance(data, dict) else {}), parts[2].lstrip("\n")


def normalize_family(value: str) -> str:
    return str(value or "").strip().lower().replace("-", "_").replace(" ", "_")


def coerce_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    text = str(value).strip().lower()
    if text in {"true", "yes", "y", "1", "required"}:
        return True
    if text in {"false", "no", "n", "0", "not_required", "not required"}:
        return False
    return None


def extract_phase_section(plan_body: str, phase_number: int) -> dict[str, str]:
    matches = list(PHASE_HEADING_RE.finditer(plan_body))
    for idx, match in enumerate(matches):
        if int(match.group("number")) != phase_number:
            continue
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(plan_body)
        return {
            "title": match.group("title").strip(),
            "status": (match.group("status") or "").strip(),
            "body": plan_body[start:end].strip(),
        }
    raise ValueError(f"Phase {phase_number} not found in project plan.")


def parse_brief_paths(brief_resolution_path: Path | None) -> list[Path]:
    if not brief_resolution_path or not brief_resolution_path.exists():
        return []
    text = brief_resolution_path.read_text(encoding="utf-8")
    paths: list[Path] = []
    for raw_path in BRIEF_PATH_RE.findall(text):
        path = Path(raw_path)
        if path.exists() and path not in paths:
            paths.append(path)
    return paths


def load_briefs(paths: list[Path]) -> list[dict[str, Any]]:
    briefs: list[dict[str, Any]] = []
    for path in paths:
        text = path.read_text(encoding="utf-8")
        frontmatter, body = split_frontmatter(text)
        briefs.append(
            {
                "path": str(path),
                "frontmatter": frontmatter,
                "body": body,
                "text": text,
            }
        )
    return briefs


def determine_phase_kind(title: str, body: str) -> str:
    haystack = f"{title}\n{body}"
    for kind, pattern in PHASE_KIND_PATTERNS.items():
        if pattern.search(haystack):
            return kind
    return "build"


def extract_explicit_probe_contract(briefs: list[dict[str, Any]]) -> tuple[bool | None, set[str], list[str]]:
    required: bool | None = None
    families: set[str] = set()
    reasons: list[str] = []
    for brief in briefs:
        frontmatter = brief["frontmatter"]
        body = brief["body"]
        for key in EXPLICIT_TRUE_KEYS:
            if key in frontmatter:
                value = coerce_bool(frontmatter.get(key))
                if value is not None:
                    required = value
                    reasons.append(f"Brief frontmatter sets `{key}: {str(value).lower()}`.")
        for key in EXPLICIT_FAMILY_KEYS:
            value = frontmatter.get(key)
            if isinstance(value, (list, tuple)):
                families.update(normalize_family(item) for item in value if str(item).strip())
            elif value:
                families.update(normalize_family(item) for item in str(value).split(",") if item.strip())
        if PROBE_SECTION_RE.search(body):
            required = True
            reasons.append("Brief body includes a `Phase-Level Adversarial Probe Pack` section.")
    return required, families, reasons


def detect_risk_families(text: str) -> set[str]:
    families = set()
    for family, pattern in RISK_FAMILY_PATTERNS.items():
        if pattern.search(text):
            families.add(family)
    return families


def suggested_probe_categories(risk_families: list[str]) -> list[str]:
    categories: list[str] = []
    for family in risk_families:
        for category in PROBE_CATEGORIES.get(family, []):
            if category not in categories:
                categories.append(category)
    return categories


def recommended_complexity(risk_families: list[str]) -> str:
    if len(risk_families) >= 3 or any(family in HIGH_RISK_FAMILIES for family in risk_families):
        return "deep"
    return "normal"


def build_report(project_plan_path: Path, phase_number: int, brief_resolution_path: Path | None = None) -> dict[str, Any]:
    plan_text = project_plan_path.read_text(encoding="utf-8")
    plan_frontmatter, plan_body = split_frontmatter(plan_text)
    phase = extract_phase_section(plan_body, phase_number)
    brief_paths = parse_brief_paths(brief_resolution_path)
    briefs = load_briefs(brief_paths)

    explicit_required, explicit_families, explicit_reasons = extract_explicit_probe_contract(briefs)
    combined_text = "\n\n".join([phase["title"], phase["body"]] + [brief["text"] for brief in briefs])
    heuristic_families = detect_risk_families(combined_text)
    risk_families = sorted(explicit_families | heuristic_families)
    phase_kind = determine_phase_kind(phase["title"], phase["body"])

    if explicit_required is False:
        required = False
        trigger_mode = "explicit_skip"
        rationale = "The brief explicitly says this phase does not require a phase-level adversarial probe."
    elif explicit_required is True:
        required = True
        trigger_mode = "explicit"
        rationale = "The brief explicitly requires a phase-level adversarial probe."
    elif phase_kind in {"stress", "review", "delivery"}:
        required = False
        trigger_mode = "phase_kind_skip"
        rationale = "This phase is stress/review/delivery-oriented rather than a feature-heavy implementation phase."
    else:
        required = bool(risk_families)
        trigger_mode = "heuristic" if required else "none"
        if required:
            rationale = "The phase introduces trust-sensitive risk surfaces that should be pressure-tested before advancement."
        else:
            rationale = "No strong risky implementation surface was detected for this phase."

    probe_categories = suggested_probe_categories(risk_families)
    report = {
        "project": str(plan_frontmatter.get("project", "")).strip(),
        "phase_number": phase_number,
        "phase_title": phase["title"],
        "phase_status": phase["status"],
        "phase_kind": phase_kind,
        "required": required,
        "trigger_mode": trigger_mode,
        "explicit_contract_present": explicit_required is not None,
        "risk_families": risk_families,
        "probe_categories": probe_categories,
        "recommended_task_type": "adversarial_probe" if required else "",
        "recommended_complexity": recommended_complexity(risk_families) if required else "",
        "recommended_scope": "phase_adversarial_pack" if required else "none",
        "gate_impact": (
            "Artifact polish / phase advancement stays blocked until the phase-level adversarial probe passes."
            if required
            else "No dedicated phase-level adversarial probe required."
        ),
        "rationale": rationale,
        "reasons": explicit_reasons,
        "brief_paths": [str(path) for path in brief_paths],
    }
    return report


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# Phase Adversarial Probe Plan — Phase {report['phase_number']}",
        "",
        f"- Project: `{report.get('project') or 'unknown'}`",
        f"- Phase: `{report['phase_title']}`",
        f"- Phase kind: `{report['phase_kind']}`",
        f"- Required: `{str(report['required']).lower()}`",
        f"- Trigger mode: `{report['trigger_mode']}`",
        f"- Rationale: {report['rationale']}",
    ]
    if report["brief_paths"]:
        lines.append("- Brief inputs:")
        for path in report["brief_paths"]:
            lines.append(f"  - `{path}`")
    if report["reasons"]:
        lines.extend(["", "## Explicit Contract Signals", ""])
        for reason in report["reasons"]:
            lines.append(f"- {reason}")
    lines.extend(["", "## Risk Families", ""])
    if report["risk_families"]:
        for family in report["risk_families"]:
            lines.append(f"- `{family}`")
    else:
        lines.append("- None")
    lines.extend(["", "## Recommendation", ""])
    if report["required"]:
        lines.extend(
            [
                f"- Create one clean-room `{report['recommended_task_type']}` ticket with `probe_scope: {report['recommended_scope']}`.",
                f"- Complexity: `{report['recommended_complexity']}`",
                "- Target probe categories:",
            ]
        )
        for category in report["probe_categories"]:
            lines.append(f"  - {category}")
        lines.append(f"- Gate impact: {report['gate_impact']}")
    else:
        lines.append("- No dedicated phase-level adversarial probe is required for this phase.")
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    report = build_report(
        Path(args.project_plan),
        args.phase,
        Path(args.brief_resolution) if args.brief_resolution else None,
    )

    json_path = Path(args.json_out)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    markdown_path = Path(args.markdown_out)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(render_markdown(report), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
