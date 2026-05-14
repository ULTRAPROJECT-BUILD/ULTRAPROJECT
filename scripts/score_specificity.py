#!/usr/bin/env python3
"""Score a visual specificity contract against brief-derived candidates."""

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
CONTRACT_SCHEMA = REPO_ROOT / "schemas" / "specificity-contract.schema.json"
MIN_ITEM_SCORE = 0.4
MIN_AVERAGE_SCORE = 0.6
MAX_BELOW_0_5_PCT = 20.0


class SpecificityScoreError(RuntimeError):
    """Raised when a specificity score cannot be computed."""


def utc_now() -> str:
    """Return a UTC ISO-8601 timestamp with timezone."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_yaml(text: str) -> Any:
    """Load YAML text with a clear dependency error."""
    try:
        import yaml
    except ImportError as exc:
        raise SpecificityScoreError("PyYAML is required to read VS frontmatter.") from exc
    return yaml.safe_load(text) or {}


def load_frontmatter(path: Path) -> dict[str, Any]:
    """Load YAML frontmatter from a markdown file."""
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        raise SpecificityScoreError(f"{path} does not start with YAML frontmatter.")
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            loaded = load_yaml("\n".join(lines[1:index]))
            if not isinstance(loaded, dict):
                raise SpecificityScoreError(f"{path} frontmatter is not a mapping.")
            return loaded
    raise SpecificityScoreError(f"{path} has no closing YAML frontmatter delimiter.")


def parse_taxonomy_terms(taxonomy_text: str, heading: str) -> set[str]:
    """Parse standalone banned terms from a markdown taxonomy heading."""
    pattern = re.compile(rf"^##\s+{re.escape(heading)}\b(?P<body>.*?)(?=^##\s+|\Z)", re.M | re.S)
    match = pattern.search(taxonomy_text)
    terms: set[str] = set()
    if match:
        for line in match.group("body").splitlines():
            bullet = re.match(r"^\s*-\s+(.+?)\s*$", line)
            if bullet:
                terms.add(normalize_phrase(bullet.group(1).strip().strip('"')))
    for quoted in re.findall(r'Banned standalone:\s+"([^"]+)"', taxonomy_text, flags=re.I):
        terms.add(normalize_phrase(quoted))
    return {term for term in terms if term}


def normalize_phrase(value: Any) -> str:
    """Normalize a phrase for matching."""
    text = str(value or "").lower()
    text = re.sub(r"[_/]+", " ", text)
    text = re.sub(r"[^a-z0-9%$.-]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def tokenize(value: Any) -> list[str]:
    """Tokenize a declaration into lowercase alphanumeric terms."""
    return re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)?", normalize_phrase(value))


def load_candidates(path: Path) -> dict[str, Any]:
    """Load a candidates JSON artifact."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SpecificityScoreError("Candidates JSON must be an object.")
    return data


def validate_contract_schema(contract: dict[str, Any]) -> None:
    """Validate a visual_specificity_contract block against its JSON schema."""
    try:
        import jsonschema
    except ImportError as exc:
        raise SpecificityScoreError("jsonschema is required to validate specificity-contract.schema.json.") from exc
    schema = json.loads(CONTRACT_SCHEMA.read_text(encoding="utf-8"))
    errors = sorted(jsonschema.Draft202012Validator(schema).iter_errors(contract), key=lambda error: list(error.path))
    if errors:
        details = "; ".join(f"/{'/'.join(str(part) for part in error.path)}: {error.message}" for error in errors)
        raise SpecificityScoreError(f"specificity contract schema validation failed: {details}")


def candidate_label(item: dict[str, Any]) -> str:
    """Return the label field used by an entity or workflow candidate."""
    return str(item.get("name") or item.get("verb") or "")


