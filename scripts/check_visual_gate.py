#!/usr/bin/env python3
"""
Fail governed UI delivery readiness when the authoritative visual review is weak or missing.

This script is the mechanical checker for the Claude-owned visual review gate.
It expects:

- ticket/brief metadata describing the visual contract
- QC reports that reference concrete runtime screenshot filenames
- a visual review report with structured frontmatter + sections

The visual review report is the place where the orchestrator/Claude lane makes
the actual screenshot/design judgment. This checker verifies that the report is
present, concrete, and strong enough to trust mechanically.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
VAULT_ROOT = REPO_ROOT / "vault"
PLATFORM_PATH = VAULT_ROOT / "config" / "platform.md"

if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

TIMESTAMP_FMT = "%Y-%m-%dT%H:%M:%S"
SCREENSHOT_REF_RE = re.compile(r"\b([A-Za-z0-9._-]+\.(?:png|jpg|jpeg|webp|gif|svg))\b", re.IGNORECASE)
QC_SCREENSHOT_HINT_RE = re.compile(r"\b(qc-screenshot-|qc-slides/|walkthrough|playthrough)\b", re.IGNORECASE)
VISUAL_VERDICT_HEADING_RE = re.compile(r"^##\s+Visual Verdict\b", re.IGNORECASE | re.MULTILINE)
EVIDENCE_REVIEWED_HEADING_RE = re.compile(r"^##\s+Evidence Reviewed\b", re.IGNORECASE | re.MULTILINE)
FINDINGS_HEADING_RE = re.compile(r"^##\s+Findings\b", re.IGNORECASE | re.MULTILINE)
REQUIRED_FIXES_HEADING_RE = re.compile(r"^##\s+Required Fixes\b", re.IGNORECASE | re.MULTILINE)
STITCH_FIDELITY_HEADING_RE = re.compile(r"^##\s+Stitch Fidelity\b", re.IGNORECASE | re.MULTILINE)
VERDICT_HEADING_RE = re.compile(r"^##\s+Verdict:\s*(.+?)\s*$", re.IGNORECASE | re.MULTILINE)
VERDICT_BOLD_RE = re.compile(r"\*\*Verdict:\s*\*?\*?([A-Z]+)\*?\*?\*\*", re.IGNORECASE)
ROUTE_FAMILY_HINT_RE = re.compile(
    r"\b("
    r"pending review|handoff|memory browser|memory page|trust ledger|audit timeline|audit page|"
    r"live watch|agent console|retrieval / context|retrieval and context|knowledge graph|teach mode|"
    r"comments|feedback page|approvals page|operator console|operator surface|primary route|"
    r"top-level route|top level route|left-rail destination|nav destination"
    r")\b",
    re.IGNORECASE,
)
PAGE_CONTRACT_HINT_RE = re.compile(
    r"\b(account|settings|billing|dashboard|profile|admin panel|admin page)\b",
    re.IGNORECASE,
)
PUBLIC_SURFACE_HINT_RE = re.compile(
    r"\b(landing page|homepage|home page|pricing page|marketing site|marketing page|public-facing|public surface|hero section|hero)\b",
    re.IGNORECASE,
)
SKIP_DIR_NAMES = {".git", "node_modules", "dist", "build", ".next", ".nuxt", "__pycache__", "coverage", ".venv", "venv"}
VS_FILE_RE = re.compile(r"\d{4}-\d{2}-\d{2}-visual-spec-.*\.md$", re.IGNORECASE)
TOKEN_FILE_SUFFIXES = {".css", ".scss", ".sass", ".less", ".json", ".js", ".jsx", ".ts", ".tsx", ".html", ".htm", ".yaml", ".yml"}
HTML_FILE_SUFFIXES = {".html", ".htm"}
RUNTIME_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}
SEMANTIC_TAGS = ("header", "aside", "nav", "main", "section")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--brief",
        action="append",
        default=[],
        help="Creative brief path(s). Repeat in project -> phase -> ticket order when a brief stack exists.",
    )
    parser.add_argument("--qc-report", action="append", default=[], required=True, help="QC report path(s).")
    parser.add_argument("--ticket-path", help="Optional ticket markdown path with UI metadata.")
    parser.add_argument("--visual-review-report", required=True, help="Claude visual-review markdown artifact.")
    parser.add_argument("--deliverables-root", required=True, help="Root of the deliverable or repo being shipped.")
    parser.add_argument("--vs-path", default="", help="Optional visual spec markdown path. Auto-resolved when omitted.")
    parser.add_argument("--require-vs-aware", action="store_true", help="Fail if a visual spec cannot be resolved.")
    parser.add_argument("--json-out", required=True, help="Where to write the visual-gate JSON report.")
    parser.add_argument("--markdown-out", required=True, help="Where to write the visual-gate markdown report.")
    return parser.parse_args()


def split_frontmatter(text: str) -> tuple[str, str]:
    if not text.startswith("---\n"):
        return "", text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return "", text
    return parts[1].strip(), parts[2].lstrip("\n")


def parse_frontmatter_map(path: Path) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return {}
    frontmatter_text, _ = split_frontmatter(text)
    if not frontmatter_text:
        return {}
    data = yaml.safe_load(frontmatter_text)
    return data if isinstance(data, dict) else {}


def read_platform_scalar(key: str, default: Any) -> Any:
    """Read a scalar from platform.md, falling back to a default."""
    if not PLATFORM_PATH.exists():
        return default
    text = PLATFORM_PATH.read_text(encoding="utf-8")
    match = re.search(rf"^\s*{re.escape(key)}:\s*(.+?)\s*$", text, flags=re.M)
    if not match:
        return default
    raw = match.group(1).strip().strip('"').strip("'")
    if isinstance(default, bool):
        return raw.lower() in {"true", "yes", "1"}
    if isinstance(default, int):
        try:
            return int(raw)
        except ValueError:
            return default
    if isinstance(default, float):
        try:
            return float(raw)
        except ValueError:
            return default
    return raw


def rel_or_abs(path: Path) -> str:
    """Prefer repo-relative paths for reporting."""
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path.resolve())


def normalize_text(value: Any) -> str:
    """Normalize text loosely for comparisons."""
    return re.sub(r"\s+", " ", str(value or "").strip())


def normalize_token_text(value: Any) -> str:
    """Normalize token names/values for fuzzy presence checks."""
    text = str(value or "").lower()
    text = re.sub(r"[_/#.-]+", " ", text)
    text = re.sub(r"[^a-z0-9%$]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def flatten_tokens(value: Any, prefix: str = "") -> dict[str, Any]:
    """Flatten a nested token dictionary into scalar leaf tokens."""
    if isinstance(value, dict):
        flattened: dict[str, Any] = {}
        for key, child in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            flattened.update(flatten_tokens(child, path))
        return flattened
    return {prefix: value}


def infer_client_from_paths(brief_paths: list[Path], ticket_path: Path | None) -> str | None:
    """Infer a client slug from known vault paths."""
    candidates = [*(str(path.resolve()) for path in brief_paths)]
    if ticket_path is not None:
        candidates.append(str(ticket_path.resolve()))
    for raw in candidates:
        match = re.search(r"/vault/clients/([^/]+)/", raw)
        if match:
            return match.group(1)
    return None


def infer_project(brief_paths: list[Path], ticket_data: dict[str, Any]) -> str:
    """Infer the project slug from ticket metadata or brief frontmatter/path."""
    explicit = normalize_text(ticket_data.get("project"))
    if explicit:
        return explicit
    for brief_path in brief_paths:
        frontmatter = parse_frontmatter_map(brief_path)
        project = normalize_text(frontmatter.get("project"))
        if project:
            return project
        if brief_path.parent.name not in {"snapshots", "incoming"}:
            return brief_path.parent.name
    return ""


def discover_visual_spec(project: str, client: str | None) -> Path | None:
    """Resolve the newest visual spec for the current project."""
    if not project:
        return None
    roots = [VAULT_ROOT / "snapshots" / project]
    if client:
        roots.append(VAULT_ROOT / "clients" / client / "snapshots" / project)
    matches: list[Path] = []
    for root in roots:
        if not root.exists():
            continue
        matches.extend(path.resolve() for path in root.glob("*-visual-spec-*.md") if path.is_file())
    if not matches:
        return None
    return sorted(matches, key=lambda path: (path.name, path.stat().st_mtime_ns), reverse=True)[0]


def resolve_reference_path(vs_path: Path, raw: Any) -> Path | None:
    """Resolve a VS-relative asset path."""
    text = normalize_text(raw)
    if not text:
        return None
    candidate = Path(text).expanduser()
    if candidate.is_absolute():
        return candidate.resolve()
    for path in (vs_path.parent / candidate, REPO_ROOT / candidate):
        if path.exists():
            return path.resolve()
    return (vs_path.parent / candidate).resolve()


def load_json(path: Path) -> dict[str, Any]:
    """Read JSON as an object."""
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def resolve_manifest_path(vs_path: Path, frontmatter: dict[str, Any]) -> Path | None:
    """Resolve the manifest.json associated with a visual spec."""
    for key in ("manifest_path", "manifest"):
        resolved = resolve_reference_path(vs_path, frontmatter.get(key))
        if resolved is not None and resolved.exists():
            return resolved
    direct = vs_path.parent / "manifest.json"
    if direct.exists():
        return direct.resolve()

    mockups = frontmatter.get("mockups") if isinstance(frontmatter.get("mockups"), list) else []
    for item in mockups:
        if not isinstance(item, dict):
            continue
        for key in ("final_html", "final_png"):
            asset_path = resolve_reference_path(vs_path, item.get(key))
            if asset_path is None:
                continue
            for parent in [asset_path.parent, *asset_path.parents]:
                candidate = parent / "manifest.json"
                if candidate.exists():
                    return candidate.resolve()
                if parent == vs_path.parent:
                    break
    return None


def collect_vs_assets(vs_path: Path, frontmatter: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any]:
    """Collect resolved asset paths and specificity contract data from a visual spec."""
    mockup_pngs: list[Path] = []
    mockup_htmls: list[Path] = []
    anti_pattern_pngs: list[Path] = []

    for item in frontmatter.get("mockups", []) if isinstance(frontmatter.get("mockups"), list) else []:
        if not isinstance(item, dict):
            continue
        png = resolve_reference_path(vs_path, item.get("final_png"))
        html = resolve_reference_path(vs_path, item.get("final_html"))
        if png is not None:
            mockup_pngs.append(png)
        if html is not None:
            mockup_htmls.append(html)

    for item in frontmatter.get("references", []) if isinstance(frontmatter.get("references"), list) else []:
        if not isinstance(item, dict):
            continue
        if normalize_text(item.get("role")).lower() != "anti_pattern":
            continue
        png = resolve_reference_path(vs_path, item.get("file"))
        if png is not None:
            anti_pattern_pngs.append(png)

    for item in manifest.get("assets", []) if isinstance(manifest.get("assets"), list) else []:
        if not isinstance(item, dict):
            continue
        role = normalize_text(item.get("role")).lower()
        path = resolve_reference_path(vs_path, item.get("path"))
        if path is None:
            continue
        if role == "mockup" and path.suffix.lower() in HTML_FILE_SUFFIXES:
            mockup_htmls.append(path)
        elif role == "mockup" and path.suffix.lower() in RUNTIME_IMAGE_SUFFIXES:
            mockup_pngs.append(path)
        elif role == "anti_pattern" and path.suffix.lower() == ".png":
            anti_pattern_pngs.append(path)

    def dedupe(paths: list[Path]) -> list[Path]:
        seen: set[str] = set()
        unique: list[Path] = []
        for path in paths:
            key = str(path.resolve())
            if key in seen or not path.exists():
                continue
            seen.add(key)
            unique.append(path.resolve())
        return unique

    return {
        "manifest_tokens": manifest.get("tokens") if isinstance(manifest.get("tokens"), dict) else {},
        "specificity_contract": frontmatter.get("visual_specificity_contract") if isinstance(frontmatter.get("visual_specificity_contract"), dict) else {},
        "mockup_pngs": dedupe(mockup_pngs),
        "mockup_htmls": dedupe(mockup_htmls),
        "anti_pattern_pngs": dedupe(anti_pattern_pngs),
    }


def collect_runtime_token_corpus(deliverables_root: Path) -> tuple[str, list[str]]:
    """Collect token-searchable runtime files."""
    chunks: list[str] = []
    files: list[str] = []
    for path in sorted(deliverables_root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in TOKEN_FILE_SUFFIXES:
            continue
        if any(part in SKIP_DIR_NAMES for part in path.parts):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        files.append(str(path.resolve()))
        chunks.append(f"\n\n# File: {path.name}\n{text}")
    return "".join(chunks), files


def score_runtime_token_presence(tokens: dict[str, Any], runtime_text: str) -> dict[str, Any]:
    """Score runtime token presence by token name or scalar value."""
    flattened = flatten_tokens(tokens)
    total = 0
    matched = 0
    matched_tokens: list[dict[str, Any]] = []
    missing_tokens: list[dict[str, Any]] = []
    corpus_normalized = normalize_token_text(runtime_text)
    corpus_raw = runtime_text.lower()

    for token_name, token_value in flattened.items():
        if not token_name:
            continue
        total += 1
        normalized_name = normalize_token_text(token_name)
        raw_value = normalize_text(token_value)
        normalized_value = normalize_token_text(token_value)
        present = bool(
            normalized_name and normalized_name in corpus_normalized
            or raw_value and raw_value.lower() in corpus_raw
            or normalized_value and normalized_value in corpus_normalized
        )
        record = {"token": token_name, "value": token_value}
        if present:
            matched += 1
            matched_tokens.append(record)
        else:
            missing_tokens.append(record)

    pct = round((matched / total), 4) if total else 0.0
    return {
        "total_tokens": total,
        "matched_tokens": matched,
        "token_presence_pct": pct,
        "matched_examples": matched_tokens[:20],
        "missing_examples": missing_tokens[:20],
    }


def parse_runtime_html(root: Path) -> tuple[list[dict[str, Any]], list[str]]:
    """Parse HTML files under the deliverables root into inspectable docs."""
    import check_visual_specificity as specificity

    docs: list[dict[str, Any]] = []
    paths: list[str] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in HTML_FILE_SUFFIXES:
            continue
        if any(part in SKIP_DIR_NAMES for part in path.parts):
            continue
        try:
            docs.append(specificity.parse_html(path))
            paths.append(str(path.resolve()))
        except Exception:
            continue
    return docs, paths


def summarize_runtime_dom(html_docs: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate text and interactive affordances across runtime HTML."""
    text = "\n".join(str(doc.get("text") or "") for doc in html_docs)
    interactive = "\n".join(
        label
        for doc in html_docs
        for label in doc.get("interactive_labels", [])
        if isinstance(label, str)
    )
    headers = [str(header) for doc in html_docs for header in doc.get("headers", []) if str(header).strip()]
    anchors = [str(anchor) for doc in html_docs for anchor in doc.get("anchors", []) if str(anchor).strip()]
    return {
        "text": text,
        "interactive_text": interactive,
        "headers": headers,
        "anchors": anchors,
        "row_count": max([0] + [int(doc.get("row_count") or 0) for doc in html_docs]),
    }


