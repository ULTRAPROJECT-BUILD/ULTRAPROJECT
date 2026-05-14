#!/usr/bin/env python3
"""Extract brief-grounded specificity candidates for visual specifications."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TAXONOMY = REPO_ROOT / "vault" / "archive" / "visual-aesthetics" / "_banned_vague_taxonomy.md"
SCHEMA_PATH = REPO_ROOT / "schemas" / "specificity-candidates.schema.json"
SLUG_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_-]*$")


class ExtractionError(RuntimeError):
    """Raised when candidate extraction cannot produce a valid artifact."""


def utc_now() -> str:
    """Return a UTC ISO-8601 timestamp with timezone."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def safe_schema_path(path: Path) -> str:
    """Return a schema-safe, repository-relative path label."""
    resolved = path.expanduser().resolve()
    try:
        rel = resolved.relative_to(REPO_ROOT)
        text = rel.as_posix()
    except ValueError:
        text = "external/" + resolved.as_posix().lstrip("/")
    text = re.sub(r"[^A-Za-z0-9._@/#-]", "_", text)
    text = re.sub(r"/+", "/", text).strip("/")
    return text or path.name


def strip_frontmatter(text: str) -> str:
    """Remove a leading YAML frontmatter block from markdown text."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return text
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return "\n".join(lines[index + 1 :]).strip()
    return text


def split_paragraphs(markdown: str) -> list[str]:
    """Split markdown into non-empty paragraphs."""
    body = strip_frontmatter(markdown)
    return [part.strip() for part in re.split(r"\n\s*\n", body) if part.strip()]


def parse_taxonomy_terms(taxonomy_text: str, heading: str) -> set[str]:
    """Parse bullet terms from a named taxonomy section."""
    pattern = re.compile(rf"^##\s+{re.escape(heading)}\b(?P<body>.*?)(?=^##\s+|\Z)", re.M | re.S)
    match = pattern.search(taxonomy_text)
    terms: set[str] = set()
    if match:
        for line in match.group("body").splitlines():
            bullet = re.match(r"^\s*-\s+(.+?)\s*$", line)
            if bullet:
                terms.add(bullet.group(1).strip().strip('"').lower())
    for quoted in re.findall(r'Banned standalone:\s+"([^"]+)"', taxonomy_text, flags=re.I):
        terms.add(quoted.strip().lower())
    return terms


def compose_prompt(brief_text: str, taxonomy_text: str) -> str:
    """Compose the extraction prompt required by plan v5 §A2.2.1."""
    return f"""Read the creative brief. Output JSON with:
- candidate_entities: list of domain-specific nouns from the brief, with brief-quote source (verbatim)
- candidate_workflow_verbs: list of action verbs from the brief, with brief-quote source
- candidate_invariants: list of named regulatory/brand/organizational requirements
- candidate_specific_signals: list of distinctive phrases hinting at project shape
EXCLUDE generic terms from the banned-vague-taxonomy list at vault/archive/visual-aesthetics/_banned_vague_taxonomy.md.
Quote brief verbatim for source.

Return only a JSON object. Candidate entity, invariant, and signal objects must use:
{{"name": "...", "brief_quote": "...", "source_paragraph_index": 0}}
Workflow objects must use:
{{"verb": "...", "brief_quote": "...", "source_paragraph_index": 0}}

BANNED VAGUE TAXONOMY:
<<<TAXONOMY
{taxonomy_text}
TAXONOMY

