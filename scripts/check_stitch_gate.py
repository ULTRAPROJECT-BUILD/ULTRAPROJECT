#!/usr/bin/env python3
"""
Fail UI/frontend delivery readiness when required Stitch evidence is missing.

This script is the mechanical proof checker for Stitch-governed UI work. It
expects a creative brief with named Stitch visual targets, on-disk Stitch
artifacts under `.stitch/`, and QC reports that explicitly reference those
targets. It should only be used for tickets whose UI contract is effectively
`design_mode: stitch_required`.

Usage:
    python3 scripts/check_stitch_gate.py \
      --brief brief.md \
      --qc-report qc-report.md \
      --ticket-path ticket.md \
      --deliverables-root /path/to/deliverable \
      --json-out stitch-gate.json \
      --markdown-out stitch-gate.md
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

TIMESTAMP_FMT = "%Y-%m-%dT%H:%M:%S"
STITCH_ID_RE = re.compile(r"screens/[A-Za-z0-9_-]+", re.IGNORECASE)
VISUAL_TARGETS_HEADING_RE = re.compile(r"^##\s+Visual Targets\s*\(Stitch\)\s*$", re.IGNORECASE)
VISUAL_QUALITY_BAR_HEADING_RE = re.compile(r"^##\s+Visual Quality Bar\s*$", re.IGNORECASE)
NARRATIVE_STRUCTURE_HEADING_RE = re.compile(r"^##\s+Narrative Structure\s*$", re.IGNORECASE)
COMPOSITION_ANCHORS_HEADING_RE = re.compile(r"^##\s+Composition Anchors\s*$", re.IGNORECASE)
REPLACE_VS_PRESERVE_HEADING_RE = re.compile(r"^##\s+Replace vs Preserve\s*$", re.IGNORECASE)
PAGE_CONTRACTS_HEADING_RE = re.compile(r"^##\s+Page Contracts\s*$", re.IGNORECASE)
ROUTE_FAMILY_HEADING_RE = re.compile(r"^##\s+Route Family\s*$", re.IGNORECASE)
QC_COMPARISON_RE = re.compile(r"\b(compare|compared|comparison|diff|image-compare)\b", re.IGNORECASE)
QC_RUNTIME_PARITY_RE = re.compile(
    r"\b("
    r"runtime[- ]vs[- ]stitch|runtime vs stitch|stitch parity|composition anchor|"
    r"above-the-fold|above the fold|hero parity|replace vs preserve"
    r")\b",
    re.IGNORECASE,
)
PUBLIC_SURFACE_HINT_RE = re.compile(
    r"\b("
    r"landing page|homepage|home page|pricing page|marketing site|marketing page|"
    r"public-facing|public surface|hero section|hero"
    r")\b",
    re.IGNORECASE,
)
PAGE_CONTRACT_HINT_RE = re.compile(
    r"\b("
    r"account|settings|billing|dashboard|profile|admin panel|admin page"
    r")\b",
    re.IGNORECASE,
)
ROUTE_FAMILY_HINT_RE = re.compile(
    r"\b("
    r"pending review|handoff|memory browser|memory page|trust ledger|audit timeline|audit page|"
    r"live watch|agent console|retrieval / context|retrieval and context|knowledge graph|teach mode|"
    r"comments|feedback page|approvals page|operator console|operator surface|primary route|"
    r"top-level route|top level route|left-rail destination|nav destination"
    r")\b",
    re.IGNORECASE,
)
EXISTING_SURFACE_REDESIGN_HINT_RE = re.compile(
    r"\b("
    r"existing landing page|existing homepage|existing home page|existing pricing page|existing page|"
    r"existing screen|existing surface|current landing page|current homepage|current page|"
    r"redesign|re-design|visual refresh|page overhaul|surface overhaul"
    r")\b",
    re.IGNORECASE,
)
QC_VISUAL_AUDIT_RE = re.compile(
    r"\b("
    r"visual[- ]narrative bar|visual quality bar|narrative structure|hero proposition|"
    r"trust/proof|trust layer|card soup|generic saas layout|interchangeable saas"
    r")\b",
    re.IGNORECASE,
)
QC_PAGE_CONTRACT_RE = re.compile(
    r"\b("
    r"page contract|danger zone|account page|settings page|billing page|dashboard page|admin page"
    r")\b",
    re.IGNORECASE,
)
QC_ROUTE_FAMILY_PARITY_RE = re.compile(
    r"\b("
    r"route family|same-product-family|same product family|family parity|product-family parity|"
    r"generic admin layout|generic admin template|generic split-view|generic split view|"
    r"duplicated page title|filler metric rail|operator workbench"
    r")\b",
    re.IGNORECASE,
)
SCREENSHOT_REF_RE = re.compile(r"\b([A-Za-z0-9._-]+\.(?:png|jpg|jpeg|webp))\b", re.IGNORECASE)
ARTIFACT_EXTENSIONS = {".html", ".png", ".jpg", ".jpeg", ".webp"}
SKIP_DIR_NAMES = {".git", "node_modules", "dist", "build", ".next", ".nuxt", "__pycache__", "coverage"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--brief",
        action="append",
        default=[],
        required=True,
        help="Creative brief path(s). Repeat in project -> phase -> ticket order when a brief stack exists.",
    )
    parser.add_argument("--qc-report", action="append", default=[], required=True, help="QC report path. Repeat as needed.")
    parser.add_argument("--ticket-path", help="Optional ticket markdown path. When present, use frontmatter metadata such as design_mode/public_surface/page_contract_required.")
    parser.add_argument("--deliverables-root", required=True, help="Root of the deliverable or repo being shipped.")
    parser.add_argument("--stitch-root", help="Optional explicit .stitch directory. If omitted, search beneath deliverables root.")
    parser.add_argument("--min-screen-targets", type=int, default=1, help="Minimum number of Stitch targets expected.")
    parser.add_argument("--json-out", required=True, help="Where to write the gate JSON report.")
    parser.add_argument("--markdown-out", required=True, help="Where to write the gate markdown report.")
    return parser.parse_args()


def walk_dirs(root: Path, max_depth: int) -> list[Path]:
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
            if not child.is_dir():
                continue
            if child.name in SKIP_DIR_NAMES:
                continue
            stack.append((child, depth + 1))
    return discovered


def unique_paths(paths: list[Path]) -> list[Path]:
    unique = []
    seen = set()
    for path in paths:
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        unique.append(resolved)
    return sorted(unique, key=lambda path: (len(path.parts), str(path)))


def find_stitch_roots(deliverables_root: Path, explicit_root: str | None) -> list[Path]:
    candidates = []
    if explicit_root:
        explicit = Path(explicit_root).expanduser().resolve()
        if explicit.exists() and explicit.is_dir():
            candidates.append(explicit)

    for directory in walk_dirs(deliverables_root, max_depth=4):
        if directory.name == ".stitch":
            candidates.append(directory)
    return unique_paths(candidates)


def collect_design_md(roots: list[Path]) -> list[Path]:
    paths = []
    for root in roots:
        candidate = root / "DESIGN.md"
        if candidate.exists():
            paths.append(candidate)
    return unique_paths(paths)


def collect_artifacts(roots: list[Path]) -> list[Path]:
    artifacts = []
    for root in roots:
        designs_root = root / "designs"
        if not designs_root.exists() or not designs_root.is_dir():
            continue
        for directory in walk_dirs(designs_root, max_depth=3):
            try:
                children = sorted(directory.iterdir(), key=lambda child: child.name)
            except OSError:
                continue
            for child in children:
                if child.is_file() and child.suffix.lower() in ARTIFACT_EXTENSIONS:
                    artifacts.append(child)
    return unique_paths(artifacts)


def extract_brief_targets(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    targets = []
    seen = set()
    in_visual_targets = False

    for raw_line in lines:
        line = raw_line.rstrip()
        if line.startswith("## "):
            in_visual_targets = bool(VISUAL_TARGETS_HEADING_RE.match(line))
            continue
        if not in_visual_targets or "|" not in line:
            continue

        cells = [cell.strip() for cell in line.split("|")[1:-1]]
        if len(cells) < 2:
            continue

        screen_name = cells[0]
        stitch_cell = cells[1]
        if not screen_name or screen_name.lower() == "screen name":
            continue
        if set(screen_name) == {"-"}:
            continue

        match = STITCH_ID_RE.search(stitch_cell)
        if not match:
            continue

        stitch_id = match.group(0)
        key = (screen_name.lower(), stitch_id.lower())
        if key in seen:
            continue
        seen.add(key)
        targets.append(
            {
                "name": screen_name,
                "stitch_id": stitch_id,
                "source_file": str(path.resolve()),
            }
        )

    if targets:
        return targets

    for stitch_id in sorted(set(STITCH_ID_RE.findall(text)), key=str.lower):
        key = stitch_id.lower()
        if key in seen:
            continue
        seen.add(key)
        targets.append(
            {
                "name": stitch_id,
                "stitch_id": stitch_id,
                "source_file": str(path.resolve()),
            }
        )
    return targets


def collect_targets(brief_paths: list[Path]) -> list[dict]:
    targets = []
    seen = set()
    for path in brief_paths:
        for target in extract_brief_targets(path):
            key = target["stitch_id"].lower()
            if key in seen:
                continue
            seen.add(key)
            targets.append(target)
    return targets


def parse_scalar(value: str) -> object:
    text = value.strip()
    if text.lower() == "true":
        return True
    if text.lower() == "false":
        return False
    return text.strip("\"'")


def normalize_design_mode(value: object) -> str:
    aliases = {
        "stitch": "stitch_required",
        "stitch_required": "stitch_required",
        "concept": "concept_required",
        "concept_required": "concept_required",
        "implementation": "implementation_only",
        "implementation-only": "implementation_only",
        "implementation_only": "implementation_only",
    }
    return aliases.get(str(value or "").strip().lower(), "")


def parse_frontmatter_map(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    frontmatter = parts[1]
    data = {}
    for raw_line in frontmatter.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        data[key.strip()] = parse_scalar(value)
    return data


def analyze_briefs(brief_paths: list[Path], ticket_path: Path | None) -> dict:
    combined_text = []
    for path in brief_paths:
        combined_text.append(path.read_text(encoding="utf-8"))
    combined = "\n".join(combined_text)
    lines = combined.splitlines()
    ticket_text = ticket_path.read_text(encoding="utf-8") if ticket_path and ticket_path.exists() else ""
    ticket_data = parse_frontmatter_map(ticket_path) if ticket_path and ticket_path.exists() else {}
    design_mode = normalize_design_mode(ticket_data.get("design_mode", ""))
    if not design_mode and bool(ticket_data.get("stitch_required", False)):
        design_mode = "stitch_required"
    public_surface_required = bool(ticket_data.get("public_surface", False)) or bool(PUBLIC_SURFACE_HINT_RE.search(combined))
    existing_surface_redesign_required = bool(ticket_data.get("existing_surface_redesign", False)) or bool(
        EXISTING_SURFACE_REDESIGN_HINT_RE.search("\n".join(part for part in (combined, ticket_text) if part))
    )
    page_contract_required = bool(ticket_data.get("page_contract_required", False)) or bool(PAGE_CONTRACT_HINT_RE.search(combined))
    route_family_required = (
        bool(ticket_data.get("route_family_required", False))
        or page_contract_required
        or bool(ROUTE_FAMILY_HINT_RE.search("\n".join(part for part in (combined, ticket_text) if part)))
    )
    return {
        "has_visual_quality_bar": any(VISUAL_QUALITY_BAR_HEADING_RE.match(line.strip()) for line in lines),
        "has_narrative_structure": any(NARRATIVE_STRUCTURE_HEADING_RE.match(line.strip()) for line in lines),
        "has_composition_anchors": any(COMPOSITION_ANCHORS_HEADING_RE.match(line.strip()) for line in lines),
        "composition_anchors": extract_heading_bullets(combined, COMPOSITION_ANCHORS_HEADING_RE),
        "has_replace_vs_preserve": any(REPLACE_VS_PRESERVE_HEADING_RE.match(line.strip()) for line in lines),
        "has_page_contracts": any(PAGE_CONTRACTS_HEADING_RE.match(line.strip()) for line in lines),
        "has_route_family": any(ROUTE_FAMILY_HEADING_RE.match(line.strip()) for line in lines),
        "design_mode": design_mode,
        "public_surface_required": public_surface_required,
        "existing_surface_redesign_required": existing_surface_redesign_required,
        "page_contract_required": page_contract_required,
        "route_family_required": route_family_required,
        "ticket_metadata_used": bool(ticket_data),
        "ticket_path": str(ticket_path.resolve()) if ticket_path and ticket_path.exists() else "",
    }


def analyze_qc_reports(qc_paths: list[Path], targets: list[dict]) -> dict:
    combined_text = []
    for path in qc_paths:
        combined_text.append(path.read_text(encoding="utf-8"))
    combined_original = "\n".join(combined_text)
    combined = combined_original.lower()

    matched = []
    seen = set()
    for target in targets:
        stitch_id = target["stitch_id"].lower()
        name = target["name"].lower()
        if stitch_id in combined or (name and name != stitch_id and name in combined):
            if stitch_id not in seen:
                seen.add(stitch_id)
                matched.append(target)

    return {
        "matched_targets": matched,
        "mentions_comparison": bool(QC_COMPARISON_RE.search(combined)),
        "mentions_visual_audit": bool(QC_VISUAL_AUDIT_RE.search(combined_original)),
        "mentions_runtime_parity": bool(QC_RUNTIME_PARITY_RE.search(combined_original)),
        "mentions_page_contract": bool(QC_PAGE_CONTRACT_RE.search(combined_original)),
        "mentions_route_family_parity": bool(QC_ROUTE_FAMILY_PARITY_RE.search(combined_original)),
        "screenshot_refs": sorted(set(match.group(1) for match in SCREENSHOT_REF_RE.finditer(combined_original))),
        "combined_text": combined_original,
    }


def extract_heading_bullets(text: str, heading_re: re.Pattern[str]) -> list[str]:
    lines = text.splitlines()
    items = []
    in_section = False
    for raw_line in lines:
        stripped = raw_line.strip()
        if stripped.startswith("## "):
            in_section = bool(heading_re.match(stripped))
            continue
        if not in_section:
            continue
        if not stripped:
            continue
        if stripped.startswith("- "):
            item = stripped[2:].strip()
        else:
            numbered = re.match(r"^\d+\.\s+(.*)$", stripped)
            item = numbered.group(1).strip() if numbered else ""
        if item:
            items.append(item)
    return items


def parse_local_timestamp(value: str) -> datetime | None:
    raw = value.strip()
    if not raw:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


def find_files_by_name(root: Path, names: list[str], max_depth: int = 6) -> list[Path]:
    wanted = {name.lower() for name in names}
    if not wanted:
        return []
    matches = []
    for directory in walk_dirs(root, max_depth=max_depth):
        try:
            children = sorted(directory.iterdir(), key=lambda child: child.name)
        except OSError:
            continue
        for child in children:
            if child.is_file() and child.name.lower() in wanted:
                matches.append(child.resolve())
    return unique_paths(matches)


def build_report(args: argparse.Namespace) -> dict:
    deliverables_root = Path(args.deliverables_root).expanduser().resolve()
    brief_paths = [Path(path).expanduser().resolve() for path in args.brief]
    qc_paths = [Path(path).expanduser().resolve() for path in args.qc_report]
    ticket_path = Path(args.ticket_path).expanduser().resolve() if args.ticket_path else None
    ticket_data = parse_frontmatter_map(ticket_path) if ticket_path and ticket_path.exists() else {}
    ticket_created_at = parse_local_timestamp(str(ticket_data.get("created", "")))
    stitch_roots = find_stitch_roots(deliverables_root, args.stitch_root)
    design_md_paths = collect_design_md(stitch_roots)
    artifacts = collect_artifacts(stitch_roots)
    targets = collect_targets(brief_paths)
    brief_analysis = analyze_briefs(brief_paths, ticket_path=ticket_path)
    qc_analysis = analyze_qc_reports(qc_paths, targets)
    matched_targets = qc_analysis["matched_targets"]
    screenshot_refs = qc_analysis["screenshot_refs"]
    runtime_screenshot_paths = find_files_by_name(deliverables_root, screenshot_refs)
    runtime_screenshot_basenames = {path.name.lower() for path in runtime_screenshot_paths}
    matched_anchors = []
    qc_lower = qc_analysis["combined_text"].lower()
    for anchor in brief_analysis["composition_anchors"]:
        normalized = " ".join(anchor.lower().split())
        if normalized and normalized in qc_lower:
            matched_anchors.append(anchor)
    latest_design_md_mtime = max((path.stat().st_mtime for path in design_md_paths), default=0.0)
    latest_artifact_mtime = max((path.stat().st_mtime for path in artifacts), default=0.0)
    design_doc_fresh = bool(ticket_created_at) and latest_design_md_mtime >= ticket_created_at.timestamp()
    artifacts_fresh = bool(ticket_created_at) and latest_artifact_mtime >= ticket_created_at.timestamp()

    required_artifact_count = max(args.min_screen_targets, len(targets))
    checks = [
        {
            "name": "stitch_root_present",
            "ok": bool(stitch_roots),
            "details": ", ".join(str(path) for path in stitch_roots) if stitch_roots else "No .stitch directory found beneath deliverables root.",
        },
        {
            "name": "design_md_present",
            "ok": bool(design_md_paths),
            "details": ", ".join(str(path) for path in design_md_paths) if design_md_paths else "No .stitch/DESIGN.md found.",
        },
        {
            "name": "brief_has_visual_quality_bar",
            "ok": brief_analysis["has_visual_quality_bar"],
            "details": (
                "Creative brief includes a Visual Quality Bar section."
                if brief_analysis["has_visual_quality_bar"]
                else "Creative brief is missing `## Visual Quality Bar`."
            ),
        },
        {
            "name": "brief_has_visual_targets",
            "ok": len(targets) >= args.min_screen_targets,
            "details": (
                f"{len(targets)} Stitch target(s) found."
                if targets
                else "No Stitch screen IDs or Visual Targets (Stitch) table found in the brief."
            ),
        },
        {
            "name": "design_artifacts_present",
            "ok": len(artifacts) >= required_artifact_count,
            "details": (
                f"{len(artifacts)} artifact(s) found under .stitch/designs/ (required >= {required_artifact_count})."
                if artifacts
                else "No downloadable Stitch HTML or screenshot artifacts found under .stitch/designs/."
            ),
        },
        {
            "name": "qc_references_all_targets",
            "ok": bool(targets) and len(matched_targets) == len(targets),
            "details": (
                f"QC references {len(matched_targets)} of {len(targets)} Stitch target(s)."
                if targets
                else "Skipped because the brief did not define any Stitch targets."
            ),
        },
        {
            "name": "qc_mentions_comparison",
            "ok": qc_analysis["mentions_comparison"],
            "details": (
                "QC report contains comparison/diff language."
                if qc_analysis["mentions_comparison"]
                else "QC report does not mention compare/comparison/diff/image-compare."
            ),
        },
        {
            "name": "qc_references_runtime_screenshots",
            "ok": bool(screenshot_refs) and len(runtime_screenshot_paths) == len(set(screenshot_refs)),
            "details": (
                f"QC references {len(screenshot_refs)} screenshot file(s); {len(runtime_screenshot_paths)} resolved under the deliverables root."
                if screenshot_refs
                else "QC report does not reference any runtime screenshot filenames."
            ),
        },
    ]

    if ticket_created_at:
        checks.extend(
            [
                {
                    "name": "design_md_fresh_since_ticket",
                    "ok": design_doc_fresh,
                    "details": (
                        f"Latest .stitch/DESIGN.md is newer than ticket creation ({ticket_data.get('created', '')})."
                        if design_doc_fresh
                        else f"No .stitch/DESIGN.md newer than ticket creation ({ticket_data.get('created', '')})."
                    ),
                },
                {
                    "name": "design_artifacts_fresh_since_ticket",
                    "ok": artifacts_fresh,
                    "details": (
                        f"Latest Stitch artifact is newer than ticket creation ({ticket_data.get('created', '')})."
                        if artifacts_fresh
                        else f"No Stitch artifact under .stitch/designs/ is newer than ticket creation ({ticket_data.get('created', '')})."
                    ),
                },
            ]
        )

    if brief_analysis["public_surface_required"]:
        checks.extend(
            [
                {
                    "name": "brief_has_narrative_structure",
                    "ok": brief_analysis["has_narrative_structure"],
                    "details": (
                        "Creative brief includes a Narrative Structure section for a public-facing surface."
                        if brief_analysis["has_narrative_structure"]
                        else "Public-facing UI detected, but the brief is missing `## Narrative Structure`."
                    ),
                },
                {
                    "name": "qc_mentions_visual_quality_bar",
                    "ok": qc_analysis["mentions_visual_audit"],
                    "details": (
                        "QC report explicitly references the visual-narrative audit."
                        if qc_analysis["mentions_visual_audit"]
                        else "Public-facing UI detected, but the QC report does not mention the visual quality bar, narrative structure, or equivalent design-audit language."
                    ),
                },
            ]
        )

    if brief_analysis["public_surface_required"]:
        checks.append(
            {
                "name": "brief_has_composition_anchors",
                "ok": brief_analysis["has_composition_anchors"] and bool(brief_analysis["composition_anchors"]),
                "details": (
                    f"Creative brief includes {len(brief_analysis['composition_anchors'])} composition anchor(s)."
                    if brief_analysis["has_composition_anchors"] and brief_analysis["composition_anchors"]
                    else "Public-facing UI detected, but the brief is missing `## Composition Anchors` or it is empty."
                ),
            }
        )

    if brief_analysis["route_family_required"]:
        checks.extend(
            [
                {
                    "name": "brief_has_route_family",
                    "ok": brief_analysis["has_route_family"],
                    "details": (
                        "Creative brief includes a Route Family section."
                        if brief_analysis["has_route_family"]
                        else "Route-family-governed surface detected, but the brief is missing `## Route Family`."
                    ),
                },
                {
                    "name": "brief_has_composition_anchors_for_route_family",
                    "ok": brief_analysis["has_composition_anchors"] and bool(brief_analysis["composition_anchors"]),
                    "details": (
                        f"Creative brief includes {len(brief_analysis['composition_anchors'])} composition anchor(s) for route-family parity."
                        if brief_analysis["has_composition_anchors"] and brief_analysis["composition_anchors"]
                        else "Route-family-governed surface detected, but the brief is missing `## Composition Anchors` or it is empty."
                    ),
                },
                {
                    "name": "qc_mentions_route_family_parity",
                    "ok": qc_analysis["mentions_route_family_parity"],
                    "details": (
                        "QC report explicitly references route-family / same-product-family parity."
                        if qc_analysis["mentions_route_family_parity"]
                        else "Route-family-governed surface detected, but the QC report does not mention route-family parity, same-product-family audit, or generic-admin drift."
                    ),
                },
            ]
        )
        if not brief_analysis["existing_surface_redesign_required"]:
            checks.append(
                {
                    "name": "qc_references_route_family_composition_anchors",
                    "ok": bool(brief_analysis["composition_anchors"]) and len(matched_anchors) == len(brief_analysis["composition_anchors"]),
                    "details": (
                        f"QC references {len(matched_anchors)} of {len(brief_analysis['composition_anchors'])} route-family composition anchor(s)."
                        if brief_analysis["composition_anchors"]
                        else "Skipped because the brief did not define route-family composition anchors."
                    ),
                }
            )

    if brief_analysis["existing_surface_redesign_required"]:
        checks.extend(
            [
                {
                    "name": "brief_has_replace_vs_preserve",
                    "ok": brief_analysis["has_replace_vs_preserve"],
                    "details": (
                        "Creative brief includes a Replace vs Preserve section."
                        if brief_analysis["has_replace_vs_preserve"]
                        else "Existing-surface redesign detected, but the brief is missing `## Replace vs Preserve`."
                    ),
                },
                {
                    "name": "qc_mentions_runtime_stitch_parity",
                    "ok": qc_analysis["mentions_runtime_parity"],
                    "details": (
                        "QC report explicitly references runtime-vs-Stitch parity / composition-anchor audit language."
                        if qc_analysis["mentions_runtime_parity"]
                        else "Existing-surface redesign detected, but the QC report does not mention runtime-vs-Stitch parity, composition anchors, above-the-fold, or replace-vs-preserve."
                    ),
                },
                {
                    "name": "qc_references_composition_anchors",
                    "ok": bool(brief_analysis["composition_anchors"]) and len(matched_anchors) == len(brief_analysis["composition_anchors"]),
                    "details": (
                        f"QC references {len(matched_anchors)} of {len(brief_analysis['composition_anchors'])} composition anchor(s)."
                        if brief_analysis["composition_anchors"]
                        else "Skipped because the brief did not define composition anchors."
                    ),
                },
            ]
        )

    if brief_analysis["page_contract_required"]:
        checks.extend(
            [
                {
                    "name": "brief_has_page_contracts",
                    "ok": brief_analysis["has_page_contracts"],
                    "details": (
                        "Creative brief includes a Page Contracts section."
                        if brief_analysis["has_page_contracts"]
                        else "Top-level nav/settings surface detected, but the brief is missing `## Page Contracts`."
                    ),
                },
                {
                    "name": "qc_mentions_page_contract_audit",
                    "ok": qc_analysis["mentions_page_contract"],
                    "details": (
                        "QC report explicitly references the page-contract / danger-zone audit."
                        if qc_analysis["mentions_page_contract"]
                        else "Top-level nav/settings surface detected, but the QC report does not mention page-contract findings or danger-zone placement."
                    ),
                },
            ]
        )

    verdict = "PASS" if all(check["ok"] for check in checks) else "FAIL"
    return {
        "generated_at": datetime.now().strftime(TIMESTAMP_FMT),
        "deliverables_root": str(deliverables_root),
        "stitch_roots": [str(path) for path in stitch_roots],
        "ticket_path": str(ticket_path) if ticket_path else "",
        "briefs": [str(path) for path in brief_paths],
        "qc_reports": [str(path) for path in qc_paths],
        "brief_analysis": brief_analysis,
        "targets": targets,
        "matched_targets": matched_targets,
        "artifact_paths": [str(path) for path in artifacts],
        "runtime_screenshot_refs": screenshot_refs,
        "runtime_screenshot_paths": [str(path) for path in runtime_screenshot_paths],
        "checks": checks,
        "verdict": verdict,
    }


def render_markdown(report: dict) -> str:
    def escape_cell(value: str) -> str:
        return value.replace("|", "\\|")

    lines = [
        "# Stitch Gate Report",
        "",
        f"**Generated:** {report['generated_at']}",
        f"**Deliverables root:** {report['deliverables_root']}",
        f"**Verdict:** {report['verdict']}",
        "",
        "## Scope Detection",
        "",
        f"- Ticket metadata used: {'yes' if report['brief_analysis']['ticket_metadata_used'] else 'no'}",
        f"- Design mode: {report['brief_analysis']['design_mode'] or 'unspecified'}",
        f"- Public-surface requirements detected: {'yes' if report['brief_analysis']['public_surface_required'] else 'no'}",
        f"- Existing-surface redesign detected: {'yes' if report['brief_analysis']['existing_surface_redesign_required'] else 'no'}",
        f"- Page-contract requirements detected: {'yes' if report['brief_analysis']['page_contract_required'] else 'no'}",
        f"- Route-family requirements detected: {'yes' if report['brief_analysis']['route_family_required'] else 'no'}",
        "",
        "## Checks",
        "",
        "| Check | Status | Details |",
        "|------|--------|---------|",
    ]
    for check in report["checks"]:
        lines.append(
            f"| {check['name']} | {'PASS' if check['ok'] else 'FAIL'} | {escape_cell(check['details'])} |"
        )

    lines.extend(
        [
            "",
            "## Targets",
            "",
            "| Screen Name | Stitch ID | Source |",
            "|-------------|-----------|--------|",
        ]
    )
    if report["targets"]:
        for target in report["targets"]:
            lines.append(
                f"| {escape_cell(target['name'])} | {escape_cell(target['stitch_id'])} | {escape_cell(target['source_file'])} |"
            )
    else:
        lines.append("| (none) | | |")

    lines.extend(
        [
            "",
            "## Runtime Screenshots",
            "",
            "| Referenced Filename | Resolved Path |",
            "|---------------------|---------------|",
        ]
    )
    if report["runtime_screenshot_refs"]:
        resolved_by_name = {}
        for path in report["runtime_screenshot_paths"]:
            resolved_by_name.setdefault(Path(path).name.lower(), []).append(path)
        for name in report["runtime_screenshot_refs"]:
            resolved = resolved_by_name.get(name.lower(), [])
            if resolved:
                for path in resolved:
                    lines.append(f"| {escape_cell(name)} | {escape_cell(path)} |")
            else:
                lines.append(f"| {escape_cell(name)} | MISSING |")
    else:
        lines.append("| (none) | |")

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
    sys.exit(main())
