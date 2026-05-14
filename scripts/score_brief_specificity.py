#!/usr/bin/env python3
"""Score a creative brief for specificity before visual-spec authoring."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TAXONOMY = REPO_ROOT / "vault" / "archive" / "visual-aesthetics" / "_banned_vague_taxonomy.md"
THRESHOLDS = {
    "named_systems": 2,
    "concrete_values": 3,
    "real_workflow_verbs": 3,
    "audience_context": 3,
    "distinctiveness_signals": 2,
}

VENDOR_TERMS = {
    "Apple",
    "AWS",
    "Azure",
    "Brex",
    "Cloudflare",
    "CrowdStrike",
    "Datadog",
    "Figma",
    "GitHub",
    "Google Cloud",
    "Linear",
    "Mercury",
    "Notion",
    "Okta",
    "PagerDuty",
    "Postgres",
    "Salesforce",
    "Snowflake",
    "Stripe",
    "Suricata",
    "Twilio",
    "Vercel",
}

GENERIC_CAPITALIZED = {
    "Audience",
    "Brief",
    "Build",
    "Creative Brief",
    "Objective",
    "Operator Clarifications",
    "Project",
    "The",
    "This",
    "Used",
}

DOMAIN_WORKFLOW_VERBS = {
    "approve",
    "apportion",
    "audit",
    "classify",
    "deploy",
    "dispute",
    "escalate",
    "ingest",
    "investigate",
    "link",
    "materialize",
    "merge",
    "provision",
    "reconcile",
    "remediate",
    "review",
    "route",
    "sign-off",
    "suppress",
    "triage",
}

CLARIFICATION_QUESTIONS = {
    "named_systems": "What specific tools, integrations, products, vendors, or internal systems does this project use?",
    "concrete_values": "What concrete numbers, scales, durations, currencies, rates, or sample values should the artifact represent?",
    "real_workflow_verbs": "What domain-specific actions do users perform, decide, escalate, suppress, reconcile, approve, or hand off?",
    "audience_context": "Who uses this, where do they use it, how often, under what pressure, and with what experience level?",
    "distinctiveness_signals": "What makes this project unlike a generic dashboard, website, app, deck, or workflow?",
}


def utc_now() -> str:
    """Return a UTC ISO-8601 timestamp with timezone."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def strip_frontmatter(text: str) -> str:
    """Remove a leading YAML frontmatter block from markdown."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return text
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return "\n".join(lines[index + 1 :]).strip()
    return text


def normalize(value: Any) -> str:
    """Normalize text for matching."""
    text = str(value or "").lower()
    text = re.sub(r"[^a-z0-9%$./-]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def unique_preserve(items: list[str]) -> list[str]:
    """Deduplicate strings case-insensitively while preserving order."""
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        cleaned = re.sub(r"\s+", " ", str(item).strip())
        if not cleaned:
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(cleaned)
    return result


def parse_taxonomy_verbs() -> set[str]:
    """Read banned standalone workflow verbs from the taxonomy."""
    try:
        text = DEFAULT_TAXONOMY.read_text(encoding="utf-8")
    except OSError:
        return set()
    match = re.search(r"^##\s+Standalone workflow verbs.*?(?P<body>.*?)(?=^##\s+|\Z)", text, flags=re.M | re.S)
    if not match:
        return set()
    verbs: set[str] = set()
    for line in match.group("body").splitlines():
        bullet = re.match(r"^\s*-\s+(.+?)\s*$", line)
        if bullet:
            verbs.add(normalize(bullet.group(1)))
    return verbs


def score_axis(count: int, threshold: int, examples: list[str]) -> dict[str, Any]:
    """Build a standard axis score object."""
    return {"count": count, "threshold": threshold, "passes": count >= threshold, "examples": examples[:12]}


def named_systems(text: str) -> list[str]:
    """Detect named tools, products, vendors, and systems."""
    examples: list[str] = []
    for term in sorted(VENDOR_TERMS, key=lambda item: (-len(item), item)):
        if re.search(rf"\b{re.escape(term)}\b", text):
            examples.append(term)
    tech_pattern = re.compile(
        r"\b(?:EDR|SIEM|SOAR|SCIM|SAML|SOC\s*2|SOC|ACH|FHIR|HIPAA|GDPR|PCI|SOX|API|SDK|SLA)(?:[- ][A-Za-z0-9]+)?\b"
    )
    examples.extend(match.group(0) for match in tech_pattern.finditer(text))
    capitalized_multi = re.compile(r"\b[A-Z][A-Za-z0-9]+(?:[- ][A-Z][A-Za-z0-9]+)+\b")
    for match in capitalized_multi.finditer(text):
        phrase = match.group(0)
        if phrase not in GENERIC_CAPITALIZED and not phrase.startswith("Creative Brief"):
            examples.append(phrase)
    return unique_preserve(examples)


def concrete_values(text: str) -> list[str]:
    """Detect concrete numbers, units, dates, currencies, and durations."""
    examples: list[str] = []
    patterns = [
        r"(?:[$€£]\s?\d[\d,.]*(?:[KMB])?)",
        r"\b\d{4}-\d{2}-\d{2}\b",
        r"\b\d{1,2}/\d{1,2}(?:/\d{2,4})?\b",
        r"\b\d+(?:\.\d+)?(?:-\d+(?:\.\d+)?)?\s*(?:named\s+)?(?:K|M|B|%|alerts?/month|alerts?|detectors?|users?|rows?|records?|incidents?|months?|days?|hours?|hrs?|h|minutes?|mins?|years?|inch|inches|ms|sec|SLA|windows?|shift|shifts?)\b",
        r"\b\d+(?:\.\d+)?(?:-\d+(?:\.\d+)?)?-(?:inch|inches|hour|day|month|year)\b",
        r"\b\d+(?:\.\d+)?[KMB]?\s+(?:alerts?/month|alerts?|detectors?|users?|rows?|records?|incidents?)\b",
        r"\b\d+(?:K|M|B)\b",
    ]
    for pattern in patterns:
        examples.extend(match.group(0) for match in re.finditer(pattern, text, flags=re.I))
    return unique_preserve(examples)


def real_workflow_verbs(text: str) -> list[str]:
    """Detect domain-specific workflow verbs, excluding banned generic verbs."""
    banned = parse_taxonomy_verbs()
    examples: list[str] = []
    for verb in sorted(DOMAIN_WORKFLOW_VERBS):
        if verb in banned:
            continue
        if re.search(rf"\b{re.escape(verb)}(?:s|ed|ing)?\b", text, flags=re.I):
            examples.append(verb)
    qualified_generic = re.compile(
        r"\b(?:send|submit|save|close|create|update|open)\s+(?:[A-Z0-9][A-Za-z0-9-]*|[a-z]+-[a-z0-9-]+|P[0-9]|Form\s+\d+)[A-Za-z0-9 -]*\b"
    )
    for match in qualified_generic.finditer(text):
        phrase = match.group(0)
        first = normalize(phrase).split(" ", 1)[0]
        if first not in banned:
            examples.append(phrase)
    return unique_preserve(examples)


def audience_context_fields(text: str) -> list[str]:
    """Detect audience context dimensions present in the brief."""
    checks = {
        "environment": r"\b(?:desktop|monitor|mobile|field|kiosk|office|SOC|operator console|27-inch|large monitor|in-vehicle|wearable)\b",
        "frequency": r"\b(?:daily|weekly|monthly|hourly|constant|per shift|shift|24/7|hours? per|alerts?/month|one-time|episodic)\b",
        "pressure": r"\b(?:time pressure|incident|urgent|high[- ]stakes|SLA|regulatory|life safety|during incidents|deadline|on-call)\b",
        "role": r"\b(?:analysts?|operators?|admins?|clinicians?|reviewers?|approvers?|developers?|managers?|users?|persona|team)\b",
        "experience_level": r"\b(?:senior|junior|novice|intermediate|expert|power user|years? experience|\d+\s*-\s*\d+\s+years?)\b",
        "concurrent_attention": r"\b(?:interrupted|multi[- ]task|multitask|alert fatigue|during incidents|on-call|handoff|shift change)\b",
    }
    return [field for field, pattern in checks.items() if re.search(pattern, text, flags=re.I)]


def distinctiveness_signals(text: str) -> list[str]:
    """Detect phrases that imply project-specific differentiators."""
    examples: list[str] = []
    patterns = [
        r"\b[A-Z][A-Za-z]+-grade [a-z -]+",
        r"\b\d+\s+named [a-z -]+",
        r"\bunder time pressure\b",
        r"\b24/7\s+SOC\b",
        r"\bfalse positives? for [^.,;\n]+",
        r"\blink related [^.,;\n]+",
        r"\btriage [^.,;\n]+",
        r"\bfor [a-z -]+ who [^.,;\n]+",
        r"\bfrom [^.,;\n]+ named [^.,;\n]+",
    ]
    for pattern in patterns:
        examples.extend(match.group(0) for match in re.finditer(pattern, text, flags=re.I))
    return unique_preserve(examples)


def score_text(text: str, brief_path: str = "<memory>") -> dict[str, Any]:
    """Score a markdown body or full brief text for specificity."""
    body = strip_frontmatter(text)
    axes = {
        "named_systems": score_axis(len(named_systems(body)), THRESHOLDS["named_systems"], named_systems(body)),
        "concrete_values": score_axis(len(concrete_values(body)), THRESHOLDS["concrete_values"], concrete_values(body)),
        "real_workflow_verbs": score_axis(len(real_workflow_verbs(body)), THRESHOLDS["real_workflow_verbs"], real_workflow_verbs(body)),
        "audience_context": score_axis(len(audience_context_fields(body)), THRESHOLDS["audience_context"], audience_context_fields(body)),
        "distinctiveness_signals": score_axis(
            len(distinctiveness_signals(body)), THRESHOLDS["distinctiveness_signals"], distinctiveness_signals(body)
        ),
    }
    overall_passes = all(axis["passes"] for axis in axes.values())
    passed_axes = sum(1 for axis in axes.values() if axis["passes"])
    questions = [CLARIFICATION_QUESTIONS[name] for name, axis in axes.items() if not axis["passes"]]
    return {
        "brief_path": brief_path,
        "scored_at": utc_now(),
        "axis_scores": axes,
        "overall_score": round(passed_axes / len(axes), 4),
        "overall_passes": overall_passes,
        "verdict": "pass" if overall_passes else "fail",
        "clarification_questions": questions,
    }


def score_brief(path: Path) -> dict[str, Any]:
    """Read and score a creative brief file."""
    return score_text(path.read_text(encoding="utf-8"), str(path))


def write_json(data: dict[str, Any], json_out: str | None = None) -> None:
    """Write JSON to stdout and optionally to a file."""
    text = json.dumps(data, indent=2, sort_keys=True) + "\n"
    sys.stdout.write(text)
    if json_out:
        out_path = Path(json_out).expanduser().resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text, encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--brief", required=True, help="Creative brief markdown path.")
    parser.add_argument("--json-out", help="Optional JSON output path.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        result = score_brief(Path(args.brief).expanduser().resolve())
        write_json(result, args.json_out)
        return 0 if result["verdict"] == "pass" else 1
    except Exception as exc:
        result = {"brief_path": args.brief, "scored_at": utc_now(), "error": str(exc), "verdict": "fail"}
        write_json(result, args.json_out)
        return 1


if __name__ == "__main__":
    sys.exit(main())
