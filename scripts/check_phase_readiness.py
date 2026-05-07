#!/usr/bin/env python3
"""
Mechanical pre-gate readiness check for a project phase.

This script is intentionally opinionated. It blocks phase-gate review when the
phase is obviously not ready yet due to:
- open or missing phase tickets
- contradictory ticket handoff/closeout artifacts
- stale evidence docs relative to the latest phase ticket activity
- brief-required QC screenshot evidence that is missing or uncited
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Iterable

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from check_ticket_evidence import build_report as build_ticket_evidence_report
from check_ticket_evidence import parse_frontmatter_map
from resolve_briefs import build_report as build_brief_resolution_report

TIMESTAMP_FMT = "%Y-%m-%dT%H:%M:%S"
PHASE_HEADER_RE = re.compile(r"^###\s+Phase\s+(\d+):\s*(.+?)\s*$")
TICKET_ID_RE = re.compile(r"\bT-\d+\b", re.IGNORECASE)
SCREENSHOT_RE = re.compile(r"(qc-screenshot-[A-Za-z0-9._-]+\.(?:png|jpg|jpeg|webp)|qc-slides/[A-Za-z0-9._/-]+\.(?:png|jpg|jpeg|webp))", re.IGNORECASE)
FRONTMATTER_TS_KEYS = ("captured", "updated", "completed", "created")
BRACKET_ANNOTATION_RE = re.compile(r"\[(.+?)\]")
IMAGE_FILE_RE = re.compile(r"([A-Za-z0-9._/\-]+\.(?:png|jpg|jpeg|webp))", re.IGNORECASE)
PARTIAL_COVERAGE_RE = re.compile(r"PARTIAL-COVERAGE", re.IGNORECASE)
EXPLICIT_PARTIAL_ACCEPTANCE_RE = re.compile(
    r"(admin(?: |-)?approved|admin approval|accepted debt|accepted exception|explicit(?:ly)? accepted|descope decision)",
    re.IGNORECASE,
)
INLINE_TICKETS_RE = re.compile(r"^\*\*Tickets:\*\*\s*(.*)$")
KNOWN_PATH_PREFIXES = (
    "clients/",
    "vault/",
    "deliverables/",
    "artifacts/",
    "proof-packs/",
    "review-pack/",
    "docs/",
    "workspaces/",
    "snapshots/",
)
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}
MAX_SCREENSHOT_SEARCH_DEPTH = 2
TOKEN_STOPWORDS = {
    "a",
    "after",
    "all",
    "an",
    "and",
    "at",
    "before",
    "beyond",
    "by",
    "check",
    "closed",
    "complete",
    "completed",
    "criteria",
    "criterion",
    "evidence",
    "exit",
    "for",
    "full",
    "gate",
    "goal",
    "ground",
    "grounds",
    "if",
    "in",
    "is",
    "it",
    "its",
    "loc",
    "log",
    "of",
    "on",
    "one",
    "pack",
    "phase",
    "proof",
    "proven",
    "project",
    "ref",
    "result",
    "results",
    "the",
    "ticket",
    "tickets",
    "to",
    "under",
    "validation",
    "verified",
    "with",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-file", help="Optional project markdown path for brief resolution.")
    parser.add_argument("--project-plan", required=True, help="Project plan markdown path.")
    parser.add_argument("--phase", required=True, type=int, help="Phase number to validate.")
    parser.add_argument("--tickets-dir", required=True, help="Tickets directory for the project.")
    parser.add_argument("--artifacts-root", help="Ticket artifacts root. Defaults to {deliverables_root}/artifacts when available.")
    parser.add_argument("--deliverables-root", help="Deliverables root for artifact discovery.")
    parser.add_argument("--search-root", action="append", default=[], help="Optional search root(s) for required screenshots. Defaults to the client root.")
    parser.add_argument("--brief", action="append", default=[], help="Creative brief or contract path(s) to scan for required screenshot filenames.")
    parser.add_argument("--evidence-doc", action="append", default=[], help="Evidence docs that must be fresh and cite required screenshot filenames.")
    parser.add_argument("--json-out", required=True, help="Where to write the JSON report.")
    parser.add_argument("--markdown-out", required=True, help="Where to write the markdown report.")
    return parser.parse_args()


def now() -> str:
    return datetime.now().astimezone().strftime(TIMESTAMP_FMT)


def parse_timestamp(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    match = re.match(r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2})?)", text)
    if not match:
        return None
    try:
        return datetime.fromisoformat(match.group(1))
    except ValueError:
        return None


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


def normalize_status(value: object) -> str:
    text = str(value or "").strip().lower()
    if text == "complete":
        return "closed"
    return text


def frontmatter_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip().strip("\"'") for item in value if str(item).strip()]
    text = str(value or "").strip()
    if not text:
        return []
    if text.startswith("[") and text.endswith("]"):
        return [item.strip().strip("\"'") for item in text.strip("[]").split(",") if item.strip()]
    return [text.strip("\"'")]


def frontmatter_int(value: object) -> int | None:
    text = str(value or "").strip().strip("\"'")
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        return None


def infer_project_slug(project_file: str | None, plan_path: Path) -> str:
    if project_file:
        project_path = Path(project_file).expanduser().resolve()
        if project_path.exists():
            data = parse_frontmatter_map(project_path)
            return str(data.get("project") or project_path.stem).strip().strip("\"'")
        return project_path.stem
    data = parse_frontmatter_map(plan_path)
    return str(data.get("project") or plan_path.stem).strip().strip("\"'")


def find_latest_gate_review_path(snapshots_dir: Path, project_slug: str, phase_number: int) -> Path | None:
    pattern = f"*-phase-{phase_number}-gate-{project_slug}.md"
    candidates = [
        path.resolve()
        for path in snapshots_dir.glob(pattern)
        if "packet" not in path.stem.lower() and "audit" not in path.stem.lower()
    ]
    if not candidates:
        return None
    return sorted(candidates, key=lambda path: path.name)[-1]


def resolve_remediation_for_path(
    value: object,
    *,
    snapshots_dir: Path,
    client_root: Path,
    repo_root: Path,
) -> Path | None:
    text = str(value or "").strip().strip("\"'")
    if not text:
        return None
    candidate = Path(text).expanduser()
    candidates: list[Path] = []
    if candidate.is_absolute():
        candidates.append(candidate)
    else:
        candidates.extend(
            [
                snapshots_dir / candidate,
                client_root / candidate,
                repo_root / candidate,
                repo_root / "vault" / candidate,
            ]
        )
    for path in candidates:
        resolved = path.resolve()
        if resolved.exists():
            return resolved
    return None


def find_gate_packet_artifacts(snapshots_dir: Path, project_slug: str, phase_number: int) -> list[Path]:
    patterns = (
        f"*-phase-{phase_number}-gate-packet-{project_slug}.yaml",
        f"*-phase-{phase_number}-gate-packet-{project_slug}.yml",
    )
    artifacts: list[Path] = []
    for pattern in patterns:
        artifacts.extend(path.resolve() for path in snapshots_dir.glob(pattern) if path.is_file())
    return sorted(set(artifacts), key=lambda path: path.name)


def has_gate_packet_rebuild_purpose(ticket_data: dict[str, object]) -> bool:
    task_type = str(ticket_data.get("task_type", "")).strip().lower()
    title = str(ticket_data.get("title", "")).strip().lower()
    tag_text = " ".join(tag.lower() for tag in frontmatter_list(ticket_data.get("tags", [])))
    title_shape = "gate packet" in title and "audit" in title and ("regeneration" in title or "rebuild" in title)
    return task_type == "gate_remediation" and "gate-packet-rebuild" in tag_text and title_shape


def gate_packet_regeneration_decision(
    ticket_id: str,
    ticket_data: dict[str, object],
    *,
    current_project: str,
    current_phase: int,
    expected_remediation_for: Path | None,
    snapshots_dir: Path,
    client_root: Path,
    repo_root: Path,
) -> dict[str, object]:
    ticket_status = normalize_status(ticket_data.get("status", ""))
    remediation_path = resolve_remediation_for_path(
        ticket_data.get("remediation_for", ""),
        snapshots_dir=snapshots_dir,
        client_root=client_root,
        repo_root=repo_root,
    )
    gate_packet_artifacts = find_gate_packet_artifacts(snapshots_dir, current_project, current_phase)
    blocked_by = frontmatter_list(ticket_data.get("blocked_by", []))
    checks = {
        "task_type": str(ticket_data.get("task_type", "")).strip().lower() == "gate_remediation",
        "project": str(ticket_data.get("project", "")).strip().strip("\"'") == current_project,
        "phase": frontmatter_int(ticket_data.get("phase")) == current_phase,
        "remediation_for_present": remediation_path is not None,
        "remediation_for_matches_expected": bool(
            remediation_path
            and expected_remediation_for
            and remediation_path.resolve() == expected_remediation_for.resolve()
        ),
        "purpose": has_gate_packet_rebuild_purpose(ticket_data),
        "owner_gate_packet_artifact_exists": bool(gate_packet_artifacts),
        "dependencies_cleared": not blocked_by,
    }
    strict_match = all(checks.values())
    control_plane_match = bool(
        checks["task_type"]
        and checks["project"]
        and checks["phase"]
        and checks["purpose"]
    )
    if control_plane_match:
        latest_policy = "excluded_gate_control_activity"
    else:
        latest_policy = "included_not_strict_regeneration_ticket"
    return {
        "ticket_id": ticket_id,
        "status": ticket_status,
        "strict_match": strict_match,
        "control_plane_match": control_plane_match,
        "exempted_from_open_tickets": bool(control_plane_match and ticket_status != "closed"),
        "excluded_from_latest_activity": control_plane_match,
        "latest_ticket_activity_policy": latest_policy,
        "checks": checks,
        "remediation_for": str(ticket_data.get("remediation_for", "")).strip().strip("\"'"),
        "resolved_remediation_for": str(remediation_path) if remediation_path else "",
        "expected_remediation_for": str(expected_remediation_for) if expected_remediation_for else "",
        "owner_gate_packet_artifacts": [str(path) for path in gate_packet_artifacts],
        "blocked_by": blocked_by,
    }


def is_gate_packet_regeneration_ticket(
    ticket_data: dict[str, object],
    *,
    current_project: str,
    current_phase: int,
    expected_remediation_for: Path | None,
    snapshots_dir: Path,
    client_root: Path,
    repo_root: Path,
) -> bool:
    decision = gate_packet_regeneration_decision(
        str(ticket_data.get("id", "")),
        ticket_data,
        current_project=current_project,
        current_phase=current_phase,
        expected_remediation_for=expected_remediation_for,
        snapshots_dir=snapshots_dir,
        client_root=client_root,
        repo_root=repo_root,
    )
    return bool(decision["control_plane_match"])


def strip_bracket_annotations(text: str) -> str:
    return normalize_whitespace(BRACKET_ANNOTATION_RE.sub("", text))


def tokenize(text: str) -> set[str]:
    normalized = text.lower()
    replacements = {
        "compile_commands.json": "compile_commands compile commands json",
        "compile-commands": "compile_commands compile commands",
        "c/c++": "cpp c",
        "c++": "cpp",
        "full-pipeline": "full pipeline",
        "dead-code": "dead code",
        "end-to-end": "end to end",
        "5m+": "5m",
        "2m+": "2m",
        "1m+": "1m",
    }
    for source, target in replacements.items():
        normalized = normalized.replace(source, target)
    tokens = set(re.findall(r"[a-z0-9_]+", normalized))
    return {token for token in tokens if token not in TOKEN_STOPWORDS and len(token) > 1}


def parse_exit_criterion(raw_text: str, index: int) -> dict:
    traces: list[str] = []
    partial_coverage_note = ""
    for annotation in BRACKET_ANNOTATION_RE.findall(raw_text):
        upper = annotation.upper()
        if upper.startswith("TRACES:"):
            trace_values = annotation.split(":", 1)[1] if ":" in annotation else ""
            traces.extend(part.strip() for part in trace_values.split(",") if part.strip())
        elif upper.startswith("PARTIAL-COVERAGE"):
            partial_coverage_note = annotation.split(":", 1)[1].strip() if ":" in annotation else annotation.strip()
    text = strip_bracket_annotations(raw_text)
    return {
        "index": index,
        "raw_text": raw_text,
        "text": text,
        "tokens": sorted(tokenize(text)),
        "traces": traces,
        "allows_partial_coverage": bool(partial_coverage_note),
        "partial_coverage_note": partial_coverage_note,
    }


def parse_plan_phase(plan_path: Path, phase_number: int) -> dict | None:
    lines = plan_path.read_text(encoding="utf-8").splitlines()
    current_phase: int | None = None
    current_title = ""
    phase_lines: list[str] = []
    for line in lines:
        match = PHASE_HEADER_RE.match(line.strip())
        if match:
            if current_phase == phase_number:
                break
            current_phase = int(match.group(1))
            current_title = match.group(2).strip()
            phase_lines = []
            continue
        if current_phase == phase_number:
            phase_lines.append(line)
    if current_phase != phase_number:
        return None

    ticket_ids: list[str] = []
    in_ticket_block = False
    in_exit_criteria = False
    exit_criteria: list[dict] = []
    runtime_verification = ""
    for raw_line in phase_lines:
        stripped = raw_line.strip()
        ticket_line_match = INLINE_TICKETS_RE.match(stripped)
        if ticket_line_match:
            inline_tickets = ticket_line_match.group(1).strip()
            if inline_tickets:
                for match in TICKET_ID_RE.finditer(inline_tickets):
                    ticket_id = match.group(0).upper()
                    if ticket_id not in ticket_ids:
                        ticket_ids.append(ticket_id)
                in_ticket_block = False
            else:
                in_ticket_block = True
            in_exit_criteria = False
            continue
        if stripped == "**Exit criteria:**":
            in_exit_criteria = True
            in_ticket_block = False
            continue
        if stripped.startswith("**Runtime verification:**"):
            runtime_verification = normalize_whitespace(stripped.split("**Runtime verification:**", 1)[1])
            in_exit_criteria = False
            in_ticket_block = False
            continue
        if stripped.startswith("**") and stripped not in {"**Exit criteria:**", "**Tickets:**"}:
            in_exit_criteria = False
            if in_ticket_block:
                break
        if in_exit_criteria:
            if stripped.startswith("-"):
                exit_criteria.append(parse_exit_criterion(stripped[1:].strip(), len(exit_criteria) + 1))
            continue
        if stripped == "**Tickets:**":
            in_ticket_block = True
            continue
        if in_ticket_block and stripped.startswith("**") and stripped != "**Tickets:**":
            break
        if in_ticket_block and stripped.startswith("-"):
            match = TICKET_ID_RE.search(stripped)
            if match:
                ticket_ids.append(match.group(0).upper())

    # Also extract ticket IDs from the Dynamic Wave Log table rows whose Anchor
    # Phase matches this phase, and from numbered list items in the plan's
    # ticket decomposition sections. This supplements inline/explicit ticket
    # blocks because some plans only list a subset of phase tickets there.
    all_lines = plan_path.read_text(encoding="utf-8").splitlines()
    phase_str = f"Phase {phase_number}"
    in_dwl = False
    for raw_line in all_lines:
        stripped = raw_line.strip()
        # Detect Dynamic Wave Log table rows
        if stripped.startswith("| Wave") and "Status" in stripped and "Anchor Phase" in stripped:
            in_dwl = True
            continue
        if in_dwl and stripped.startswith("|---"):
            continue
        if in_dwl and stripped.startswith("|"):
            cols = [c.strip() for c in stripped.split("|")]
            # cols[0] is empty (before first |), cols[1]=Wave, cols[2]=Status, cols[3]=Anchor Phase
            if len(cols) > 3 and phase_str in cols[3]:
                for tid_match in TICKET_ID_RE.finditer(stripped):
                    tid = tid_match.group(0).upper()
                    if tid not in ticket_ids:
                        ticket_ids.append(tid)
        elif in_dwl and not stripped.startswith("|"):
            in_dwl = False
        # Also check numbered list items (e.g., "1. T-486: ...")
        if re.match(r"^\d+\.\s+T-\d+", stripped):
            for tid_match in TICKET_ID_RE.finditer(stripped):
                tid = tid_match.group(0).upper()
                if tid not in ticket_ids:
                    ticket_ids.append(tid)

    return {
        "phase": phase_number,
        "title": current_title,
        "tickets": ticket_ids,
        "exit_criteria": exit_criteria,
        "runtime_verification": runtime_verification,
        "body": "\n".join(phase_lines),
    }


def index_ticket_files(tickets_dir: Path) -> dict[str, Path]:
    index: dict[str, Path] = {}
    for path in tickets_dir.rglob("*.md"):
        ticket_id: str | None = None
        frontmatter = parse_frontmatter_map(path)
        explicit = str(frontmatter.get("id", "")).strip().upper()
        if explicit:
            ticket_id = explicit
        else:
            match = TICKET_ID_RE.search(path.stem.upper())
            if match:
                ticket_id = match.group(0).upper()
        if ticket_id:
            index[ticket_id] = path.resolve()
    return index


def find_required_screenshots(brief_paths: list[Path]) -> list[str]:
    required: set[str] = set()
    for path in brief_paths:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for match in SCREENSHOT_RE.finditer(text):
            required.add(match.group(1))
    return sorted(required)


SKIP_DIR_NAMES = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    "dist",
    "build",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "shards",
    "store",
    "workspaces",
    "repos",
    ".refactor-platform",
}


def build_file_index(search_roots: list[Path]) -> dict[str, list[str]]:
    index: dict[str, list[str]] = {}
    for root in search_roots:
        if not root.exists():
            continue
        stack = [root]
        while stack:
            current = stack.pop()
            try:
                children = list(current.iterdir())
            except OSError:
                continue
            for child in children:
                if child.is_dir():
                    if child.name in SKIP_DIR_NAMES:
                        continue
                    stack.append(child)
                    continue
                resolved = str(child.resolve())
                index.setdefault(child.name, []).append(resolved)
                rel = child.relative_to(root).as_posix()
                index.setdefault(rel, []).append(resolved)
    return index


def resolve_required_files(required_names: list[str], file_index: dict[str, list[str]]) -> tuple[list[str], dict[str, list[str]]]:
    missing: list[str] = []
    found: dict[str, list[str]] = {}
    for name in required_names:
        basename = Path(name).name
        matches = file_index.get(name, []) + file_index.get(basename, [])
        unique_matches = sorted(set(matches))
        if unique_matches:
            found[name] = unique_matches
        else:
            missing.append(name)
    return missing, found


def extract_doc_timestamp(path: Path) -> datetime:
    frontmatter = parse_frontmatter_map(path)
    candidates = [parse_timestamp(frontmatter.get(key)) for key in FRONTMATTER_TS_KEYS]
    candidates = [candidate for candidate in candidates if candidate is not None]
    if candidates:
        return max(candidates)
    return datetime.fromtimestamp(path.stat().st_mtime)


def merge_brief_paths(resolved_entries: list[dict], explicit_paths: list[Path]) -> list[Path]:
    merged: list[Path] = []
    seen: set[str] = set()

    def add(path: Path) -> None:
        resolved = path.expanduser().resolve()
        key = str(resolved)
        if key in seen:
            return
        seen.add(key)
        merged.append(resolved)

    for entry in resolved_entries:
        path_text = str(entry.get("path", "")).strip()
        if path_text:
            add(Path(path_text))
    for path in explicit_paths:
        add(path)
    return merged


def split_frontmatter(text: str) -> tuple[str, str]:
    if not text.startswith("---\n"):
        return "", text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return "", text
    return parts[1].strip("\n"), parts[2]


def extract_partial_coverage_flags(text: str) -> list[dict]:
    flags: list[dict] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        if PARTIAL_COVERAGE_RE.search(line) and re.search(r"\b(closed|closeout|conditionally)\b", line, re.IGNORECASE):
            flags.append({"line_number": line_number, "line": line.strip()})
    return flags


def resolve_path_reference(
    candidate: str,
    *,
    client_root: Path,
    deliverables_root: Path | None,
    repo_root: Path,
    search_roots: Iterable[Path] | None = None,
) -> Path | None:
    cleaned = candidate.strip().strip("`").strip().rstrip(".,:;)]}")
    cleaned = cleaned.rstrip("/")
    if not cleaned:
        return None
    candidate_roots: list[Path]
    if cleaned.startswith("/"):
        resolved = Path(cleaned).expanduser().resolve()
        return resolved if resolved.exists() else None
    if cleaned.startswith("vault/"):
        candidate_roots = [repo_root]
    elif cleaned.startswith("clients/"):
        candidate_roots = [repo_root / "vault"]
    elif cleaned.startswith("deliverables/"):
        candidate_roots = [client_root]
    elif cleaned.startswith(("artifacts/", "proof-packs/", "workspaces/")):
        candidate_roots = [deliverables_root] if deliverables_root is not None else [client_root]
    elif cleaned.startswith("snapshots/"):
        candidate_roots = [client_root]
    else:
        candidate_roots = []
        if deliverables_root is not None:
            candidate_roots.append(deliverables_root)
        candidate_roots.extend([client_root, repo_root])

    for root in search_roots or []:
        root = root.expanduser()
        candidate_roots.append(root)
        candidate_roots.append(root.parent)

    for root in candidate_roots:
        resolved = (root / cleaned).expanduser().resolve()
        if resolved.exists():
            return resolved
    return None


def extract_referenced_paths(
    text: str,
    *,
    client_root: Path,
    deliverables_root: Path | None,
    repo_root: Path,
    search_roots: Iterable[Path] | None = None,
) -> list[str]:
    candidates: set[str] = set()
    for block in re.findall(r"`([^`]+)`", text):
        if "\n" in block or len(block) > 260:
            continue
        candidates.add(block)
    for prefix in KNOWN_PATH_PREFIXES:
        pattern = re.compile(rf"({re.escape(prefix)}[A-Za-z0-9._/\-]+)")
        for match in pattern.finditer(text):
            candidate = match.group(1)
            if "\n" in candidate or len(candidate) > 260:
                continue
            candidates.add(candidate)

    resolved: set[str] = set()
    for candidate in candidates:
        path = resolve_path_reference(
            candidate,
            client_root=client_root,
            deliverables_root=deliverables_root,
            repo_root=repo_root,
            search_roots=search_roots,
        )
        if path is not None:
            resolved.add(str(path))
    return sorted(resolved)


def score_ticket_relevance(criterion: dict, ticket_context: dict) -> int:
    criterion_text = criterion["text"].lower()
    ticket_text = ticket_context["search_text"]
    criterion_tokens = set(criterion["tokens"])
    ticket_tokens = ticket_context["tokens"]
    title_tokens = ticket_context.get("title_tokens", set())
    task_type = str(ticket_context.get("task_type", "")).strip().lower()

    for language in ("java", "python", "typescript"):
        if f"{language} proving ground" in criterion_text and "full pipeline" in criterion_text and language not in title_tokens:
            return 0

    discriminator_groups = (
        {"java", "python", "typescript", "llvm", "go", "cpp"},
        {"compile_commands"},
    )
    for group in discriminator_groups:
        required = criterion_tokens & group
        if required and not (ticket_tokens & required):
            return 0

    score = len(criterion_tokens & ticket_tokens)

    phrase_pairs = (
        ("full pipeline", 4),
        ("proving ground", 4),
        ("dead code", 5),
        ("dependency decoupling", 5),
        ("docker parity", 5),
        ("compile_commands", 5),
        ("throughput", 4),
        ("analysis", 3),
        ("llvm", 4),
        ("typescript", 4),
        ("python", 4),
        ("java", 4),
        ("benchmark", 3),
    )
    for phrase, bonus in phrase_pairs:
        if phrase in criterion_text and phrase in ticket_text:
            score += bonus

    if "dependency decoupling" in criterion_text and "extract interface" in ticket_text:
        score += 4
    if "autonomous refactor" in criterion_text and ("dead code" in ticket_text or "dependency decoupling" in ticket_text):
        score += 4
    if "docker" in criterion_text and "docker" in ticket_text:
        score += 2
    if "parity" in criterion_text and "parity" in ticket_text:
        score += 2

    quality_lane = (
        task_type in {"quality_check", "artifact_polish_review", "artifact_cleanup"}
        or "qc" in title_tokens
        or "quality_check" in ticket_text
        or "artifact_polish_review" in ticket_text
        or "artifact polish" in ticket_text
        or "evidence capture" in ticket_text
    )
    if quality_lane:
        if any(token in criterion_text for token in ("screenshot", "visual", "evidence", "proof")):
            score += 3
        if any(token in criterion_text for token in ("walkthrough", "video", "recording", "demo")):
            score += 3
        if any(token in criterion_text for token in ("review pack", "artifact polish", "paperwork", "readiness", "runtime verification")):
            score += 3
    return score


def match_tickets_to_criterion(criterion: dict, ticket_contexts: dict[str, dict]) -> list[dict]:
    scored: list[tuple[int, dict]] = []
    for ticket_context in ticket_contexts.values():
        score = score_ticket_relevance(criterion, ticket_context)
        if score > 0:
            scored.append((score, ticket_context))
    if not scored:
        if len(ticket_contexts) == 1:
            return list(ticket_contexts.values())
        return []
    top_score = max(score for score, _ in scored)
    threshold = max(3, top_score - 2)
    matches = [context for score, context in scored if score >= threshold]
    return sorted(matches, key=lambda item: item["ticket_id"])


def find_ticket_evidence_artifacts(ticket_id: str, search_roots: Iterable[Path]) -> list[str]:
    patterns = (ticket_id.lower(), ticket_id.lower().replace("-", ""))
    matches: set[str] = set()
    for root in search_roots:
        if not root.exists():
            continue
        try:
            children = list(root.iterdir())
        except OSError:
            continue
        for path in children:
            rel = path.name.lower()
            if any(pattern in rel for pattern in patterns):
                matches.add(str(path.resolve()))
    return sorted(matches)


def is_benchmark_criterion(text: str) -> bool:
    lower = text.lower()
    return any(
        phrase in lower
        for phrase in (
            "throughput",
            "analysis completes",
            "plan generation",
            "end-to-end cycle",
            "docker validation overhead",
            "docker validation parity",
        )
    )


def benchmark_selector(criterion_text: str) -> str | None:
    lower = criterion_text.lower()
    if "throughput" in lower:
        return "throughput"
    if "analysis" in lower and "120" in lower:
        return "analysis"
    if "plan generation" in lower:
        return "plan generation"
    if "end-to-end cycle" in lower or "end to end cycle" in lower:
        return "end-to-end cycle"
    if "docker" in lower and "overhead" in lower:
        return "docker validation overhead"
    if "docker" in lower and "parity" in lower:
        return "docker validation parity"
    return None


def find_matching_benchmark_result(criterion_text: str, artifact_paths: list[str]) -> tuple[dict | None, str | None]:
    selector = benchmark_selector(criterion_text)
    if selector is None:
        return None, None
    for path_text in artifact_paths:
        path = Path(path_text)
        if path.name != "benchmark-measurements.json":
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        for entry in payload.get("criteria", []):
            criterion_label = str(entry.get("criterion", "")).lower()
            if selector in criterion_label:
                return entry, str(path.resolve())
    return None, None


def summarize_path(path_text: str) -> str:
    path = Path(path_text)
    if path.is_absolute():
        return path_text
    parts = path.parts
    if len(parts) >= 3:
        return "/".join(parts[-3:])
    return path.name or path_text


def requires_dashboard_screenshot(phase: dict, brief_paths: list[Path]) -> bool:
    # Only check the phase's own runtime verification text and phase-scoped briefs
    # (not the project-level brief, which may reference dashboard screenshots for
    # future phases where the dashboard is actually built).
    texts = [phase.get("runtime_verification", ""), phase.get("body", "")]
    for path in brief_paths:
        if path.exists():
            name = path.name.lower()
            # Only include phase-scoped briefs (contain "phase" in filename),
            # not project-level briefs which describe the full project scope.
            if "phase" in name:
                texts.append(path.read_text(encoding="utf-8"))
    combined = "\n".join(texts).lower()
    return "dashboard screenshot" in combined or ("dashboard" in combined and "screenshot" in combined and "proving-ground" in combined)


def collect_dashboard_screenshot_refs(text: str) -> list[str]:
    refs: set[str] = set()
    for line in text.splitlines():
        if "dashboard" not in line.lower():
            continue
        for match in IMAGE_FILE_RE.finditer(line):
            refs.add(match.group(1))
    return sorted(refs)


def find_dashboard_screenshot_files(search_roots: list[Path]) -> list[str]:
    matches: set[str] = set()
    for root in search_roots:
        if not root.exists():
            continue
        stack: list[tuple[Path, int]] = [(root, 0)]
        while stack:
            current, depth = stack.pop()
            try:
                children = list(current.iterdir())
            except OSError:
                continue
            for child in children:
                if child.is_dir():
                    if child.name in SKIP_DIR_NAMES or depth >= MAX_SCREENSHOT_SEARCH_DEPTH:
                        continue
                    stack.append((child, depth + 1))
                    continue
                if child.suffix.lower() in IMAGE_SUFFIXES and "dashboard" in child.name.lower():
                    matches.add(str(child.resolve()))
    return sorted(matches)


def evaluate_exit_criteria(
    phase: dict,
    ticket_contexts: dict[str, dict],
    artifact_search_roots: list[Path],
) -> tuple[list[dict], list[dict]]:
    cache: dict[str, list[str]] = {}
    warnings: list[dict] = []
    evaluations: list[dict] = []

    for ticket_context in ticket_contexts.values():
        if ticket_context["status"] != "closed":
            continue
        for flag in ticket_context["partial_coverage_flags"]:
            warnings.append(
                {
                    "category": "partial-coverage",
                    "ticket_id": ticket_context["ticket_id"],
                    "details": (
                        f"{ticket_context['ticket_id']} includes [PARTIAL-COVERAGE] at "
                        f"line {flag['line_number']}: {flag['line']}"
                    ),
                }
            )

    for criterion in phase.get("exit_criteria", []):
        matched_tickets = match_tickets_to_criterion(criterion, ticket_contexts)
        matched_ticket_ids = [ticket["ticket_id"] for ticket in matched_tickets]
        evidence_paths: set[str] = set()
        for ticket in matched_tickets:
            if ticket["ticket_id"] not in cache:
                cache[ticket["ticket_id"]] = sorted(
                    set(ticket["referenced_paths"]) | set(find_ticket_evidence_artifacts(ticket["ticket_id"], artifact_search_roots))
                )
            evidence_paths.update(cache[ticket["ticket_id"]])

        partial_tickets = [ticket for ticket in matched_tickets if ticket["partial_coverage_flags"]]
        benchmark_entry, benchmark_path = find_matching_benchmark_result(criterion["text"], sorted(evidence_paths))
        if benchmark_path:
            evidence_paths.add(benchmark_path)

        verdict = "PASS"
        details = "Evidence artifacts located and no partial-coverage flags detected on matched tickets."
        if not matched_tickets:
            verdict = "FAIL"
            details = "No relevant phase ticket matched this exit criterion."
        elif any(ticket["status"] != "closed" for ticket in matched_tickets):
            verdict = "FAIL"
            open_ids = ", ".join(ticket["ticket_id"] for ticket in matched_tickets if ticket["status"] != "closed")
            details = f"Matched ticket(s) are not closed: {open_ids}."
        elif not evidence_paths:
            verdict = "FAIL"
            details = "Matched ticket(s) do not cite or preserve any evidence artifact paths."
        elif benchmark_entry is not None:
            benchmark_verdict = str(benchmark_entry.get("verdict", "")).lower()
            details = str(benchmark_entry.get("reason", "")).strip() or "Benchmark artifact evaluated this criterion."
            verdict = "PASS" if benchmark_verdict == "pass" else "FAIL"
        elif partial_tickets:
            accepted_partial_ids = [ticket["ticket_id"] for ticket in partial_tickets if ticket["explicit_partial_acceptance"]]
            if criterion["allows_partial_coverage"] and len(accepted_partial_ids) == len(partial_tickets):
                verdict = "ACCEPTED PARTIAL"
                details = (
                    f"Matched ticket(s) use [PARTIAL-COVERAGE] with explicit acceptance: {', '.join(accepted_partial_ids)}."
                )
            elif criterion["allows_partial_coverage"]:
                verdict = "FAIL"
                details = (
                    "Matched ticket(s) use [PARTIAL-COVERAGE], but no explicit acceptance was found in the ticket evidence: "
                    f"{', '.join(ticket['ticket_id'] for ticket in partial_tickets)}."
                )
            else:
                verdict = "FAIL"
                details = (
                    "Matched ticket(s) use [PARTIAL-COVERAGE] for a criterion that does not allow partial closure: "
                    f"{', '.join(ticket['ticket_id'] for ticket in partial_tickets)}."
                )

        evaluations.append(
            {
                "index": criterion["index"],
                "criterion": criterion["text"],
                "raw_text": criterion["raw_text"],
                "verdict": verdict,
                "details": details,
                "traces": criterion["traces"],
                "allows_partial_coverage": criterion["allows_partial_coverage"],
                "partial_coverage_note": criterion["partial_coverage_note"],
                "matched_tickets": matched_ticket_ids,
                "evidence_paths": sorted(evidence_paths),
            }
        )

    return evaluations, warnings


def build_report(args: argparse.Namespace) -> dict:
    plan_path = Path(args.project_plan).expanduser().resolve()
    tickets_dir = Path(args.tickets_dir).expanduser().resolve()
    deliverables_root = Path(args.deliverables_root).expanduser().resolve() if args.deliverables_root else None
    artifacts_root = Path(args.artifacts_root).expanduser().resolve() if args.artifacts_root else None
    if artifacts_root is None and deliverables_root is not None:
        artifacts_root = (deliverables_root / "artifacts").resolve()

    phase = parse_plan_phase(plan_path, args.phase)
    if phase is None:
        return {
            "generated_at": now(),
            "project_plan": str(plan_path),
            "phase": args.phase,
            "verdict": "FAIL",
            "checks": [
                {
                    "name": "phase_present_in_plan",
                    "ok": False,
                    "details": f"Phase {args.phase} not found in {plan_path}.",
                }
            ],
            "findings": [],
        }

    client_root = plan_path.parent.parent
    repo_root = SCRIPT_DIR.parent
    snapshots_dir = client_root / "snapshots"
    project_slug = infer_project_slug(args.project_file, plan_path)
    expected_regeneration_remediation = find_latest_gate_review_path(snapshots_dir, project_slug, args.phase)
    ticket_index = index_ticket_files(tickets_dir)
    resolved_tickets: list[dict] = []
    missing_tickets: list[str] = []
    ticket_reports: list[dict] = []
    latest_ticket_activity: datetime | None = None
    open_tickets: list[str] = []
    gate_packet_regeneration_decisions: list[dict[str, object]] = []
    contradiction_findings: list[dict] = []
    ticket_contexts: dict[str, dict] = {}

    if args.search_root:
        search_roots = [Path(path).expanduser().resolve() for path in args.search_root]
    else:
        search_roots = [client_root / "snapshots"]
        if deliverables_root is not None:
            search_roots.append(deliverables_root)

    for ticket_id in phase["tickets"]:
        ticket_path = ticket_index.get(ticket_id)
        if ticket_path is None:
            missing_tickets.append(ticket_id)
            continue
        ticket_data = parse_frontmatter_map(ticket_path)
        ticket_status = normalize_status(ticket_data.get("status", ""))
        gate_packet_regeneration = gate_packet_regeneration_decision(
            ticket_id,
            ticket_data,
            current_project=project_slug,
            current_phase=args.phase,
            expected_remediation_for=expected_regeneration_remediation,
            snapshots_dir=snapshots_dir,
            client_root=client_root,
            repo_root=repo_root,
        )
        strict_gate_control_ticket = bool(gate_packet_regeneration["strict_match"])
        control_plane_gate_ticket = bool(gate_packet_regeneration["control_plane_match"])
        open_ticket_exempted = ticket_status != "closed" and strict_gate_control_ticket
        latest_activity_excluded = control_plane_gate_ticket and (
            ticket_status == "closed" or open_ticket_exempted
        )
        gate_packet_regeneration["exempted_from_open_tickets"] = open_ticket_exempted
        gate_packet_regeneration["excluded_from_latest_activity"] = latest_activity_excluded
        if not latest_activity_excluded:
            gate_packet_regeneration["latest_ticket_activity_policy"] = "included_not_strict_regeneration_ticket"
        gate_checks = gate_packet_regeneration.get("checks", {})
        if isinstance(gate_checks, dict) and (gate_checks.get("task_type") or gate_checks.get("purpose")):
            gate_packet_regeneration_decisions.append(gate_packet_regeneration)
        ticket_text = ticket_path.read_text(encoding="utf-8")
        partial_coverage_flags = extract_partial_coverage_flags(ticket_text)
        referenced_paths = extract_referenced_paths(
            ticket_text,
            client_root=client_root,
            deliverables_root=deliverables_root,
            repo_root=repo_root,
            search_roots=search_roots,
        )
        resolved_tickets.append(
            {
                "ticket_id": ticket_id,
                "path": str(ticket_path),
                "status": ticket_status,
                "partial_coverage": ticket_status == "closed" and bool(partial_coverage_flags),
                "explicit_partial_acceptance": bool(EXPLICIT_PARTIAL_ACCEPTANCE_RE.search(ticket_text)),
            }
        )
        ticket_contexts[ticket_id] = {
            "ticket_id": ticket_id,
            "path": str(ticket_path),
            "status": ticket_status,
            "task_type": str(ticket_data.get("task_type", "")).strip().lower(),
            "title": str(ticket_data.get("title", ticket_path.stem)).strip(),
            "title_tokens": tokenize(str(ticket_data.get("title", ticket_path.stem)).strip()),
            "search_text": normalize_whitespace(
                f"{ticket_data.get('title', '')}\n{ticket_data.get('task_type', '')}\n{ticket_text}"
            ).lower(),
            "tokens": tokenize(f"{ticket_data.get('title', '')}\n{ticket_data.get('task_type', '')}\n{ticket_text}"),
            "partial_coverage_flags": partial_coverage_flags,
            "explicit_partial_acceptance": bool(EXPLICIT_PARTIAL_ACCEPTANCE_RE.search(ticket_text)),
            "referenced_paths": referenced_paths,
        }
        if ticket_status != "closed" and not open_ticket_exempted:
            open_tickets.append(ticket_id)
        if not latest_activity_excluded:
            for key in ("completed", "updated", "created"):
                ts = parse_timestamp(ticket_data.get(key))
                if ts and (latest_ticket_activity is None or ts > latest_ticket_activity):
                    latest_ticket_activity = ts
        if artifacts_root is not None:
            ticket_report = build_ticket_evidence_report(ticket_path, artifacts_root)
            ticket_reports.append(ticket_report)
            for contradiction in ticket_report.get("contradictions", []):
                contradiction_findings.append(
                    {
                        "ticket_id": ticket_id,
                        **contradiction,
                    }
                )

    evidence_docs = [Path(path).expanduser().resolve() for path in args.evidence_doc]
    explicit_brief_paths = [Path(path).expanduser().resolve() for path in args.brief]
    if explicit_brief_paths and not args.project_file:
        brief_resolution = {"ordered_briefs": []}
        brief_paths = merge_brief_paths([], explicit_brief_paths)
    else:
        brief_resolution = build_brief_resolution_report(
            argparse.Namespace(
                project=None,
                project_file=args.project_file,
                project_plan=args.project_plan,
                phase=args.phase,
                ticket_id=None,
                ticket_path=None,
                search_root=[str(path) for path in search_roots],
                json_out=None,
                markdown_out=None,
            )
        )
        brief_paths = merge_brief_paths(brief_resolution.get("ordered_briefs", []), explicit_brief_paths)
    required_screenshots = find_required_screenshots(brief_paths)
    artifact_search_roots = []
    seen_artifact_roots: set[str] = set()
    for root in [artifacts_root, deliverables_root / "proof-packs" if deliverables_root else None, *search_roots]:
        if root is None:
            continue
        resolved = root.expanduser().resolve()
        key = str(resolved)
        if key in seen_artifact_roots:
            continue
        seen_artifact_roots.add(key)
        artifact_search_roots.append(resolved)

    evidence_doc_records: list[dict] = []
    stale_docs: list[str] = []
    missing_evidence_docs: list[str] = []
    screenshot_reference_failures: list[dict] = []
    evidence_doc_texts: list[str] = []

    for path in evidence_docs:
        if not path.exists():
            missing_evidence_docs.append(str(path))
            continue
        text = path.read_text(encoding="utf-8")
        evidence_doc_texts.append(text)
        doc_timestamp = extract_doc_timestamp(path)
        referenced = sorted(name for name in required_screenshots if Path(name).name in text or name in text)
        evidence_doc_records.append(
            {
                "path": str(path),
                "timestamp": doc_timestamp.strftime(TIMESTAMP_FMT),
                "references": referenced,
            }
        )
        if latest_ticket_activity and doc_timestamp < latest_ticket_activity:
            stale_docs.append(str(path))

    if required_screenshots:
        for screenshot_name in required_screenshots:
            referenced_in = [
                record["path"]
                for record in evidence_doc_records
                if screenshot_name in record["references"] or Path(screenshot_name).name in record["references"]
            ]
            if not referenced_in:
                screenshot_reference_failures.append(
                    {
                        "screenshot": screenshot_name,
                        "details": "No supplied evidence doc references this required screenshot filename.",
                    }
                )

    dashboard_screenshot_required = requires_dashboard_screenshot(phase, brief_paths)
    dashboard_screenshot_doc_refs: set[str] = set()
    for text in evidence_doc_texts:
        dashboard_screenshot_doc_refs.update(collect_dashboard_screenshot_refs(text))
    file_index = build_file_index(search_roots) if (required_screenshots or dashboard_screenshot_doc_refs) else {}
    missing_screenshots, found_screenshots = resolve_required_files(required_screenshots, file_index) if required_screenshots else ([], {})
    if dashboard_screenshot_doc_refs:
        missing_dashboard_screenshots, found_dashboard_screenshot_map = resolve_required_files(
            sorted(dashboard_screenshot_doc_refs), file_index
        )
        found_dashboard_screenshots = sorted({path for paths in found_dashboard_screenshot_map.values() for path in paths})
    else:
        missing_dashboard_screenshots = []
        found_dashboard_screenshots = []

    exit_criteria, partial_coverage_warnings = evaluate_exit_criteria(phase, ticket_contexts, artifact_search_roots)
    failed_exit_criteria = [criterion for criterion in exit_criteria if criterion["verdict"] not in {"PASS", "ACCEPTED PARTIAL"}]

    checks = [
        {
            "name": "phase_present_in_plan",
            "ok": True,
            "details": f"Phase {args.phase} found with {len(phase['tickets'])} ticket(s).",
        },
        {
            "name": "phase_tickets_resolved",
            "ok": not missing_tickets,
            "details": "All phase tickets resolved to files." if not missing_tickets else f"Missing ticket files: {', '.join(missing_tickets)}",
        },
        {
            "name": "all_phase_tickets_closed",
            "ok": not open_tickets,
            "details": "All phase tickets are closed." if not open_tickets else f"Open/non-closed phase tickets: {', '.join(open_tickets)}",
        },
        {
            "name": "ticket_evidence_consistent",
            "ok": not contradiction_findings,
            "details": "No contradictory ticket status artifacts found."
            if not contradiction_findings
            else f"{len(contradiction_findings)} contradictory ticket artifact status finding(s).",
        },
        {
            "name": "evidence_docs_supplied",
            "ok": bool(evidence_docs),
            "details": f"{len(evidence_docs)} evidence doc(s) supplied." if evidence_docs else "No evidence docs supplied to the readiness check.",
        },
        {
            "name": "evidence_docs_exist",
            "ok": not missing_evidence_docs,
            "details": "All evidence docs exist." if not missing_evidence_docs else f"Missing evidence docs: {', '.join(missing_evidence_docs)}",
        },
        {
            "name": "evidence_docs_fresh",
            # For capability-waves plans, individual evidence docs from earlier waves
            # may legitimately predate later ticket activity. The pack is fresh if at
            # least one evidence doc is at or after the latest ticket activity.
            "ok": not stale_docs or len(stale_docs) < len(evidence_doc_records),
            "details": "Evidence docs are at or after the latest phase ticket activity."
            if not stale_docs
            else (
                f"All evidence docs are stale relative to latest phase ticket activity: {', '.join(stale_docs)}"
                if len(stale_docs) >= len(evidence_doc_records)
                else f"Evidence pack is fresh ({len(evidence_doc_records) - len(stale_docs)} recent doc(s) cover latest activity). Older docs: {', '.join(stale_docs)}"
            ),
        },
        {
            "name": "exit_criteria_parsed",
            "ok": bool(phase.get("exit_criteria")),
            "details": f"{len(phase.get('exit_criteria', []))} exit criterion/criteria parsed from the plan."
            if phase.get("exit_criteria")
            else "No exit criteria were parsed from the phase block.",
        },
        {
            "name": "exit_criteria_evidenced",
            "ok": not failed_exit_criteria,
            "details": "Every exit criterion has evidence coverage."
            if not failed_exit_criteria
            else f"{len(failed_exit_criteria)} exit criterion/criteria are missing evidence or remain open.",
        },
        {
            "name": "ticket_partial_coverage_flags",
            "ok": True,
            "details": "No phase tickets include [PARTIAL-COVERAGE]."
            if not partial_coverage_warnings
            else f"{len(partial_coverage_warnings)} [PARTIAL-COVERAGE] warning(s) detected across phase tickets.",
        },
    ]

    if required_screenshots:
        checks.extend(
            [
                {
                    "name": "required_screenshot_files_present",
                    "ok": not missing_screenshots,
                    "details": "All brief-required screenshot files exist."
                    if not missing_screenshots
                    else f"Missing required screenshot files: {', '.join(missing_screenshots)}",
                },
                {
                    "name": "required_screenshots_cited_in_evidence",
                    "ok": not screenshot_reference_failures,
                    "details": "All brief-required screenshot filenames are cited in supplied evidence docs."
                    if not screenshot_reference_failures
                    else f"{len(screenshot_reference_failures)} required screenshot(s) are uncited in supplied evidence docs.",
                },
            ]
        )
    if dashboard_screenshot_required:
        dashboard_ok = bool(found_dashboard_screenshots) and not missing_dashboard_screenshots
        checks.append(
            {
                "name": "dashboard_screenshot_files_present",
                "ok": dashboard_ok,
                "details": "Dashboard screenshot evidence files exist."
                if dashboard_ok
                else (
                    f"Dashboard screenshot filenames were cited but missing on disk: {', '.join(missing_dashboard_screenshots)}"
                    if missing_dashboard_screenshots
                    else "No supplied evidence doc references a dashboard screenshot filename."
                ),
            }
        )

    warnings: list[dict] = list(partial_coverage_warnings)
    findings: list[dict] = []
    for missing_ticket in missing_tickets:
        findings.append({"severity": "HIGH", "category": "requirements-compliance", "details": f"Missing ticket file for {missing_ticket}."})
    for open_ticket in open_tickets:
        findings.append({"severity": "HIGH", "category": "requirements-compliance", "details": f"{open_ticket} is not closed yet."})
    for contradiction in contradiction_findings:
        findings.append(
            {
                "severity": "HIGH",
                "category": "verification-evidence",
                "details": (
                    f"{contradiction['ticket_id']} is `{contradiction['ticket_status']}` but "
                    f"`{Path(contradiction['path']).name}` proposes `{contradiction['artifact_status']}` "
                    f"via {contradiction['source']} ({contradiction['snippet']})."
                ),
            }
        )
    for doc in missing_evidence_docs:
        findings.append({"severity": "HIGH", "category": "verification-evidence", "details": f"Missing evidence doc: {doc}."})
    stale_severity = "HIGH" if len(stale_docs) >= len(evidence_doc_records) else "LOW"
    for doc in stale_docs:
        findings.append({"severity": stale_severity, "category": "verification-evidence", "details": f"Stale evidence doc: {doc} predates latest phase ticket activity."})
    for screenshot_name in missing_screenshots:
        findings.append({"severity": "HIGH", "category": "verification-evidence", "details": f"Missing brief-required screenshot file: {screenshot_name}."})
    for failure in screenshot_reference_failures:
        findings.append({"severity": "HIGH", "category": "verification-evidence", "details": f"Required screenshot not cited in evidence docs: {failure['screenshot']}."})
    if dashboard_screenshot_required and (not found_dashboard_screenshots or missing_dashboard_screenshots):
        details = (
            f"Dashboard screenshot filenames were cited but missing on disk: {', '.join(missing_dashboard_screenshots)}."
            if missing_dashboard_screenshots
            else "Runtime verification requires dashboard screenshot evidence, but no supplied evidence doc cites a dashboard screenshot filename."
        )
        findings.append({"severity": "HIGH", "category": "verification-evidence", "details": details})
    for criterion in failed_exit_criteria:
        findings.append(
            {
                "severity": "HIGH",
                "category": "requirements-compliance",
                "details": f"Exit criterion {criterion['index']} failed: {criterion['criterion']} — {criterion['details']}",
            }
        )
    if not evidence_docs:
        findings.append({"severity": "HIGH", "category": "verification-evidence", "details": "No evidence docs were supplied to the readiness checker."})

    verdict = "PASS" if all(check["ok"] for check in checks) else "FAIL"
    return {
        "generated_at": now(),
        "project_plan": str(plan_path),
        "phase": phase["phase"],
        "phase_title": phase["title"],
        "tickets_dir": str(tickets_dir),
        "artifacts_root": str(artifacts_root) if artifacts_root else "",
        "deliverables_root": str(deliverables_root) if deliverables_root else "",
        "latest_phase_ticket_activity": latest_ticket_activity.strftime(TIMESTAMP_FMT) if latest_ticket_activity else "",
        "brief_paths": [str(path) for path in brief_paths],
        "brief_resolution": brief_resolution,
        "runtime_verification": phase.get("runtime_verification", ""),
        "exit_criteria": exit_criteria,
        "required_screenshots": required_screenshots,
        "found_screenshots": found_screenshots,
        "dashboard_screenshot_required": dashboard_screenshot_required,
        "dashboard_screenshot_refs": sorted(dashboard_screenshot_doc_refs),
        "found_dashboard_screenshots": found_dashboard_screenshots,
        "phase_tickets": resolved_tickets,
        "project_slug": project_slug,
        "expected_gate_regeneration_remediation_for": str(expected_regeneration_remediation) if expected_regeneration_remediation else "",
        "gate_packet_regeneration_decisions": gate_packet_regeneration_decisions,
        "ticket_evidence_reports": ticket_reports,
        "evidence_docs": evidence_doc_records,
        "checks": checks,
        "warnings": warnings,
        "findings": findings,
        "verdict": verdict,
    }


def render_markdown(report: dict) -> str:
    lines = [
        "# Phase Readiness Check",
        "",
        f"**Generated:** {report['generated_at']}",
        f"**Phase:** {report['phase']} — {report.get('phase_title', '')}",
        f"**Project plan:** `{report['project_plan']}`",
        f"**Verdict:** {report['verdict']}",
        "",
        "## Checks",
        "",
    ]
    for check in report.get("checks", []):
        icon = "PASS" if check["ok"] else "FAIL"
        lines.append(f"- **{check['name']}**: {icon} — {check['details']}")

    lines.extend(["", "## Warnings", ""])
    if report.get("warnings"):
        for warning in report["warnings"]:
            lines.append(f"- **[{warning['category']}]** {warning['details']}")
    else:
        lines.append("- None.")

    if report.get("exit_criteria"):
        lines.extend(
            [
                "",
                "## Exit Criteria Verdicts",
                "",
                "| # | Verdict | Criterion | Tickets | Evidence |",
                "| --- | --- | --- | --- | --- |",
            ]
        )
        for criterion in report["exit_criteria"]:
            tickets = ", ".join(criterion.get("matched_tickets", [])) or "none"
            evidence = ", ".join(summarize_path(path) for path in criterion.get("evidence_paths", [])[:3]) or "none"
            lines.append(
                f"| {criterion['index']} | {criterion['verdict']} | {criterion['criterion']} | {tickets} | {evidence} |"
            )

    lines.extend(["", "## Findings", ""])
    if report.get("findings"):
        for finding in report["findings"]:
            lines.append(f"- **[{finding['severity']}] [{finding['category']}]** {finding['details']}")
    else:
        lines.append("- None.")

    lines.extend(["", "## Phase Tickets", ""])
    for ticket in report.get("phase_tickets", []):
        partial = " [PARTIAL-COVERAGE]" if ticket.get("partial_coverage") else ""
        lines.append(f"- `{ticket['ticket_id']}` — `{ticket['status']}`{partial} — `{ticket['path']}`")

    if report.get("gate_packet_regeneration_decisions"):
        lines.extend(["", "## Gate Packet Regeneration Decisions", ""])
        for decision in report["gate_packet_regeneration_decisions"]:
            exempted = "yes" if decision.get("exempted_from_open_tickets") else "no"
            lines.append(
                f"- `{decision['ticket_id']}` — status `{decision['status']}`, "
                f"open-ticket exemption: {exempted}, latest activity: `{decision['latest_ticket_activity_policy']}`"
            )

    if report.get("brief_paths"):
        lines.extend(["", "## Brief Stack", ""])
        for path in report["brief_paths"]:
            lines.append(f"- `{path}`")

    if report.get("required_screenshots"):
        lines.extend(["", "## Required Screenshots", ""])
        for name in report["required_screenshots"]:
            matches = report.get("found_screenshots", {}).get(name, [])
            if matches:
                lines.append(f"- `{name}`")
                for match in matches:
                    lines.append(f"  - `{match}`")
            else:
                lines.append(f"- `{name}` — MISSING")

    if report.get("dashboard_screenshot_required"):
        lines.extend(["", "## Dashboard Screenshots", ""])
        if report.get("found_dashboard_screenshots"):
            for path in report["found_dashboard_screenshots"]:
                lines.append(f"- `{path}`")
        else:
            lines.append("- MISSING")

    if report.get("evidence_docs"):
        lines.extend(["", "## Evidence Docs", ""])
        for doc in report["evidence_docs"]:
            refs = ", ".join(doc["references"]) if doc["references"] else "none"
            lines.append(f"- `{doc['path']}` — timestamp `{doc['timestamp']}` — screenshot refs: {refs}")

    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    args = parse_args()
    report = build_report(args)
    json_out = Path(args.json_out).expanduser().resolve()
    markdown_out = Path(args.markdown_out).expanduser().resolve()
    json_out.parent.mkdir(parents=True, exist_ok=True)
    markdown_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    markdown_out.write_text(render_markdown(report), encoding="utf-8")
    return 0 if report["verdict"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