def semantic_tag_counts(path: Path) -> dict[str, int]:
    """Count semantic layout tags in an HTML document."""
    text = path.read_text(encoding="utf-8", errors="replace").lower()
    return {tag: len(re.findall(rf"<{tag}\b", text)) for tag in SEMANTIC_TAGS}


def compare_topology(mockup_html: Path, runtime_html: Path) -> dict[str, Any]:
    """Compare semantic tag topology between locked mockup HTML and runtime HTML."""
    locked = semantic_tag_counts(mockup_html)
    runtime = semantic_tag_counts(runtime_html)
    per_tag: dict[str, float] = {}
    for tag in SEMANTIC_TAGS:
        baseline = max(locked.get(tag, 0), 1)
        per_tag[tag] = round(abs(runtime.get(tag, 0) - locked.get(tag, 0)) / baseline * 100.0, 2)
    variance = round(max(per_tag.values()) if per_tag else 0.0, 2)
    return {
        "locked_counts": locked,
        "runtime_counts": runtime,
        "per_tag_variance_pct": per_tag,
        "layout_topology_variance_pct": variance,
    }


def resolve_runtime_screenshots(
    deliverables_root: Path,
    resolved_review_paths: list[Path],
    qc_paths: list[Path],
) -> list[dict[str, Any]]:
    """Collect runtime screenshot evidence from review/QC artifacts and deliverables."""
    records: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add(path: Path, source: str) -> None:
        resolved = path.resolve()
        key = str(resolved)
        if key in seen or not resolved.exists() or resolved.suffix.lower() not in RUNTIME_IMAGE_SUFFIXES:
            return
        seen.add(key)
        records.append({"path": resolved, "source": source})

    for path in resolved_review_paths:
        add(path, "visual_review")

    for qc_path in qc_paths:
        parent = qc_path.parent
        for candidate in sorted(parent.rglob("*")):
            if any(part in SKIP_DIR_NAMES for part in candidate.parts):
                continue
            if candidate.is_file() and candidate.suffix.lower() in RUNTIME_IMAGE_SUFFIXES and "qc" in candidate.name.lower():
                add(candidate, "qc_report_dir")

    screenshots_dir = deliverables_root / "screenshots"
    if screenshots_dir.exists():
        for candidate in sorted(screenshots_dir.rglob("*")):
            if any(part in SKIP_DIR_NAMES for part in candidate.parts):
                continue
            if candidate.is_file():
                add(candidate, "deliverables_screenshots")

    return records