def candidate_texts(candidates: dict[str, Any], field: str) -> list[str]:
    """Return relevant candidate labels and quotes for a specificity field."""
    mapping = {
        "domain_entities": ["candidate_entities"],
        "workflow_signatures": ["candidate_workflow_verbs"],
        "data_texture_requirements": ["candidate_entities", "candidate_specific_signals"],
        "brand_or_context_invariants": ["candidate_invariants", "candidate_specific_signals"],
        "signature_affordances": ["candidate_specific_signals", "candidate_entities", "candidate_workflow_verbs"],
        "forbidden_generic_signals": ["candidate_specific_signals", "candidate_entities", "candidate_workflow_verbs"],
    }
    keys = mapping.get(field, [])
    texts: list[str] = []
    for key in keys:
        for item in candidates.get(key, []):
            if isinstance(item, dict):
                label = candidate_label(item)
                quote = str(item.get("brief_quote") or "")
                if label:
                    texts.append(label)
                if quote:
                    texts.append(quote)
    return texts


def term_specificity_score(name: str, banned_terms: set[str], *, field: str) -> float:
    """Compute a 0..1 term-level specificity score for a declared item."""
    normalized = normalize_phrase(name)
    tokens = tokenize(name)
    if not tokens:
        return 0.0
    banned_token_set = {token for term in banned_terms for token in tokenize(term)}
    has_banned_phrase = normalized in banned_terms
    has_banned_token = any(token in banned_token_set for token in tokens)
    non_banned_tokens = [token for token in tokens if token not in banned_token_set]

    if field == "data_texture_requirements":
        if len(tokens) == 1 and has_banned_token:
            return 0.4
        if has_banned_token and non_banned_tokens:
            return 0.8
        return 1.0

    if has_banned_phrase and len(tokens) <= 1:
        return 0.0
    if len(tokens) == 1 and has_banned_token:
        return 0.0
    if has_banned_token and non_banned_tokens:
        return 0.8 if len(tokens) >= 2 else 0.4
    if len(tokens) >= 2 and non_banned_tokens:
        return 1.0
    if non_banned_tokens:
        return 1.0
    return 0.2


def brief_grounding_score(name: str, candidate_values: list[str]) -> tuple[float, str | None]:
    """Compute a 0..1 brief-grounding score against candidate labels and quotes."""
    normalized = normalize_phrase(name)
    tokens = set(tokenize(name))
    if not normalized or not candidate_values:
        return 0.0, None
    for candidate in candidate_values:
        candidate_norm = normalize_phrase(candidate)
        if normalized == candidate_norm:
            return 1.0, candidate
    for candidate in candidate_values:
        candidate_norm = normalize_phrase(candidate)
        if normalized and (normalized in candidate_norm or candidate_norm in normalized):
            return 0.7, candidate
    if tokens:
        for candidate in candidate_values:
            candidate_tokens = set(tokenize(candidate))
            if not candidate_tokens:
                continue
            overlap = len(tokens & candidate_tokens) / max(len(tokens), 1)
            if overlap >= 0.5:
                return 0.3, candidate
    return 0.0, None


def declaration_items(contract: dict[str, Any]) -> list[tuple[str, str]]:
    """Flatten declared specificity fields into scoreable items."""
    items: list[tuple[str, str]] = []
    for entity in contract.get("domain_entities", []) or []:
        if isinstance(entity, dict):
            items.append(("domain_entities", str(entity.get("name") or "")))
    for workflow in contract.get("workflow_signatures", []) or []:
        if isinstance(workflow, dict):
            items.append(("workflow_signatures", str(workflow.get("verb") or "")))
    data_texture = contract.get("data_texture_requirements") or {}
    if isinstance(data_texture, dict):
        for column in data_texture.get("columns", []) or []:
            if isinstance(column, dict):
                items.append(("data_texture_requirements", str(column.get("name") or "")))
    invariants = contract.get("brand_or_context_invariants")
    if isinstance(invariants, list):
        for invariant in invariants:
            if isinstance(invariant, dict):
                items.append(("brand_or_context_invariants", str(invariant.get("description") or "")))
    elif isinstance(invariants, dict) and invariants.get("none_required"):
        items.append(("brand_or_context_invariants", str(invariants.get("justification") or "none_required")))
    for affordance in contract.get("signature_affordances", []) or []:
        if isinstance(affordance, dict):
            items.append(("signature_affordances", str(affordance.get("name") or "")))
    return [(field, name.strip()) for field, name in items if name.strip()]