CREATIVE BRIEF:
<<<BRIEF
{brief_text}
BRIEF
"""


def extract_json_object(raw: str) -> dict[str, Any]:
    """Parse a JSON object from LLM output, allowing fenced JSON wrappers."""
    text = raw.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.S)
    if fenced:
        text = fenced.group(1)
    else:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            text = text[start : end + 1]
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ExtractionError(f"LLM output was not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ExtractionError("LLM output must be a JSON object.")
    if not any(key in data for key in ("candidate_entities", "candidate_workflow_verbs", "candidate_invariants", "candidate_specific_signals")):
        for wrapper_key in ("result", "response", "output", "text", "content"):
            wrapped = data.get(wrapper_key)
            if isinstance(wrapped, str) and "{" in wrapped:
                return extract_json_object(wrapped)
    return data


def run_claude(prompt: str) -> dict[str, Any]:
    """Run Claude in JSON-output mode and parse the result."""
    try:
        completed = subprocess.run(
            ["claude", "-p", "--output-format", "json"],
            input=prompt,
            text=True,
            capture_output=True,
            check=False,
            timeout=300,
        )
    except FileNotFoundError as exc:
        raise ExtractionError("claude executable not found.") from exc
    if completed.returncode != 0:
        raise ExtractionError(f"claude exited {completed.returncode}: {completed.stderr.strip()}")
    return extract_json_object(completed.stdout)


def run_codex(prompt: str) -> dict[str, Any]:
    """Run Codex read-only via stdin and parse the result."""
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix="-specificity-prompt.txt", delete=False) as handle:
        handle.write(prompt)
        temp_path = Path(handle.name)
    try:
        input_text = temp_path.read_text(encoding="utf-8")
        completed = subprocess.run(
            ["codex", "exec", "--skip-git-repo-check"],
            input=input_text,
            text=True,
            capture_output=True,
            check=False,
            timeout=300,
            cwd=REPO_ROOT,
        )
    except FileNotFoundError as exc:
        raise ExtractionError("codex executable not found.") from exc
    finally:
        try:
            temp_path.unlink()
        except OSError:
            pass
    if completed.returncode != 0:
        raise ExtractionError(f"codex exited {completed.returncode}: {completed.stderr.strip()}")
    return extract_json_object(completed.stdout)


def paragraph_index(paragraphs: list[str], quote: str, name: str) -> int:
    """Find the best paragraph index for a candidate quote or name."""
    quote_lower = quote.lower()
    name_lower = name.lower()
    for index, paragraph in enumerate(paragraphs):
        lowered = paragraph.lower()
        if quote_lower and quote_lower in lowered:
            return index
        if name_lower and name_lower in lowered:
            return index
    return 0


def source_quote(paragraphs: list[str], name: str) -> str:
    """Return a short verbatim source paragraph containing a candidate name."""
    lowered = name.lower()
    for paragraph in paragraphs:
        if lowered and lowered in paragraph.lower():
            return paragraph
    return paragraphs[0] if paragraphs else name


def normalize_candidate(item: Any, paragraphs: list[str], *, workflow: bool = False) -> dict[str, Any] | None:
    """Normalize a candidate object returned by an LLM or stub extractor."""
    if isinstance(item, str):
        label = item.strip()
        raw_quote = source_quote(paragraphs, label)
        index = paragraph_index(paragraphs, raw_quote, label)
        return {"verb" if workflow else "name": label, "brief_quote": raw_quote, "source_paragraph_index": index}
    if not isinstance(item, dict):
        return None
    key = "verb" if workflow else "name"
    label = (
        item.get(key)
        or item.get("name")
        or item.get("entity")
        or item.get("signal")
        or item.get("phrase")
        or item.get("description")
    )
    label = str(label or "").strip()
    if not label:
        return None
    raw_quote = str(item.get("brief_quote") or item.get("source") or item.get("quote") or "").strip()
    if not raw_quote:
        raw_quote = source_quote(paragraphs, label)
    raw_index = item.get("source_paragraph_index")
    index = raw_index if isinstance(raw_index, int) and raw_index >= 0 else paragraph_index(paragraphs, raw_quote, label)
    return {key: label, "brief_quote": raw_quote, "source_paragraph_index": index}


def is_banned_standalone(label: str, banned_terms: set[str]) -> bool:
    """Return true when a label is only a banned generic term."""
    normalized = re.sub(r"\s+", " ", label.strip().lower())
    return normalized in banned_terms


def dedupe(items: list[dict[str, Any]], label_key: str) -> list[dict[str, Any]]:
    """Deduplicate candidates by normalized label while preserving order."""
    seen: set[str] = set()
    result: list[dict[str, Any]] = []
    for item in items:
        key = str(item.get(label_key, "")).strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def stub_extract(brief_text: str, taxonomy_text: str) -> dict[str, Any]:
    """Return deterministic candidates for offline tests."""
    paragraphs = split_paragraphs(brief_text)
    body = strip_frontmatter(brief_text)
    banned_entities = parse_taxonomy_terms(taxonomy_text, "Standalone entity terms (must be qualified)")
    banned_verbs = parse_taxonomy_terms(taxonomy_text, "Standalone workflow verbs (must be qualified)")

    vendor_pattern = re.compile(
        r"\b(?:CrowdStrike|Snowflake|Okta|Suricata|Stripe|Linear|Salesforce|Datadog|PagerDuty|AWS|Azure|Google Cloud|Vercel|Notion|Mercury|Brex)\b"
    )
    noun_phrases = re.findall(r"\b(?:[A-Z][A-Za-z0-9]+(?:[- ][A-Z][A-Za-z0-9]+)*|[a-z0-9]+-[a-z0-9-]+|[A-Z]{2,}[A-Za-z0-9-]*)\b", body)
    domain_terms = [
        "security analyst",
        "operator dashboard",
        "alerts",
        "detectors",
        "incidents",
        "false positives",
        "SOC",
        "27-inch monitor",
    ]
    entities = list(vendor_pattern.findall(body)) + [term for term in domain_terms if re.search(re.escape(term), body, re.I)]
    entities.extend(noun_phrases)

    workflow_lexicon = [
        "build",
        "triage",
        "escalate",
        "suppress",
        "link",
        "reconcile",
        "ingest",
        "investigate",
        "remediate",
        "approve",
        "provision",
        "dispute",
        "sign-off",
        "promote",
    ]
    verbs = [verb for verb in workflow_lexicon if re.search(rf"\b{re.escape(verb)}\w*\b", body, re.I)]

    invariant_patterns = [
        r"\b(?:SOC 2|HIPAA|GDPR|PCI|SOX|KYC|SLA)\b",
        r"\b(?:Linear-grade|Stripe-grade|Apple-grade|brand|compliance|regulatory|24/7 SOC)\b",
    ]
    invariants: list[str] = []
    for pattern in invariant_patterns:
        invariants.extend(re.findall(pattern, body, flags=re.I))

    signals = []
    signal_patterns = [
        r"(?<!/)\b\d+[KMB]?\s+[A-Za-z-]+(?:/[A-Za-z-]+)?",
        r"\b\d+/?\d*\s*(?:hours?|h|days?|inch|years?)\b",
        r"\b[A-Z][A-Za-z]+-grade [a-z ]+",
        r"\bunder time pressure\b",
        r"\b24/7 SOC\b",
        r"\b\d+\s+named detectors\b",
    ]
    for pattern in signal_patterns:
        signals.extend(re.findall(pattern, body, flags=re.I))

    def build(labels: list[str], *, workflow: bool = False) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        for label in labels:
            cleaned = str(label).strip()
            if not cleaned:
                continue
            if workflow and is_banned_standalone(cleaned, banned_verbs):
                continue
            if not workflow and is_banned_standalone(cleaned, banned_entities):
                continue
            candidate = normalize_candidate(cleaned, paragraphs, workflow=workflow)
            if candidate:
                normalized.append(candidate)
        return dedupe(normalized, "verb" if workflow else "name")[:12]

    return {
        "candidate_entities": build(entities),
        "candidate_workflow_verbs": build(verbs, workflow=True),
        "candidate_invariants": build(invariants),
        "candidate_specific_signals": build(signals),
    }


def normalize_payload(
    raw: dict[str, Any],
    *,
    project: str,
    client: str | None,
    brief_path: Path,
    brief_text: str,
    extractor: str,
) -> dict[str, Any]:
    """Normalize extracted JSON to the repository schema."""
    paragraphs = split_paragraphs(brief_text)
    payload: dict[str, Any] = {
        "project": project,
        "brief_path": safe_schema_path(brief_path),
        "extracted_at": utc_now(),
        "extractor_agent": extractor,
        "candidate_entities": dedupe(
            [item for raw_item in raw.get("candidate_entities", []) if (item := normalize_candidate(raw_item, paragraphs))],
            "name",
        ),
        "candidate_workflow_verbs": dedupe(
            [
                item
                for raw_item in raw.get("candidate_workflow_verbs", [])
                if (item := normalize_candidate(raw_item, paragraphs, workflow=True))
            ],
            "verb",
        ),
        "candidate_invariants": dedupe(
            [item for raw_item in raw.get("candidate_invariants", []) if (item := normalize_candidate(raw_item, paragraphs))],
            "name",
        ),
        "candidate_specific_signals": dedupe(
            [item for raw_item in raw.get("candidate_specific_signals", []) if (item := normalize_candidate(raw_item, paragraphs))],
            "name",
        ),
    }
    if client:
        payload["client"] = client
    return payload


def validate_schema(payload: dict[str, Any]) -> None:
    """Validate payload against specificity-candidates.schema.json."""
    try:
        import jsonschema
    except ImportError as exc:
        raise ExtractionError("jsonschema is required for candidate schema validation.") from exc
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(payload), key=lambda error: list(error.path))
    if errors:
        details = "; ".join(f"/{'/'.join(str(p) for p in error.path)}: {error.message}" for error in errors)
        raise ExtractionError(f"specificity candidate schema validation failed: {details}")


def default_output_path(project: str, client: str | None) -> Path:
    """Return the default candidate snapshot output path."""
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    filename = f"{date}-specificity-candidates-{project}.json"
    if client:
        return REPO_ROOT / "vault" / "clients" / client / "snapshots" / project / filename
    return REPO_ROOT / "vault" / "snapshots" / project / filename


def write_json(payload: dict[str, Any], path: Path) -> None:
    """Write JSON to stdout and to the requested path."""
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    sys.stdout.write(text)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--brief", required=True, help="Creative brief markdown path.")
    parser.add_argument("--project", required=True, help="Project slug.")
    parser.add_argument("--client", help="Optional client slug.")
    parser.add_argument("--out", help="Output JSON path. Defaults to a vault snapshot path.")
    parser.add_argument("--llm-mode", choices=["claude", "codex", "stub"], default="stub", help="Extractor backend.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if not SLUG_RE.match(args.project):
            raise ExtractionError(f"Invalid project slug: {args.project}")
        if args.client and not SLUG_RE.match(args.client):
            raise ExtractionError(f"Invalid client slug: {args.client}")
        brief_path = Path(args.brief).expanduser().resolve()
        brief_text = brief_path.read_text(encoding="utf-8")
        taxonomy_text = DEFAULT_TAXONOMY.read_text(encoding="utf-8")
        prompt = compose_prompt(brief_text, taxonomy_text)
        if args.llm_mode == "claude":
            raw = run_claude(prompt)
        elif args.llm_mode == "codex":
            raw = run_codex(prompt)
        else:
            raw = stub_extract(brief_text, taxonomy_text)
        payload = normalize_payload(
            raw,
            project=args.project,
            client=args.client,
            brief_path=brief_path,
            brief_text=brief_text,
            extractor=args.llm_mode,
        )
        validate_schema(payload)
        out_path = Path(args.out).expanduser().resolve() if args.out else default_output_path(args.project, args.client)
        write_json(payload, out_path)
        return 0
    except Exception as exc:
        error_payload = {"error": str(exc), "ok": False}
        sys.stdout.write(json.dumps(error_payload, indent=2, sort_keys=True) + "\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