def resolve_anchor_runtime_capture(
    runtime_screenshots: list[dict[str, Any]],
    capture_warnings: list[str],
) -> Path | None:
    """Choose a runtime screenshot for anchor-parity checks."""
    if runtime_screenshots:
        return runtime_screenshots[0]["path"]
    if shutil.which("agent-browser"):
        capture_warnings.append("agent-browser executable exists but no standalone capture contract is configured for this script; no live screenshot captured.")
    else:
        capture_warnings.append("agent-browser MCP/CLI unavailable; skipped live runtime capture.")
    return None


def score_specificity_runtime(contract: dict[str, Any], runtime_dom: dict[str, Any]) -> dict[str, Any]:
    """Check runtime DOM against the VS specificity contract."""
    import check_visual_specificity as specificity

    text = runtime_dom.get("text", "")
    interactive_text = runtime_dom.get("interactive_text", "")
    entities = contract.get("domain_entities") if isinstance(contract.get("domain_entities"), list) else []
    workflows = contract.get("workflow_signatures") if isinstance(contract.get("workflow_signatures"), list) else []
    invariants = contract.get("brand_or_context_invariants")
    forbidden = contract.get("forbidden_generic_signals") if isinstance(contract.get("forbidden_generic_signals"), list) else []

    entity_found = [
        str(item.get("name") or "")
        for item in entities
        if isinstance(item, dict) and specificity.contains_phrase(text, item.get("name"))
    ]
    entity_total = len([item for item in entities if isinstance(item, dict) and str(item.get("name") or "").strip()])
    entity_pct = round((len(entity_found) / entity_total), 4) if entity_total else 0.0

    workflow_found = [
        str(item.get("verb") or "")
        for item in workflows
        if isinstance(item, dict)
        and (
            specificity.contains_phrase(interactive_text, item.get("verb"))
            or specificity.contains_phrase(interactive_text, item.get("mockup_affordance"))
        )
    ]

    invariant_missing: list[str] = []
    if isinstance(invariants, list):
        for item in invariants:
            if not isinstance(item, dict):
                continue
            description = str(item.get("description") or "")
            if description and not (
                specificity.contains_phrase(text, description)
                or specificity.token_overlap_present(text, description, 0.45)
            ):
                invariant_missing.append(description)

    forbidden_present = [
        str(item.get("signal") or "")
        for item in forbidden
        if isinstance(item, dict) and specificity.contains_phrase(text, item.get("signal"))
    ]

    passes = entity_pct >= 0.8 and len(workflow_found) >= 5 and not invariant_missing and not forbidden_present
    return {
        "passes": passes,
        "domain_entities_found": entity_found,
        "domain_entities_total": entity_total,
        "domain_entities_pct": entity_pct,
        "workflow_signatures_found": workflow_found,
        "workflow_signatures_found_count": len(workflow_found),
        "missing_invariants": invariant_missing,
        "forbidden_generic_signals_present": forbidden_present,
    }