def score_contract(vs_path: Path, candidates_path: Path, taxonomy_path: Path) -> dict[str, Any]:
    """Score a visual specificity contract against candidates and taxonomy."""
    frontmatter = load_frontmatter(vs_path)
    contract = frontmatter.get("visual_specificity_contract")
    if not isinstance(contract, dict):
        raise SpecificityScoreError("visual_specificity_contract block is missing or not an object.")
    validate_contract_schema(contract)

    candidates = load_candidates(candidates_path)
    taxonomy_text = taxonomy_path.read_text(encoding="utf-8")
    banned_entities = parse_taxonomy_terms(taxonomy_text, "Standalone entity terms (must be qualified)")
    banned_verbs = parse_taxonomy_terms(taxonomy_text, "Standalone workflow verbs (must be qualified)")

    item_scores: list[dict[str, Any]] = []
    for field, name in declaration_items(contract):
        banned = banned_verbs if field == "workflow_signatures" else banned_entities
        term_score = term_specificity_score(name, banned, field=field)
        brief_score, matched_candidate = brief_grounding_score(name, candidate_texts(candidates, field))
        combined = round(term_score * brief_score, 4)
        item_scores.append(
            {
                "field": field,
                "name": name,
                "term_score": round(term_score, 4),
                "brief_score": round(brief_score, 4),
                "combined": combined,
                "matched_candidate": matched_candidate,
            }
        )

    combined_scores = [item["combined"] for item in item_scores]
    average = sum(combined_scores) / len(combined_scores) if combined_scores else 0.0
    below_0_4 = sum(1 for score in combined_scores if score < MIN_ITEM_SCORE)
    below_0_5 = sum(1 for score in combined_scores if score < 0.5)
    below_0_5_pct = (below_0_5 / len(combined_scores) * 100.0) if combined_scores else 100.0
    passes_per_item = bool(combined_scores) and below_0_4 == 0
    passes_average = average >= MIN_AVERAGE_SCORE
    passes_distribution = below_0_5_pct < MAX_BELOW_0_5_PCT
    verdict = "pass" if passes_per_item and passes_average and passes_distribution else "fail"

    return {
        "vs_path": str(vs_path),
        "candidates_path": str(candidates_path),
        "scored_at": utc_now(),
        "item_scores": item_scores,
        "average_score": round(average, 4),
        "items_below_0_4_count": below_0_4,
        "items_below_0_5_count": below_0_5,
        "items_below_0_5_pct": round(below_0_5_pct, 2),
        "passes_per_item_threshold": passes_per_item,
        "passes_average_threshold": passes_average,
        "passes_distribution_threshold": passes_distribution,
        "verdict": verdict,
    }


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
    parser.add_argument("--vs-path", required=True, help="Visual spec markdown path.")
    parser.add_argument("--candidates", required=True, help="Specificity candidates JSON path.")
    parser.add_argument("--banned-taxonomy", default=str(DEFAULT_TAXONOMY), help="Banned vague taxonomy path.")
    parser.add_argument("--json-out", help="Optional JSON output path.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        result = score_contract(
            Path(args.vs_path).expanduser().resolve(),
            Path(args.candidates).expanduser().resolve(),
            Path(args.banned_taxonomy).expanduser().resolve(),
        )
        write_json(result, args.json_out)
        return 0 if result["verdict"] == "pass" else 1
    except Exception as exc:
        result = {
            "vs_path": args.vs_path,
            "candidates_path": args.candidates,
            "scored_at": utc_now(),
            "error": str(exc),
            "verdict": "fail",
        }
        write_json(result, args.json_out)
        return 1


if __name__ == "__main__":
    sys.exit(main())
