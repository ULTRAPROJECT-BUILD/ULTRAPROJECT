#!/usr/bin/env python3
"""Run visual specificity gate checks against locked mockup references."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
CONTRACT_SCHEMA = REPO_ROOT / "schemas" / "specificity-contract.schema.json"
AUDIENCE_FIELDS = [
    "primary_environment",
    "usage_frequency",
    "usage_pressure",
    "primary_user_role",
    "user_experience_level",
    "concurrent_attention",
]


class VisualSpecificityError(RuntimeError):
    """Raised when the visual specificity gate cannot inspect inputs."""


def utc_now() -> str:
    """Return a UTC ISO-8601 timestamp with timezone."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_yaml(text: str) -> Any:
    """Load YAML with a clear dependency error."""
    try:
        import yaml
    except ImportError as exc:
        raise VisualSpecificityError("PyYAML is required to read VS frontmatter.") from exc
    return yaml.safe_load(text) or {}


def load_frontmatter(path: Path) -> dict[str, Any]:
    """Load YAML frontmatter from a visual spec markdown file."""
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        raise VisualSpecificityError(f"{path} does not start with YAML frontmatter.")
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            loaded = load_yaml("\n".join(lines[1:index]))
            if not isinstance(loaded, dict):
                raise VisualSpecificityError(f"{path} frontmatter is not a mapping.")
            return loaded
    raise VisualSpecificityError(f"{path} has no closing YAML frontmatter delimiter.")