def walk_dirs(root: Path, max_depth: int = 6) -> list[Path]:
    discovered = []
    stack = [(root, 0)]
    while stack:
        current, depth = stack.pop()
        discovered.append(current)
        if depth >= max_depth:
            continue
        try:
            children = sorted(current.iterdir(), key=lambda child: child.name, reverse=True)
        except OSError:
            continue
        for child in children:
            if child.is_dir() and child.name not in SKIP_DIR_NAMES:
                stack.append((child, depth + 1))
    return discovered


def find_files_by_name(root: Path, names: list[str]) -> list[Path]:
    wanted = {name.lower() for name in names}
    matches = []
    if not wanted:
        return matches
    for directory in walk_dirs(root):
        try:
            children = sorted(directory.iterdir(), key=lambda child: child.name)
        except OSError:
            continue
        for child in children:
            if child.is_file() and child.name.lower() in wanted:
                matches.append(child.resolve())
    seen: set[str] = set()
    unique: list[Path] = []
    for path in matches:
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        unique.append(path)
    return unique


def coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value or "").strip().lower()
    return text in {"true", "yes", "y", "1", "pass", "passed"}


def coerce_string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, tuple):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value or "").strip()
    if not text:
        return []
    if text.startswith("[") and text.endswith("]"):
        try:
            parsed = yaml.safe_load(text)
        except yaml.YAMLError:
            parsed = None
        else:
            if isinstance(parsed, list):
                return [str(item).strip() for item in parsed if str(item).strip()]
    return [part.strip() for part in re.split(r"[\n,]+", text) if part.strip()]


def normalize_verdict(value: Any) -> str:
    text = str(value or "").strip().strip("*").upper()
    if text.startswith("PASS"):
        return "PASS"
    if text.startswith("REVISE"):
        return "REVISE"
    if text.startswith("FAIL"):
        return "FAIL"
    return text or "UNKNOWN"


def normalize_pass_fail(value: Any) -> str:
    if isinstance(value, bool):
        return "pass" if value else "fail"
    text = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    if text in {"pass", "passed", "ok", "yes", "true"}:
        return "pass"
    if text in {"fail", "failed", "no", "false"}:
        return "fail"
    if text in {"n/a", "na", "not_applicable", "not-applicable"}:
        return "not_applicable"
    return text or "unknown"


def normalize_yes_no(value: Any) -> str:
    if isinstance(value, bool):
        return "yes" if value else "no"
    text = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    if text in {"yes", "true"}:
        return "yes"
    if text in {"no", "false"}:
        return "no"
    if text in {"n/a", "na", "not_applicable", "not-applicable"}:
        return "not_applicable"
    return text or "unknown"


def detect_report_verdict(frontmatter: dict[str, Any], text: str) -> str:
    verdict = normalize_verdict(frontmatter.get("verdict"))
    if verdict != "UNKNOWN":
        return verdict
    match = VERDICT_HEADING_RE.search(text)
    if match:
        return normalize_verdict(match.group(1))
    match = VERDICT_BOLD_RE.search(text)
    if match:
        return normalize_verdict(match.group(1))
    return "UNKNOWN"


