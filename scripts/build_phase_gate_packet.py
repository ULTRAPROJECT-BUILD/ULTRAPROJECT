#!/usr/bin/env python3
"""
Build a machine-readable phase gate packet contract.

The packet is a derived artifact that declares what a hard phase gate is
allowed to trust:
- the active phase contract and exit criteria
- the current phase ticket set
- the exact evidence docs the packet depends on
- the current visual/walkthrough proof surface
- proof-item ownership for gate-critical criteria
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from build_project_context import (
    choose_latest_path,
    discover_project_layout,
    find_latest_project_plan,
    path_matches_project,
)
from build_review_pack import build_report as build_review_pack_report
from check_phase_readiness import (
    extract_referenced_paths,
    match_tickets_to_criterion,
    normalize_status,
    normalize_whitespace,
    parse_plan_phase,
    tokenize,
)
from check_ticket_evidence import parse_frontmatter_map
from resolve_briefs import build_report as build_brief_resolution_report

TIMESTAMP_FMT = "%Y-%m-%dT%H:%M:%S %Z %z"
TICKET_ID_RE = re.compile(r"\bT-\d+\b", re.IGNORECASE)
SEARCH_ROOT_HINTS = (
    "artifact",
    "deliverable",
    "docs",
    "proof",
    "review-pack",
    "screenshot",
    "screens",
    "qc",
    "stitch",
    "design",
    "media",
    "walkthrough",
    "slide",
)
SEARCHABLE_SUFFIXES = {".md", ".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg", ".mp4", ".mov", ".webm", ".json", ".yaml", ".yml", ".txt", ".pdf"}
PROJECT_WORKSPACE_RE = re.compile(r"(/" + r"Users/[A-Za-z0-9._/\-]+)")
KIND_STEM_ALIASES = {
    "quality-check": ("quality-check", "quality_check", "formal-qc", "recovery-qc", "phase-1-recovery-qc"),
    "artifact-polish-review": ("artifact-polish-review", "artifact_polish_review", "polish-review"),
    "review-pack": ("review-pack", "review_pack"),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-file", required=True, help="Project markdown path.")
    parser.add_argument("--project-plan", help="Optional explicit project plan path.")
    parser.add_argument("--phase", required=True, type=int, help="Phase number to build the packet for.")
    parser.add_argument("--packet-out", "--output", required=True, help="Where to write the YAML gate packet.")
    return parser.parse_args()


def now() -> str:
    return datetime.now().astimezone().strftime(TIMESTAMP_FMT)


def is_project_deliverables_root(path: Path) -> bool:
    return path.exists() and path.is_dir() and (
        (path / "review-pack").exists()
        or (path / "package.json").exists()
        or (path / "src-tauri").exists()
        or (path / "artifacts").exists()
    )


def resolve_project_deliverables_root(layout: dict[str, Any], project_file: Path, plan_path: Path) -> Path:
    default_root = Path(layout["deliverables_root"]).resolve()
    project = str(layout["project"])
    candidates: list[Path] = []
    desktop_candidate = Path(layout["platform_root"]).resolve().parent / project
    candidates.append(desktop_candidate)

    for source in (project_file, plan_path):
        if not source.exists():
            continue
        text = source.read_text(encoding="utf-8")
        for match in PROJECT_WORKSPACE_RE.finditer(text):
            candidate = Path(match.group(1)).expanduser()
            if candidate.name == project:
                candidates.append(candidate)

    seen: set[str] = set()
    for candidate in candidates:
        resolved = candidate.resolve()
        key = str(resolved)
        if key in seen:
            continue
        seen.add(key)
        if is_project_deliverables_root(resolved):
            return resolved
    return default_root


def latest_snapshot_matching(
    layout: dict[str, Any],
    project: str,
    *,
    phase: int | None = None,
    subtype_values: tuple[str, ...] = (),
    filename_contains: tuple[str, ...] = (),
) -> Path | None:
    snapshots_dir = Path(layout["snapshots_dir"])
    project_snapshots_dir = snapshots_dir / project
    scoped_candidates: list[Path] = []
    fallback_candidates: list[Path] = []
    normalized_subtype_values = {value.strip().lower().replace("_", "-") for value in subtype_values}
    snapshot_paths: list[Path] = []
    if project_snapshots_dir.exists():
        snapshot_paths.extend(sorted(project_snapshots_dir.rglob("*.md")))
    snapshot_paths.extend(sorted(snapshots_dir.glob("*.md")))

    for path in snapshot_paths:
        project_scoped = is_project_scoped_snapshot(path, layout)
        if not project_scoped and not path_matches_project(path, project):
            continue
        data = parse_frontmatter_map(path)
        subtype = str(data.get("subtype", "")).strip().lower().replace("_", "-")
        type_value = str(data.get("type", "")).strip().lower().replace("_", "-")
        stem = path.stem.lower().replace("_", "-")
        stem_kind_match = False
        for value in normalized_subtype_values:
            aliases = KIND_STEM_ALIASES.get(value, (value,))
            if any(alias in stem for alias in aliases):
                stem_kind_match = True
                break
        if subtype_values and subtype not in normalized_subtype_values and type_value not in normalized_subtype_values and not stem_kind_match:
            continue
        if phase is not None:
            phase_value = data.get("phase")
            try:
                snapshot_phase = int(str(phase_value).strip()) if str(phase_value).strip() else None
            except ValueError:
                snapshot_phase = None
            if snapshot_phase is not None and snapshot_phase != phase:
                continue
        if filename_contains and not all(token in stem for token in filename_contains):
            continue
        if project_scoped:
            scoped_candidates.append(path.resolve())
        else:
            fallback_candidates.append(path.resolve())
    return choose_latest_path(scoped_candidates) or choose_latest_path(fallback_candidates)


def is_project_scoped_snapshot(path: Path, layout: dict[str, Any]) -> bool:
    project_snapshots_dir = Path(layout["snapshots_dir"]) / str(layout["project"])
    try:
        path.resolve().relative_to(project_snapshots_dir.resolve())
        return True
    except ValueError:
        return False


def resolve_review_surface_root(
    default_root: Path,
    layout: dict[str, Any],
    *,
    review_pack: Path | None,
) -> Path:
    if review_pack and is_project_scoped_snapshot(review_pack, layout):
        parent = review_pack.resolve().parent
        project_snapshots_dir = (Path(layout["snapshots_dir"]) / str(layout["project"])).resolve()
        if parent != project_snapshots_dir:
            return parent
    return default_root


def resolve_brief_paths(project_file: Path, plan_path: Path, layout: dict[str, Any], phase: int) -> list[Path]:
    report = build_brief_resolution_report(
        argparse.Namespace(
            project=layout["project"],
            project_file=str(project_file),
            project_plan=str(plan_path),
            phase=phase,
            wave=None,
            ticket_id=None,
            ticket_path=None,
            search_root=[str(Path(layout["snapshots_dir"]))],
            json_out=None,
            markdown_out=None,
        )
    )
    paths: list[Path] = []
    seen: set[str] = set()
    for entry in report.get("ordered_briefs", []):
        path_text = str(entry.get("path", "")).strip()
        if not path_text:
            continue
        resolved = Path(path_text).expanduser().resolve()
        key = str(resolved)
        if key in seen:
            continue
        seen.add(key)
        paths.append(resolved)
    return paths


def derive_search_roots(
    snapshots_dir: Path,
    evidence_docs: list[Path | None],
    proof_items: list[dict[str, Any]],
    walkthrough_artifacts: list[dict[str, Any]],
) -> list[str]:
    roots: list[str] = []
    seen: set[str] = set()

    def add(path: Path | None, *, force: bool = False) -> None:
        if path is None:
            return
        resolved = path.expanduser().resolve()
        root = resolved if resolved.is_dir() else resolved.parent
        if not root.exists():
            return
        lowered = root.name.lower()
        if not force and not any(hint in lowered for hint in SEARCH_ROOT_HINTS):
            return
        key = str(root)
        if key in seen:
            return
        seen.add(key)
        roots.append(key)

    def add_hinted_children(path: Path | None) -> None:
        if path is None:
            return
        resolved = path.expanduser().resolve()
        root = resolved if resolved.is_dir() else resolved.parent
        if not root.exists() or not root.is_dir():
            return
        try:
            children = list(root.iterdir())
        except OSError:
            return
        for child in children:
            if not child.is_dir():
                continue
            lowered = child.name.lower()
            if any(hint in lowered for hint in SEARCH_ROOT_HINTS):
                add(child)

    add(snapshots_dir, force=True)
    for doc in evidence_docs:
        add(doc, force=True)
    for item in proof_items:
        for value in item.get("expected_paths", []) or []:
            path_text = str(value).strip()
            if path_text:
                candidate = Path(path_text)
                if candidate.suffix.lower() in SEARCHABLE_SUFFIXES or candidate.is_dir():
                    add(candidate)
                    add_hinted_children(candidate)
    for artifact in walkthrough_artifacts:
        path_text = str(artifact.get("path", "")).strip()
        if path_text:
            add(Path(path_text), force=True)
    return roots


def build_ticket_contexts(
    phase_ticket_ids: list[str],
    ticket_files: dict[str, Path],
    *,
    client_root: Path,
    deliverables_root: Path,
    repo_root: Path,
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    ticket_contexts: dict[str, dict[str, Any]] = {}
    ticket_records: dict[str, dict[str, Any]] = {}
    for ticket_id in phase_ticket_ids:
        ticket_path = ticket_files.get(ticket_id)
        if ticket_path is None or not ticket_path.exists():
            continue
        data = parse_frontmatter_map(ticket_path)
        text = ticket_path.read_text(encoding="utf-8")
        title = str(data.get("title", ticket_path.stem)).strip()
        tags_raw = data.get("tags", [])
        if isinstance(tags_raw, list):
            tags = [str(tag).strip() for tag in tags_raw if str(tag).strip()]
        else:
            tags = [item.strip() for item in str(tags_raw).strip("[]").split(",") if item.strip()]
        referenced_paths = extract_referenced_paths(
            text,
            client_root=client_root,
            deliverables_root=deliverables_root,
            repo_root=repo_root,
        )
        ticket_contexts[ticket_id] = {
            "ticket_id": ticket_id,
            "path": str(ticket_path),
            "status": normalize_status(data.get("status", "")),
            "task_type": str(data.get("task_type", "")).strip().lower(),
            "title": title,
            "title_tokens": tokenize(title),
            "search_text": normalize_whitespace(f"{title}\n{data.get('task_type', '')}\n{text}").lower(),
            "tokens": tokenize(f"{title}\n{data.get('task_type', '')}\n{text}"),
            "partial_coverage_flags": [],
            "explicit_partial_acceptance": False,
            "referenced_paths": referenced_paths,
        }
        ticket_records[ticket_id] = {
            "id": ticket_id,
            "title": title,
            "path": str(ticket_path),
            "status": normalize_status(data.get("status", "")),
            "task_type": str(data.get("task_type", "")).strip().lower(),
            "tags": tags,
        }
    return ticket_contexts, ticket_records


def infer_ticket_owners(ticket_records: dict[str, dict[str, Any]], *needles: str) -> list[str]:
    lowered_needles = [needle.lower() for needle in needles if needle]
    owners: list[str] = []
    for ticket_id, record in ticket_records.items():
        haystack = " ".join(
            [
                str(record.get("task_type", "")),
                str(record.get("title", "")),
                " ".join(record.get("tags", [])),
            ]
        ).lower()
        if any(needle in haystack for needle in lowered_needles):
            owners.append(ticket_id)
    return sorted(set(owners))


def owner_tickets_for_criterion(
    criterion: dict[str, Any],
    ticket_contexts: dict[str, dict[str, Any]],
    ticket_records: dict[str, dict[str, Any]],
) -> tuple[list[str], list[dict[str, Any]]]:
    matched = match_tickets_to_criterion(criterion, ticket_contexts)
    owner_tickets = [entry["ticket_id"] for entry in matched]
    lower = criterion["text"].lower()
    inferred_owner_ids: list[str] = []

    if any(token in lower for token in ("screenshot", "theme", "visual", "runtime screenshot", "dark mode", "light mode")):
        inferred_owner_ids.extend(infer_ticket_owners(ticket_records, "quality_check", "qc", "evidence capture"))
    if any(token in lower for token in ("walkthrough", "video", "media", "screen recording", "demo")):
        inferred_owner_ids.extend(infer_ticket_owners(ticket_records, "quality_check", "qc", "evidence capture", "walkthrough"))
    if any(token in lower for token in ("review pack", "artifact polish", "paperwork", "readiness", "runtime verification")):
        inferred_owner_ids.extend(infer_ticket_owners(ticket_records, "artifact_polish_review", "artifact polish"))

    owner_tickets.extend(inferred_owner_ids)
    if inferred_owner_ids:
        inferred_contexts = [ticket_contexts[ticket_id] for ticket_id in inferred_owner_ids if ticket_id in ticket_contexts]
        if not matched:
            matched = inferred_contexts
        else:
            existing_ids = {entry["ticket_id"] for entry in matched}
            matched.extend(entry for entry in inferred_contexts if entry["ticket_id"] not in existing_ids)

    deduped_owner_tickets = sorted(set(owner_tickets))
    if not deduped_owner_tickets and len(ticket_records) == 1:
        deduped_owner_tickets = sorted(ticket_records.keys())
    return deduped_owner_tickets, matched


def packet_proof_items(
    phase: dict[str, Any],
    ticket_contexts: dict[str, dict[str, Any]],
    ticket_records: dict[str, dict[str, Any]],
    *,
    runtime_doc: Path | None,
    regression_doc: Path | None,
    qc_reports: list[Path],
    artifact_polish_review: Path | None,
    walkthrough_requirement: dict[str, Any],
    walkthrough_artifacts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for criterion in phase.get("exit_criteria", []):
        owner_tickets, matched = owner_tickets_for_criterion(criterion, ticket_contexts, ticket_records)
        evidence_paths = sorted({path for entry in matched for path in entry.get("referenced_paths", [])})
        items.append(
            {
                "key": f"exit-criterion-{criterion['index']}",
                "kind": "exit_criterion",
                "description": criterion["text"],
                "validator": "phase_readiness_exit_criterion",
                "owner_tickets": owner_tickets,
                "expected_paths": evidence_paths,
            }
        )

    if runtime_doc:
        items.append(
            {
                "key": "runtime-check-doc",
                "kind": "evidence_doc",
                "description": "Latest phase runtime verification snapshot",
                "validator": "path_exists_and_is_fresh",
                "owner_tickets": infer_ticket_owners(ticket_records, "runtime", "verification", "regression"),
                "expected_paths": [str(runtime_doc)],
            }
        )
    if regression_doc:
        items.append(
            {
                "key": "regression-doc",
                "kind": "evidence_doc",
                "description": "Latest phase regression snapshot",
                "validator": "path_exists_and_is_fresh",
                "owner_tickets": infer_ticket_owners(ticket_records, "regression", "quality_check", "qc"),
                "expected_paths": [str(regression_doc)],
            }
        )
    if qc_reports:
        items.append(
            {
                "key": "qc-evidence-docs",
                "kind": "evidence_doc",
                "description": "Latest QC report set for the active phase",
                "validator": "qc_evidence_present_and_cited",
                "owner_tickets": infer_ticket_owners(ticket_records, "quality_check", "qc"),
                "expected_paths": [str(path) for path in qc_reports],
            }
        )
    if artifact_polish_review:
        items.append(
            {
                "key": "artifact-polish-review",
                "kind": "evidence_doc",
                "description": "Latest artifact polish review for the project",
                "validator": "path_exists_and_is_fresh",
                "owner_tickets": infer_ticket_owners(ticket_records, "artifact_polish_review", "artifact polish"),
                "expected_paths": [str(artifact_polish_review)],
            }
        )
    if walkthrough_requirement.get("level") in {"required", "recommended"}:
        items.append(
            {
                "key": "walkthrough-artifact",
                "kind": "media",
                "description": "Walkthrough video surface for interactive deliverables",
                "validator": "walkthrough_required_if_interactive",
                "owner_tickets": infer_ticket_owners(
                    ticket_records,
                    "quality_check",
                    "qc",
                    "artifact polish",
                    "evidence capture",
                    "walkthrough",
                ),
                "expected_paths": [str(item.get("path")) for item in walkthrough_artifacts if item.get("path")],
                "meta": {"requirement": walkthrough_requirement},
            }
        )
    return items


def build_report(project_file: Path, *, explicit_plan: Path | None, phase_number: int) -> dict[str, Any]:
    layout = discover_project_layout(project_file)
    project = layout["project"]
    plan_path = find_latest_project_plan(layout, explicit_plan)
    if plan_path is None:
        raise FileNotFoundError(f"No project plan found for {project}.")
    deliverables_root = resolve_project_deliverables_root(layout, project_file, plan_path)

    phase = parse_plan_phase(plan_path, phase_number)
    if phase is None:
        raise ValueError(f"Phase {phase_number} not found in {plan_path}.")

    tickets_dir = Path(layout["tickets_dir"]).resolve()
    ticket_files: dict[str, Path] = {}
    for path in sorted(tickets_dir.glob("*.md")):
        data = parse_frontmatter_map(path)
        explicit_id = str(data.get("id", "")).strip().upper()
        match = TICKET_ID_RE.search(path.stem.upper())
        ticket_id = explicit_id or (match.group(0).upper() if match else "")
        if ticket_id:
            ticket_files[ticket_id] = path.resolve()
    ticket_contexts, ticket_records = build_ticket_contexts(
        phase.get("tickets", []),
        ticket_files,
        client_root=Path(layout["client_root"]).resolve(),
        deliverables_root=deliverables_root,
        repo_root=Path(layout["platform_root"]).resolve(),
    )

    brief_paths = resolve_brief_paths(project_file, plan_path, layout, phase_number)
    runtime_doc = latest_snapshot_matching(
        layout,
        project,
        phase=phase_number,
        filename_contains=(f"phase-{phase_number}", "runtime-check"),
    )
    regression_doc = latest_snapshot_matching(
        layout,
        project,
        phase=phase_number,
        filename_contains=(f"phase-{phase_number}", "regression"),
    )
    latest_qc = latest_snapshot_matching(
        layout,
        project,
        phase=phase_number,
        subtype_values=("quality-check",),
    )
    if latest_qc is None:
        latest_qc = latest_snapshot_matching(
            layout,
            project,
            filename_contains=(f"qc-phase{phase_number}",),
        )
    artifact_polish_review = latest_snapshot_matching(
        layout,
        project,
        subtype_values=("artifact-polish-review",),
    )
    review_pack = latest_snapshot_matching(
        layout,
        project,
        subtype_values=("review-pack",),
    )
    latest_readiness = latest_snapshot_matching(
        layout,
        project,
        phase=phase_number,
        filename_contains=(f"phase-{phase_number}", "readiness"),
    )

    qc_reports = [path for path in [latest_qc] if path is not None]
    review_surface_root = resolve_review_surface_root(
        deliverables_root,
        layout,
        review_pack=review_pack,
    )
    review_pack_preview = build_review_pack_report(
        argparse.Namespace(
            deliverables_root=str(review_surface_root),
            brief=[str(path) for path in brief_paths],
            qc_report=[str(path) for path in qc_reports],
            max_files_per_category=12,
            json_out=str(review_surface_root / "_unused-review-pack.json"),
            markdown_out=str(review_surface_root / "_unused-review-pack.md"),
        )
    )

    evidence_docs = [path for path in [runtime_doc, regression_doc, latest_qc, artifact_polish_review, review_pack] if path is not None]
    proof_items = packet_proof_items(
        phase,
        ticket_contexts,
        ticket_records,
        runtime_doc=runtime_doc,
        regression_doc=regression_doc,
        qc_reports=qc_reports,
        artifact_polish_review=artifact_polish_review,
        walkthrough_requirement=review_pack_preview.get("walkthrough_requirement", {}),
        walkthrough_artifacts=review_pack_preview.get("walkthrough_artifacts", []),
    )
    readiness_search_roots = derive_search_roots(
        Path(layout["snapshots_dir"]).resolve(),
        evidence_docs,
        proof_items,
        review_pack_preview.get("walkthrough_artifacts", []),
    )
    search_root_paths = [Path(path) for path in readiness_search_roots]
    for ticket_id in phase.get("tickets", []):
        ticket_path = ticket_files.get(ticket_id)
        ticket_context = ticket_contexts.get(ticket_id)
        if ticket_path is None or ticket_context is None or not ticket_path.exists():
            continue
        refreshed_paths = extract_referenced_paths(
            ticket_path.read_text(encoding="utf-8"),
            client_root=Path(layout["client_root"]).resolve(),
            deliverables_root=deliverables_root,
            repo_root=Path(layout["platform_root"]).resolve(),
            search_roots=search_root_paths,
        )
        ticket_context["referenced_paths"] = sorted(set(ticket_context.get("referenced_paths", [])) | set(refreshed_paths))
    proof_items = packet_proof_items(
        phase,
        ticket_contexts,
        ticket_records,
        runtime_doc=runtime_doc,
        regression_doc=regression_doc,
        qc_reports=qc_reports,
        artifact_polish_review=artifact_polish_review,
        walkthrough_requirement=review_pack_preview.get("walkthrough_requirement", {}),
        walkthrough_artifacts=review_pack_preview.get("walkthrough_artifacts", []),
    )
    readiness_search_roots = derive_search_roots(
        Path(layout["snapshots_dir"]).resolve(),
        evidence_docs,
        proof_items,
        review_pack_preview.get("walkthrough_artifacts", []),
    )

    return {
        "generated_at": now(),
        "project": project,
        "client": layout["client"],
        "phase": phase_number,
        "phase_title": phase.get("title", ""),
        "execution_scope": layout["scope"],
        "paths": {
            "platform_root": str(Path(layout["platform_root"]).resolve()),
            "client_root": str(Path(layout["client_root"]).resolve()),
            "project_file": str(project_file.resolve()),
            "project_plan": str(plan_path.resolve()),
            "tickets_dir": str(tickets_dir),
            "snapshots_dir": str(Path(layout["snapshots_dir"]).resolve()),
            "deliverables_root": str(deliverables_root),
            "artifacts_root": str((deliverables_root / "artifacts").resolve()),
        },
        "brief_paths": [str(path) for path in brief_paths],
        "phase_contract": {
            "title": phase.get("title", ""),
            "tickets": phase.get("tickets", []),
            "exit_criteria": [
                {"index": item["index"], "criterion": item["text"], "raw_text": item["raw_text"]}
                for item in phase.get("exit_criteria", [])
            ],
        },
        "phase_tickets": [ticket_records[ticket_id] for ticket_id in phase.get("tickets", []) if ticket_id in ticket_records],
        "evidence_docs": {
            "runtime_check": str(runtime_doc) if runtime_doc else "",
            "regression": str(regression_doc) if regression_doc else "",
            "quality_check": [str(path) for path in qc_reports],
            "artifact_polish_review": str(artifact_polish_review) if artifact_polish_review else "",
            "review_pack": str(review_pack) if review_pack else "",
            "latest_readiness": str(latest_readiness) if latest_readiness else "",
        },
        "review_surface": {
            "walkthrough_requirement": review_pack_preview.get("walkthrough_requirement", {}),
            "walkthrough_artifacts": review_pack_preview.get("walkthrough_artifacts", []),
            "walkthrough_selection": review_pack_preview.get("walkthrough_selection", {}),
            "spotlight_artifacts": review_pack_preview.get("spotlight_artifacts", []),
        },
        "proof_items": proof_items,
        "readiness_inputs": {
            "project_file": str(project_file.resolve()),
            "project_plan": str(plan_path.resolve()),
            "phase": phase_number,
            "tickets_dir": str(tickets_dir),
            "artifacts_root": str((deliverables_root / "artifacts").resolve()),
            "deliverables_root": str(deliverables_root),
            "search_root": readiness_search_roots,
            "brief": [str(path) for path in brief_paths],
            "evidence_doc": [str(path) for path in evidence_docs],
        },
    }


def write_packet(report: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(yaml.safe_dump(report, sort_keys=False, allow_unicode=False), encoding="utf-8")


def main() -> int:
    args = parse_args()
    project_file = Path(args.project_file).expanduser().resolve()
    explicit_plan = Path(args.project_plan).expanduser().resolve() if args.project_plan else None
    report = build_report(project_file, explicit_plan=explicit_plan, phase_number=args.phase)
    output_path = Path(args.packet_out).expanduser().resolve()
    write_packet(report, output_path)
    print(json.dumps({"status": "ok", "packet": str(output_path)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