def normalize(value: Any) -> str:
    """Normalize text for case-insensitive matching."""
    text = str(value or "").lower()
    text = re.sub(r"[_/#.-]+", " ", text)
    text = re.sub(r"[^a-z0-9%$]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def tokens(value: Any) -> set[str]:
    """Return normalized word tokens."""
    return set(re.findall(r"[a-z0-9]+", normalize(value)))


def contains_phrase(haystack: str, needle: str) -> bool:
    """Return true when normalized haystack contains normalized needle."""
    cleaned = normalize(needle)
    return bool(cleaned) and cleaned in normalize(haystack)


def token_overlap_present(haystack: str, needle: str, threshold: float = 0.5) -> bool:
    """Return true when enough of needle's tokens appear in haystack."""
    needle_tokens = tokens(needle)
    if not needle_tokens:
        return False
    haystack_tokens = tokens(haystack)
    return len(needle_tokens & haystack_tokens) / len(needle_tokens) >= threshold


def discover_reference_files(root: Path) -> list[Path]:
    """Return inspectable reference files under a directory."""
    if root.is_file():
        return [root]
    suffixes = {".html", ".htm", ".png", ".jpg", ".jpeg", ".txt", ".md", ".svg"}
    return sorted(path for path in root.rglob("*") if path.is_file() and path.suffix.lower() in suffixes)


def parse_html(path: Path) -> dict[str, Any]:
    """Extract visible text and interactive labels from an HTML mockup."""
    try:
        from bs4 import BeautifulSoup
    except ImportError as exc:
        raise VisualSpecificityError("beautifulsoup4 is required to parse web_ui HTML mockups.") from exc
    soup = BeautifulSoup(path.read_text(encoding="utf-8", errors="replace"), "html.parser")
    for hidden in soup(["script", "style", "template"]):
        hidden.decompose()
    text = soup.get_text(" ", strip=True)

    labels: list[str] = []
    selector = "button, a, summary, option, input, textarea, select, [role='button'], [role='menuitem'], [role='tab']"
    for element in soup.select(selector):
        parts = [
            element.get_text(" ", strip=True),
            element.get("aria-label"),
            element.get("title"),
            element.get("alt"),
            element.get("placeholder"),
            element.get("value"),
            element.get("name"),
        ]
        label = " ".join(str(part) for part in parts if part)
        if label.strip():
            labels.append(label.strip())

    headers = [cell.get_text(" ", strip=True) for cell in soup.find_all(["th"])]
    if not headers:
        first_row = soup.find("tr")
        if first_row:
            headers = [cell.get_text(" ", strip=True) for cell in first_row.find_all(["td", "th"])]
    row_count = max(0, len(soup.find_all("tr")) - 1)
    ids_and_classes: list[str] = []
    for element in soup.find_all(True):
        if element.get("id"):
            ids_and_classes.append(str(element.get("id")))
        classes = element.get("class") or []
        ids_and_classes.extend(str(item) for item in classes)

    return {
        "path": str(path),
        "text": text,
        "interactive_labels": labels,
        "headers": headers,
        "row_count": row_count,
        "anchors": ids_and_classes,
    }


def ocr_image(path: Path) -> tuple[list[str], str | None]:
    """OCR an image file, returning readable lines and an optional error."""
    try:
        from PIL import Image
        import pytesseract
    except ImportError as exc:
        return [], f"OCR dependencies missing: {exc.name}"
    try:
        text = pytesseract.image_to_string(Image.open(path))
    except Exception as exc:
        return [], f"OCR failed for {path}: {exc}"
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return lines, None


def inspect_references(root: Path, medium: str) -> dict[str, Any]:
    """Extract searchable text, labels, headers, and OCR lines from references."""
    files = discover_reference_files(root)
    html_files = [path for path in files if path.suffix.lower() in {".html", ".htm"}]
    image_files = [path for path in files if path.suffix.lower() in {".png", ".jpg", ".jpeg"}]
    text_files = [path for path in files if path.suffix.lower() in {".txt", ".md", ".svg"}]

    html_docs: list[dict[str, Any]] = []
    html_errors: list[str] = []
    for path in html_files:
        try:
            html_docs.append(parse_html(path))
        except Exception as exc:
            html_errors.append(str(exc))

    text_chunks: list[str] = []
    for path in text_files:
        text_chunks.append(path.read_text(encoding="utf-8", errors="replace"))
    for doc in html_docs:
        text_chunks.append(str(doc.get("text") or ""))
        text_chunks.extend(str(label) for label in doc.get("interactive_labels", []))
        text_chunks.extend(str(header) for header in doc.get("headers", []))
        text_chunks.extend(str(anchor) for anchor in doc.get("anchors", []))

    ocr_results: dict[str, Any] = {}
    for path in image_files:
        lines, error = ocr_image(path)
        ocr_results[str(path)] = {"lines": lines, "error": error}
        text_chunks.extend(lines)

    return {
        "files": [str(path) for path in files],
        "html_files": [str(path) for path in html_files],
        "image_files": [str(path) for path in image_files],
        "html_errors": html_errors,
        "text": "\n".join(text_chunks),
        "interactive_text": "\n".join(
            label for doc in html_docs for label in doc.get("interactive_labels", []) if isinstance(label, str)
        ),
        "headers": [header for doc in html_docs for header in doc.get("headers", [])],
        "row_count": max([0] + [int(doc.get("row_count") or 0) for doc in html_docs]),
        "anchors": [anchor for doc in html_docs for anchor in doc.get("anchors", [])],
        "ocr_results": ocr_results,
        "medium": medium,
    }


def check(status: bool, name: str, details: dict[str, Any]) -> dict[str, Any]:
    """Build a check result object."""
    return {"status": "pass" if status else "fail", "name": name, "details": details}


def validate_contract_schema(contract: dict[str, Any]) -> tuple[bool, list[str]]:
    """Validate the specificity contract against its JSON schema."""
    try:
        import jsonschema
    except ImportError:
        return False, ["jsonschema is required to validate specificity-contract.schema.json"]
    schema = json.loads(CONTRACT_SCHEMA.read_text(encoding="utf-8"))
    errors = sorted(jsonschema.Draft202012Validator(schema).iter_errors(contract), key=lambda error: list(error.path))
    return not errors, [f"/{'/'.join(str(part) for part in error.path)}: {error.message}" for error in errors]


def contract_presence_check(contract: Any) -> dict[str, Any]:
    """Check 65: all required contract fields and minimum counts are populated."""
    if not isinstance(contract, dict):
        return check(False, "Specificity contract present", {"error": "visual_specificity_contract missing or not an object"})

    schema_ok, schema_errors = validate_contract_schema(contract)
    entities = contract.get("domain_entities") if isinstance(contract.get("domain_entities"), list) else []
    workflows = contract.get("workflow_signatures") if isinstance(contract.get("workflow_signatures"), list) else []
    data_texture = contract.get("data_texture_requirements") if isinstance(contract.get("data_texture_requirements"), dict) else {}
    invariants = contract.get("brand_or_context_invariants")
    if isinstance(invariants, list):
        invariants_ok = len(invariants) >= 3
    elif isinstance(invariants, dict):
        invariants_ok = invariants.get("none_required") is True and len(str(invariants.get("justification") or "")) >= 20
    else:
        invariants_ok = False
    signatures = contract.get("signature_affordances") if isinstance(contract.get("signature_affordances"), list) else []
    forbidden = contract.get("forbidden_generic_signals") if isinstance(contract.get("forbidden_generic_signals"), list) else []
    audience = contract.get("audience_context") if isinstance(contract.get("audience_context"), dict) else {}
    columns = data_texture.get("columns") if isinstance(data_texture.get("columns"), list) else []

    details = {
        "schema_valid": schema_ok,
        "schema_errors": schema_errors,
        "domain_entities_count": len(entities),
        "workflow_signatures_count": len(workflows),
        "data_texture_columns_count": len(columns),
        "brand_or_context_invariants_ok": invariants_ok,
        "signature_affordances_count": len(signatures),
        "forbidden_generic_signals_count": len(forbidden),
        "audience_context_present": bool(audience),
    }
    passed = (
        schema_ok
        and len(entities) >= 5
        and len(workflows) >= 5
        and bool(columns)
        and invariants_ok
        and len(signatures) >= 3
        and len(forbidden) >= 5
        and bool(audience)
    )
    return check(passed, "Specificity contract present", details)


def domain_entity_coverage(contract: dict[str, Any], corpus: dict[str, Any]) -> dict[str, Any]:
    """Check 52: at least 80% of domain entities are findable in mockups."""
    entities = contract.get("domain_entities") or []
    found: list[str] = []
    missing: list[str] = []
    text = str(corpus.get("text") or "")
    for item in entities:
        name = str(item.get("name") or "") if isinstance(item, dict) else ""
        if name and contains_phrase(text, name):
            found.append(name)
        elif name:
            missing.append(name)
    pct = (len(found) / len(entities) * 100.0) if entities else 0.0
    return check(pct >= 80.0, "Domain entity coverage", {"found": found, "missing": missing, "coverage_pct": round(pct, 2)})


def workflow_affordance_coverage(contract: dict[str, Any], corpus: dict[str, Any]) -> dict[str, Any]:
    """Check 53: at least five workflow verbs appear in interactive labels."""
    workflows = contract.get("workflow_signatures") or []
    interactive = str(corpus.get("interactive_text") or "")
    found: list[str] = []
    missing: list[str] = []
    for item in workflows:
        if not isinstance(item, dict):
            continue
        verb = str(item.get("verb") or "")
        affordance = str(item.get("mockup_affordance") or "")
        if contains_phrase(interactive, verb) or contains_phrase(interactive, affordance):
            found.append(verb)
        elif verb:
            missing.append(verb)
    return check(len(found) >= 5, "Workflow signature affordance coverage", {"found": found, "missing": missing, "found_count": len(found)})


def data_texture_match(contract: dict[str, Any], corpus: dict[str, Any]) -> dict[str, Any]:
    """Check 54: visible data shape and column headers match declarations."""
    data_texture = contract.get("data_texture_requirements") or {}
    columns = data_texture.get("columns") if isinstance(data_texture, dict) else []
    declared = [str(column.get("name") or "") for column in columns if isinstance(column, dict) and column.get("name")]
    header_text = "\n".join(str(header) for header in corpus.get("headers", []))
    full_text = str(corpus.get("text") or "")
    found = [name for name in declared if contains_phrase(header_text, name) or contains_phrase(full_text, name)]
    missing = [name for name in declared if name not in found]
    column_pct = (len(found) / len(declared) * 100.0) if declared else 0.0
    sample_target = int(data_texture.get("sample_size_target") or 0) if isinstance(data_texture, dict) else 0
    row_count = int(corpus.get("row_count") or 0)
    sample_visible = sample_target > 0 and (str(sample_target) in full_text or row_count >= min(sample_target, 5))
    passed = bool(declared) and column_pct >= 80.0 and (sample_target <= 1 or sample_visible or row_count > 0)
    return check(
        passed,
        "Data texture match",
        {
            "declared_columns": declared,
            "found_columns": found,
            "missing_columns": missing,
            "column_coverage_pct": round(column_pct, 2),
            "visible_row_count": row_count,
            "sample_size_target": sample_target,
            "sample_visible_or_implied": sample_visible,
        },
    )


def location_present(location: str, references_dir: Path, corpus: dict[str, Any]) -> bool:
    """Return true when a declared mockup location is represented."""
    if not location:
        return False
    path_part, _, anchor_part = location.partition("#")
    cleaned_path = path_part.strip()
    cleaned_anchor = anchor_part.strip()
    possible_paths = [REPO_ROOT / cleaned_path, references_dir / cleaned_path]
    if cleaned_path and any(path.exists() for path in possible_paths):
        if not cleaned_anchor:
            return True
        anchors = "\n".join(str(anchor) for anchor in corpus.get("anchors", []))
        return contains_phrase(anchors, cleaned_anchor) or contains_phrase(str(corpus.get("text") or ""), cleaned_anchor)
    cleaned = (cleaned_anchor or cleaned_path or location).lstrip("#")
    if not cleaned:
        return True
    anchors = "\n".join(str(anchor) for anchor in corpus.get("anchors", []))
    return contains_phrase(anchors, cleaned) or contains_phrase(str(corpus.get("text") or ""), cleaned)


def invariant_presence(contract: dict[str, Any], references_dir: Path, corpus: dict[str, Any]) -> dict[str, Any]:
    """Check 55: declared invariants are present at their declared locations."""
    invariants = contract.get("brand_or_context_invariants")
    if isinstance(invariants, dict) and invariants.get("none_required"):
        return check(True, "Brand/context invariants present", {"none_required": True})
    present: list[str] = []
    missing: list[dict[str, str]] = []
    text = str(corpus.get("text") or "")
    for item in invariants or []:
        if not isinstance(item, dict):
            continue
        description = str(item.get("description") or "")
        location = str(item.get("mockup_location") or "")
        text_ok = contains_phrase(text, description) or token_overlap_present(text, description, 0.45)
        location_ok = location_present(location, references_dir, corpus)
        if text_ok and location_ok:
            present.append(description)
        else:
            missing.append({"description": description, "mockup_location": location, "text_ok": str(text_ok), "location_ok": str(location_ok)})
    return check(bool(invariants) and not missing, "Brand/context invariants present", {"present": present, "missing": missing})


def signature_affordance_count(contract: dict[str, Any], corpus: dict[str, Any]) -> dict[str, Any]:
    """Check 56: at least three signature affordances are visible by name."""
    signatures = contract.get("signature_affordances") or []
    text = str(corpus.get("text") or "")
    found: list[str] = []
    missing: list[str] = []
    for item in signatures:
        name = str(item.get("name") or "") if isinstance(item, dict) else ""
        if name and contains_phrase(text, name):
            found.append(name)
        elif name:
            missing.append(name)
    return check(len(found) >= 3, "Signature affordance count", {"found": found, "missing": missing, "found_count": len(found)})


def forbidden_generic_absent(contract: dict[str, Any], corpus: dict[str, Any]) -> dict[str, Any]:
    """Check 57: declared forbidden generic signals are absent."""
    forbidden = contract.get("forbidden_generic_signals") or []
    text = str(corpus.get("text") or "")
    present: list[str] = []
    absent: list[str] = []
    for item in forbidden:
        signal = str(item.get("signal") or "") if isinstance(item, dict) else ""
        if signal and contains_phrase(text, signal):
            present.append(signal)
        elif signal:
            absent.append(signal)
    return check(not present, "Forbidden generic signals absent", {"present": present, "absent": absent})


def ocr_extractability(contract: dict[str, Any], corpus: dict[str, Any]) -> dict[str, Any]:
    """Check 66: non-HTML mockups have at least one readable OCR line per image anchor."""
    if corpus.get("html_files"):
        return check(True, "OCR extractability", {"skipped": True, "reason": "html mockups provide extractable text"})
    image_files = corpus.get("image_files", []) or []
    if not image_files:
        return check(True, "OCR extractability", {"skipped": True, "reason": "no non-HTML image mockups found"})
    results = corpus.get("ocr_results", {}) or {}
    unreadable = []
    readable = []
    for image in image_files:
        result = results.get(image, {})
        lines = result.get("lines") or []
        if lines:
            readable.append({"path": image, "line_count": len(lines)})
        else:
            unreadable.append({"path": image, "error": result.get("error") or "no readable OCR lines"})
    return check(not unreadable, "OCR extractability", {"readable": readable, "unreadable": unreadable})


def audience_context_present(contract: dict[str, Any]) -> dict[str, Any]:
    """Check 77: at least three required audience context fields are populated."""
    audience = contract.get("audience_context") if isinstance(contract, dict) else {}
    populated = [field for field in AUDIENCE_FIELDS if isinstance(audience, dict) and str(audience.get(field) or "").strip()]
    missing = [field for field in AUDIENCE_FIELDS if field not in populated]
    return check(
        len(populated) >= 3,
        "Audience context field present",
        {"populated_fields": populated, "missing_fields": missing, "populated_count": len(populated), "required_min": 3},
    )


def run_checks(vs_path: Path, references_dir: Path, medium: str) -> dict[str, Any]:
    """Run checks 52-57, 65-66, and 77."""
    frontmatter = load_frontmatter(vs_path)
    contract = frontmatter.get("visual_specificity_contract")
    corpus = inspect_references(references_dir, medium)
    contract_dict = contract if isinstance(contract, dict) else {}

    checks = {
        "52": domain_entity_coverage(contract_dict, corpus),
        "53": workflow_affordance_coverage(contract_dict, corpus),
        "54": data_texture_match(contract_dict, corpus),
        "55": invariant_presence(contract_dict, references_dir, corpus),
        "56": signature_affordance_count(contract_dict, corpus),
        "57": forbidden_generic_absent(contract_dict, corpus),
        "65": contract_presence_check(contract),
        "66": ocr_extractability(contract_dict, corpus),
        "77": audience_context_present(contract_dict),
    }
    verdict = "pass" if all(item["status"] == "pass" for item in checks.values()) else "fail"
    return {
        "vs_path": str(vs_path),
        "references_dir": str(references_dir),
        "medium": medium,
        "checked_at": utc_now(),
        "checks": checks,
        "reference_summary": {
            "files_count": len(corpus.get("files", [])),
            "html_files_count": len(corpus.get("html_files", [])),
            "image_files_count": len(corpus.get("image_files", [])),
            "html_errors": corpus.get("html_errors", []),
        },
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
    parser.add_argument("--references-dir", required=True, help="Directory containing locked mockup references.")
    parser.add_argument("--medium", required=True, help="Medium identifier, e.g. web_ui.")
    parser.add_argument("--json-out", help="Optional JSON output path.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        result = run_checks(
            Path(args.vs_path).expanduser().resolve(),
            Path(args.references_dir).expanduser().resolve(),
            args.medium,
        )
        write_json(result, args.json_out)
        return 0 if result["verdict"] == "pass" else 1
    except Exception as exc:
        result = {
            "vs_path": args.vs_path,
            "references_dir": args.references_dir,
            "medium": args.medium,
            "checked_at": utc_now(),
            "error": str(exc),
            "verdict": "fail",
        }
        write_json(result, args.json_out)
        return 1


if __name__ == "__main__":
    sys.exit(main())