def read_report(path: Path) -> tuple[dict[str, Any], str]:
    text = path.read_text(encoding="utf-8")
    frontmatter_text, body = split_frontmatter(text)
    if not frontmatter_text:
        return {}, body
    data = yaml.safe_load(frontmatter_text)
    return (data if isinstance(data, dict) else {}), body


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    deliverables_root = Path(args.deliverables_root).expanduser().resolve()
    ticket_path = Path(args.ticket_path).expanduser().resolve() if args.ticket_path else None
    ticket_data = parse_frontmatter_map(ticket_path) if ticket_path and ticket_path.exists() else {}
    brief_paths = [Path(path).expanduser().resolve() for path in args.brief]
    qc_paths = [Path(path).expanduser().resolve() for path in args.qc_report]
    visual_review_path = Path(args.visual_review_report).expanduser().resolve()

    brief_text = "\n".join(path.read_text(encoding="utf-8") for path in brief_paths if path.exists())
    qc_text = "\n".join(path.read_text(encoding="utf-8") for path in qc_paths if path.exists())
    review_frontmatter, review_body = read_report(visual_review_path)
    review_text = review_body
    client = infer_client_from_paths(brief_paths, ticket_path)
    project = infer_project(brief_paths, ticket_data)

    raw_vs_path = str(getattr(args, "vs_path", "") or "")
    explicit_vs_path = Path(raw_vs_path).expanduser().resolve() if raw_vs_path.strip() else None
    resolved_vs_path = explicit_vs_path if explicit_vs_path and explicit_vs_path.exists() else discover_visual_spec(project, client)
    vs_aware = bool(resolved_vs_path and resolved_vs_path.exists())
    vs_warning_messages: list[str] = []
    if getattr(args, "require_vs_aware", False) and not vs_aware:
        vs_warning_messages.append("VS-aware mode was required but no visual spec could be resolved.")

    design_mode = str(ticket_data.get("design_mode", "")).strip()
    public_surface = bool(ticket_data.get("public_surface", False)) or bool(PUBLIC_SURFACE_HINT_RE.search(brief_text))
    page_contract_required = bool(ticket_data.get("page_contract_required", False)) or bool(
        PAGE_CONTRACT_HINT_RE.search(brief_text)
    )
    route_family_required = bool(ticket_data.get("route_family_required", False)) or bool(
        ROUTE_FAMILY_HINT_RE.search(brief_text)
    )
    existing_surface_redesign = bool(ticket_data.get("existing_surface_redesign", False))
    ui_work = bool(ticket_data.get("ui_work", False)) or design_mode in {"stitch_required", "concept_required", "implementation_only"}
    stitch_required = bool(ticket_data.get("stitch_required", False)) or design_mode == "stitch_required"

    qc_screenshot_refs = sorted(set(match.group(1) for match in SCREENSHOT_REF_RE.finditer(qc_text)))
    visual_gate_required = ui_work or stitch_required or public_surface or page_contract_required or route_family_required or bool(qc_screenshot_refs)

    screenshot_files = coerce_string_list(review_frontmatter.get("screenshot_files"))
    resolved_review_paths: list[Path] = []
    search_roots = [deliverables_root] + [path.parent for path in qc_paths]
    seen_paths: set[str] = set()
    for root in search_roots:
        for path in find_files_by_name(root, screenshot_files):
            key = str(path)
            if key in seen_paths:
                continue
            seen_paths.add(key)
            resolved_review_paths.append(path)

    review_files_lower = {name.lower() for name in screenshot_files}
    qc_refs_lower = {name.lower() for name in qc_screenshot_refs}
    covered_qc_refs = sorted(review_files_lower & qc_refs_lower)
    runtime_screenshots = resolve_runtime_screenshots(deliverables_root, resolved_review_paths, qc_paths)

    verdict = detect_report_verdict(review_frontmatter, review_text)
    composition_anchor_parity = normalize_pass_fail(review_frontmatter.get("composition_anchor_parity"))
    route_family_parity = normalize_pass_fail(review_frontmatter.get("route_family_parity"))
    page_contract_parity = normalize_pass_fail(review_frontmatter.get("page_contract_parity"))
    visual_quality_bar = normalize_pass_fail(review_frontmatter.get("visual_quality_bar"))
    generic_admin_drift = normalize_yes_no(review_frontmatter.get("generic_admin_drift"))
    duplicate_shell_chrome = normalize_yes_no(review_frontmatter.get("duplicate_shell_chrome"))
    stitch_runtime_parity = normalize_pass_fail(review_frontmatter.get("stitch_runtime_parity"))
    stitch_surface_traceability = normalize_pass_fail(review_frontmatter.get("stitch_surface_traceability"))
    token_only_basis = normalize_yes_no(review_frontmatter.get("token_only_basis"))
    inspected_images = coerce_bool(review_frontmatter.get("inspected_images"))

    vs_frontmatter: dict[str, Any] = {}
    vs_manifest: dict[str, Any] = {}
    vs_assets: dict[str, Any] = {"manifest_tokens": {}, "specificity_contract": {}, "mockup_pngs": [], "mockup_htmls": [], "anti_pattern_pngs": []}
    token_presence_report: dict[str, Any] | None = None
    anchor_ssim_report: dict[str, Any] | None = None
    topology_report: dict[str, Any] | None = None
    antipattern_report: dict[str, Any] | None = None
    specificity_runtime_report: dict[str, Any] | None = None
    runtime_capture_warnings: list[str] = []
    runtime_html_docs: list[dict[str, Any]] = []
    runtime_html_paths: list[str] = []

    if vs_aware and resolved_vs_path is not None:
        vs_frontmatter = parse_frontmatter_map(resolved_vs_path)
        manifest_path = resolve_manifest_path(resolved_vs_path, vs_frontmatter)
        if manifest_path is not None and manifest_path.exists():
            try:
                vs_manifest = load_json(manifest_path)
            except Exception as exc:
                vs_warning_messages.append(f"failed to parse manifest.json: {exc}")
        else:
            vs_warning_messages.append("visual spec resolved but manifest.json could not be found.")

        vs_assets = collect_vs_assets(resolved_vs_path, vs_frontmatter, vs_manifest)
        runtime_token_text, runtime_token_files = collect_runtime_token_corpus(deliverables_root)
        token_presence_report = score_runtime_token_presence(vs_assets["manifest_tokens"], runtime_token_text)
        token_presence_report["files_scanned"] = runtime_token_files

        runtime_html_docs, runtime_html_paths = parse_runtime_html(deliverables_root)
        runtime_dom = summarize_runtime_dom(runtime_html_docs)

        if vs_assets["specificity_contract"] and runtime_html_docs:
            specificity_runtime_report = score_specificity_runtime(vs_assets["specificity_contract"], runtime_dom)
        elif vs_assets["specificity_contract"]:
            specificity_runtime_report = {
                "passes": False,
                "error": "No runtime HTML files were available for specificity inspection.",
            }

        runtime_anchor = resolve_anchor_runtime_capture(runtime_screenshots, runtime_capture_warnings)
        if runtime_anchor is not None and vs_assets["mockup_pngs"]:
            try:
                import ssim_compare

                anchor_ssim_report = ssim_compare.compute_ssim(vs_assets["mockup_pngs"][0], runtime_anchor)
                anchor_ssim_report["locked_mockup_png"] = str(vs_assets["mockup_pngs"][0])
                anchor_ssim_report["runtime_capture_png"] = str(runtime_anchor)
                anchor_ssim_report["source"] = next(
                    (record["source"] for record in runtime_screenshots if record["path"] == runtime_anchor),
                    "unknown",
                )
            except Exception as exc:
                runtime_capture_warnings.append(f"anchor SSIM comparison failed: {exc}")

        if runtime_anchor is not None and vs_assets["anti_pattern_pngs"]:
            try:
                import compute_phash

                runtime_hash = compute_phash.compute_phash(runtime_anchor).get("phash")
                distances: list[dict[str, Any]] = []
                if runtime_hash:
                    for anti_path in vs_assets["anti_pattern_pngs"]:
                        anti_hash = compute_phash.compute_phash(anti_path).get("phash")
                        if not anti_hash:
                            continue
                        distances.append(
                            {
                                "anti_pattern_png": str(anti_path),
                                "distance": compute_phash.compute_phash_distance(runtime_hash, anti_hash),
                            }
                        )
                antipattern_report = {
                    "runtime_capture_png": str(runtime_anchor),
                    "distances": distances,
                    "min_distance": min((item["distance"] for item in distances), default=None),
                }
            except Exception as exc:
                runtime_capture_warnings.append(f"anti-pattern pHash comparison failed: {exc}")

        if vs_assets["mockup_htmls"] and runtime_html_paths:
            try:
                runtime_index = next(
                    (Path(path) for path in runtime_html_paths if Path(path).name.lower() == "index.html"),
                    Path(runtime_html_paths[0]),
                )
                topology_report = compare_topology(vs_assets["mockup_htmls"][0], runtime_index)
                topology_report["locked_mockup_html"] = str(vs_assets["mockup_htmls"][0])
                topology_report["runtime_html"] = str(runtime_index)
            except Exception as exc:
                vs_warning_messages.append(f"layout topology comparison failed: {exc}")

    checks: list[dict[str, Any]] = [
        {
            "name": "visual_gate_required",
            "ok": True,
            "details": "Governed UI/image-facing review detected." if visual_gate_required else "No governed UI/image-facing review requirement detected.",
        }
    ]

    if visual_gate_required:
        checks.extend(
            [
                {
                    "name": "visual_review_pass",
                    "ok": verdict == "PASS",
                    "details": f"Visual review verdict: {verdict}",
                },
                {
                    "name": "visual_review_inspected_images",
                    "ok": inspected_images,
                    "details": (
                        "Visual review frontmatter declares `inspected_images: true`."
                        if inspected_images
                        else "Visual review frontmatter does not declare `inspected_images: true`."
                    ),
                },
                {
                    "name": "visual_review_has_visual_verdict_section",
                    "ok": bool(VISUAL_VERDICT_HEADING_RE.search(review_text)),
                    "details": (
                        "Visual review includes `## Visual Verdict`."
                        if VISUAL_VERDICT_HEADING_RE.search(review_text)
                        else "Visual review is missing `## Visual Verdict`."
                    ),
                },
                {
                    "name": "visual_review_has_evidence_reviewed_section",
                    "ok": bool(EVIDENCE_REVIEWED_HEADING_RE.search(review_text)),
                    "details": (
                        "Visual review includes `## Evidence Reviewed`."
                        if EVIDENCE_REVIEWED_HEADING_RE.search(review_text)
                        else "Visual review is missing `## Evidence Reviewed`."
                    ),
                },
                {
                    "name": "visual_review_has_findings_section",
                    "ok": bool(FINDINGS_HEADING_RE.search(review_text)),
                    "details": (
                        "Visual review includes `## Findings`."
                        if FINDINGS_HEADING_RE.search(review_text)
                        else "Visual review is missing `## Findings`."
                    ),
                },
                {
                    "name": "visual_review_has_required_fixes_section",
                    "ok": bool(REQUIRED_FIXES_HEADING_RE.search(review_text)),
                    "details": (
                        "Visual review includes `## Required Fixes`."
                        if REQUIRED_FIXES_HEADING_RE.search(review_text)
                        else "Visual review is missing `## Required Fixes`."
                    ),
                },
                {
                    "name": "visual_review_references_runtime_screenshots",
                    "ok": bool(screenshot_files) and len(resolved_review_paths) == len(set(screenshot_files)),
                    "details": (
                        f"Visual review references {len(screenshot_files)} screenshot file(s); {len(resolved_review_paths)} resolved."
                        if screenshot_files
                        else "Visual review frontmatter does not list any `screenshot_files`."
                    ),
                },
                {
                    "name": "visual_review_covers_qc_runtime_screenshots",
                    "ok": bool(covered_qc_refs) if qc_screenshot_refs else True,
                    "details": (
                        f"Visual review covers {len(covered_qc_refs)} of {len(qc_screenshot_refs)} QC screenshot reference(s)."
                        if qc_screenshot_refs
                        else "QC report does not reference concrete screenshot filenames."
                    ),
                },
            ]
        )

        if stitch_required:
            checks.extend(
                [
                    {
                        "name": "visual_review_has_stitch_fidelity_section",
                        "ok": bool(STITCH_FIDELITY_HEADING_RE.search(review_text)),
                        "details": (
                            "Visual review includes `## Stitch Fidelity`."
                            if STITCH_FIDELITY_HEADING_RE.search(review_text)
                            else "Visual review is missing `## Stitch Fidelity`."
                        ),
                    },
                    {
                        "name": "visual_review_clears_stitch_runtime_parity",
                        "ok": stitch_runtime_parity == "pass",
                        "details": f"stitch_runtime_parity={stitch_runtime_parity}",
                    },
                    {
                        "name": "visual_review_clears_stitch_surface_traceability",
                        "ok": stitch_surface_traceability == "pass",
                        "details": f"stitch_surface_traceability={stitch_surface_traceability}",
                    },
                    {
                        "name": "visual_review_rejects_token_only_stitch_basis",
                        "ok": token_only_basis == "no",
                        "details": f"token_only_basis={token_only_basis}",
                    },
                ]
            )

        if public_surface:
            checks.extend(
                [
                    {
                        "name": "visual_review_clears_visual_quality_bar",
                        "ok": visual_quality_bar == "pass",
                        "details": f"visual_quality_bar={visual_quality_bar}",
                    },
                    {
                        "name": "visual_review_clears_composition_anchor_parity",
                        "ok": composition_anchor_parity == "pass",
                        "details": f"composition_anchor_parity={composition_anchor_parity}",
                    },
                ]
            )

        if page_contract_required:
            checks.append(
                {
                    "name": "visual_review_clears_page_contract_parity",
                    "ok": page_contract_parity == "pass",
                    "details": f"page_contract_parity={page_contract_parity}",
                }
            )

        if route_family_required:
            checks.extend(
                [
                    {
                        "name": "visual_review_clears_route_family_parity",
                        "ok": route_family_parity == "pass",
                        "details": f"route_family_parity={route_family_parity}",
                    },
                    {
                        "name": "visual_review_rejects_generic_admin_drift",
                        "ok": generic_admin_drift == "no",
                        "details": f"generic_admin_drift={generic_admin_drift}",
                    },
                    {
                        "name": "visual_review_rejects_duplicate_shell_chrome",
                        "ok": duplicate_shell_chrome == "no",
                        "details": f"duplicate_shell_chrome={duplicate_shell_chrome}",
                    },
                ]
            )

        if existing_surface_redesign and (public_surface or route_family_required):
            checks.append(
                {
                    "name": "visual_review_clears_existing_surface_composition_parity",
                    "ok": composition_anchor_parity == "pass",
                    "details": f"composition_anchor_parity={composition_anchor_parity}",
                }
            )

    if getattr(args, "require_vs_aware", False):
        checks.append(
            {
                "name": "vs_aware_mode_detected",
                "ok": vs_aware,
                "details": (
                    f"Resolved visual spec `{resolved_vs_path}`."
                    if vs_aware and resolved_vs_path is not None
                    else "VS-aware mode required, but no visual spec could be resolved."
                ),
            }
        )

    if vs_aware:
        token_presence_threshold = 0.8
        runtime_ssim_threshold = float(read_platform_scalar("visual_spec_ssim_runtime_min", 0.85))
        topology_threshold = float(read_platform_scalar("visual_spec_layout_topology_variance_max_pct", 20))
        antipattern_threshold = int(read_platform_scalar("visual_spec_phash_forbidden_proximity", 12))

        checks.append(
            {
                "name": "vs_runtime_token_presence",
                "ok": bool(token_presence_report) and float(token_presence_report.get("token_presence_pct") or 0.0) >= token_presence_threshold,
                "details": token_presence_report or {"error": "token presence analysis did not run"},
            }
        )

        checks.append(
            {
                "name": "vs_runtime_anchor_ssim",
                "ok": bool(anchor_ssim_report) and float(anchor_ssim_report.get("ssim") or 0.0) >= runtime_ssim_threshold,
                "details": anchor_ssim_report
                or {
                    "warning": "anchor runtime capture unavailable",
                    "runtime_capture_warnings": runtime_capture_warnings,
                },
            }
        )

        checks.append(
            {
                "name": "vs_runtime_layout_topology",
                "ok": bool(topology_report) and float(topology_report.get("layout_topology_variance_pct") or 100.0) <= topology_threshold,
                "details": topology_report
                or {
                    "warning": "runtime HTML topology comparison unavailable",
                    "runtime_html_paths": runtime_html_paths,
                },
            }
        )

        checks.append(
            {
                "name": "vs_runtime_antipattern_divergence",
                "ok": bool(antipattern_report)
                and antipattern_report.get("min_distance") is not None
                and int(antipattern_report.get("min_distance")) > antipattern_threshold,
                "details": antipattern_report
                or {
                    "warning": "runtime capture or anti-pattern assets unavailable",
                    "runtime_capture_warnings": runtime_capture_warnings,
                },
            }
        )

        checks.append(
            {
                "name": "vs_runtime_specificity_contract",
                "ok": bool(specificity_runtime_report) and bool(specificity_runtime_report.get("passes")),
                "details": specificity_runtime_report
                or {
                    "warning": "specificity runtime analysis unavailable",
                    "runtime_html_paths": runtime_html_paths,
                },
            }
        )

    final_verdict = "PASS" if all(check["ok"] for check in checks) else "FAIL"

    return {
        "generated_at": datetime.now().strftime(TIMESTAMP_FMT),
        "ticket_path": str(ticket_path) if ticket_path else "",
        "deliverables_root": str(deliverables_root),
        "project": project,
        "client": client or "",
        "visual_review_report": str(visual_review_path),
        "briefs": [str(path) for path in brief_paths],
        "qc_reports": [str(path) for path in qc_paths],
        "vs_aware": vs_aware,
        "vs_path": str(resolved_vs_path) if resolved_vs_path else "",
        "vs_warning_messages": vs_warning_messages,
        "runtime_capture_warnings": runtime_capture_warnings,
        "token_presence_pct": float((token_presence_report or {}).get("token_presence_pct") or 0.0),
        "anchor_ssim": float((anchor_ssim_report or {}).get("ssim") or 0.0) if anchor_ssim_report else None,
        "layout_topology_variance_pct": float((topology_report or {}).get("layout_topology_variance_pct") or 0.0)
        if topology_report
        else None,
        "antipattern_min_phash_distance": antipattern_report.get("min_distance") if antipattern_report else None,
        "runtime_specificity_contract": specificity_runtime_report,
        "brief_analysis": {
            "ui_work": ui_work,
            "design_mode": design_mode,
            "stitch_required": stitch_required,
            "public_surface": public_surface,
            "page_contract_required": page_contract_required,
            "route_family_required": route_family_required,
            "existing_surface_redesign": existing_surface_redesign,
            "visual_gate_required": visual_gate_required,
        },
        "qc_analysis": {
            "screenshot_refs": qc_screenshot_refs,
            "mentions_qc_visual_evidence": bool(QC_SCREENSHOT_HINT_RE.search(qc_text)),
        },
        "review_analysis": {
            "verdict": verdict,
            "inspected_images": inspected_images,
            "screenshot_files": screenshot_files,
            "resolved_screenshot_paths": [str(path) for path in resolved_review_paths],
            "runtime_screenshot_candidates": [{"path": str(item["path"]), "source": item["source"]} for item in runtime_screenshots],
            "composition_anchor_parity": composition_anchor_parity,
            "route_family_parity": route_family_parity,
            "page_contract_parity": page_contract_parity,
            "visual_quality_bar": visual_quality_bar,
            "generic_admin_drift": generic_admin_drift,
            "duplicate_shell_chrome": duplicate_shell_chrome,
            "stitch_runtime_parity": stitch_runtime_parity,
            "stitch_surface_traceability": stitch_surface_traceability,
            "token_only_basis": token_only_basis,
        },
        "vs_runtime_analysis": {
            "manifest_tokens_present": bool(vs_assets.get("manifest_tokens")),
            "mockup_pngs": [str(path) for path in vs_assets.get("mockup_pngs", [])],
            "mockup_htmls": [str(path) for path in vs_assets.get("mockup_htmls", [])],
            "anti_pattern_pngs": [str(path) for path in vs_assets.get("anti_pattern_pngs", [])],
            "token_presence": token_presence_report,
            "anchor_ssim": anchor_ssim_report,
            "layout_topology": topology_report,
            "antipattern_divergence": antipattern_report,
            "specificity_contract": specificity_runtime_report,
            "runtime_html_paths": runtime_html_paths,
        },
        "checks": checks,
        "verdict": final_verdict,
    }


def render_markdown(report: dict[str, Any]) -> str:
    def escape_cell(value: str) -> str:
        return value.replace("|", "\\|")

    lines = [
        "# Visual Gate Report",
        "",
        f"**Generated:** {report['generated_at']}",
        f"**Visual review report:** {report['visual_review_report']}",
        f"**Deliverables root:** {report['deliverables_root']}",
        f"**Verdict:** {report['verdict']}",
        "",
        "## Visual Review Summary",
        "",
        f"- VS-aware mode: {'yes' if report.get('vs_aware') else 'no'}",
        f"- Visual spec: {report.get('vs_path') or 'none'}",
        f"- UI work detected: {'yes' if report['brief_analysis']['ui_work'] else 'no'}",
        f"- Design mode: {report['brief_analysis']['design_mode'] or 'none'}",
        f"- Public surface: {'yes' if report['brief_analysis']['public_surface'] else 'no'}",
        f"- Page contracts required: {'yes' if report['brief_analysis']['page_contract_required'] else 'no'}",
        f"- Route family required: {'yes' if report['brief_analysis']['route_family_required'] else 'no'}",
        f"- Existing-surface redesign: {'yes' if report['brief_analysis']['existing_surface_redesign'] else 'no'}",
        f"- Visual gate required: {'yes' if report['brief_analysis']['visual_gate_required'] else 'no'}",
        "",
        f"- Visual review verdict: {report['review_analysis']['verdict']}",
        f"- Inspected images: {'yes' if report['review_analysis']['inspected_images'] else 'no'}",
        f"- Screenshot files listed: {len(report['review_analysis']['screenshot_files'])}",
    ]
    if report.get("vs_aware"):
        lines.extend(
            [
                f"- Runtime token presence: {report.get('token_presence_pct')}",
                f"- Anchor SSIM: {report.get('anchor_ssim') if report.get('anchor_ssim') is not None else 'N/A'}",
                f"- Layout topology variance: {report.get('layout_topology_variance_pct') if report.get('layout_topology_variance_pct') is not None else 'N/A'}",
                f"- Anti-pattern min pHash distance: {report.get('antipattern_min_phash_distance') if report.get('antipattern_min_phash_distance') is not None else 'N/A'}",
            ]
        )
    if report["brief_analysis"]["stitch_required"]:
        lines.extend(
            [
                f"- Stitch runtime parity: {report['review_analysis']['stitch_runtime_parity']}",
                f"- Stitch surface traceability: {report['review_analysis']['stitch_surface_traceability']}",
                f"- Token-only Stitch basis: {report['review_analysis']['token_only_basis']}",
            ]
        )
    lines.extend(
        [
            "",
            "## Checks",
            "",
            "| Check | Status | Details |",
            "|------|--------|---------|",
        ]
    )
    for check in report["checks"]:
        lines.append(
            f"| {check['name']} | {'PASS' if check['ok'] else 'FAIL'} | {escape_cell(check['details'])} |"
        )

    lines.extend(["", "## Resolved Screenshot Paths", ""])
    resolved_paths = report["review_analysis"].get("resolved_screenshot_paths") or []
    if resolved_paths:
        for path in resolved_paths:
            lines.append(f"- {path}")
    else:
        lines.append("- None")
    lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    args = parse_args()
    json_out = Path(args.json_out).expanduser().resolve()
    markdown_out = Path(args.markdown_out).expanduser().resolve()
    json_out.parent.mkdir(parents=True, exist_ok=True)
    markdown_out.parent.mkdir(parents=True, exist_ok=True)

    report = build_report(args)
    json_out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    markdown_out.write_text(render_markdown(report), encoding="utf-8")

    print(f"verdict={report['verdict']}")
    for check in report["checks"]:
        print(f"{check['name']}={'PASS' if check['ok'] else 'FAIL'}")
    print(f"json_report={json_out}")
    print(f"markdown_report={markdown_out}")
    return 0 if report["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
