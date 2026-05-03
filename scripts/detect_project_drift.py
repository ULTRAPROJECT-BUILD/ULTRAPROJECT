#!/usr/bin/env python3
from __future__ import annotations

"""
Detect project-level drift between canonical artifacts and derived/projected state.
"""

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
    build_report as build_project_context_report,
    default_context_path,
    default_image_index_path,
    default_index_path,
    default_video_index_path,
    discover_project_layout,
    relative_to_platform,
)
from build_project_image_evidence import build_report as build_project_image_report
from build_project_video_evidence import build_report as build_project_video_report

PHASE_TARGET_RE = re.compile(r"\bphase\s+(\d+)\b", re.IGNORECASE)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-file", required=True, help="Project markdown path.")
    parser.add_argument("--project-plan", help="Optional explicit project plan path.")
    parser.add_argument("--json-out", help="Optional JSON output path.")
    parser.add_argument("--markdown-out", help="Optional markdown output path.")
    return parser.parse_args()


def now() -> str:
    return datetime.now().astimezone().strftime("%Y-%m-%dT%H:%M:%S %Z %z")


def load_yaml(path: Path) -> dict[str, Any]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def parse_phase_target(text: str) -> int | None:
    match = PHASE_TARGET_RE.search(text or "")
    if not match:
        return None
    return int(match.group(1))


def write_output(path: str | None, content: str) -> None:
    if not path:
        return
    target = Path(path).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    project_file = Path(args.project_file).expanduser().resolve()
    layout = discover_project_layout(project_file)
    platform_root = Path(layout["platform_root"])
    fresh_report = build_project_context_report(
        argparse.Namespace(
            project_file=str(project_file),
            project_plan=args.project_plan,
            context_out=None,
            index_out=None,
        )
    )
    fresh_image_report = build_project_image_report(project_file)
    fresh_video_report = build_project_video_report(project_file)

    context_path = default_context_path(project_file)
    index_path = default_index_path(project_file)
    image_index_path = default_image_index_path(project_file)
    video_index_path = default_video_index_path(project_file)

    actual_index = load_yaml(index_path) if index_path.exists() else {}
    actual_image_index = load_yaml(image_index_path) if image_index_path.exists() else {}
    actual_video_index = load_yaml(video_index_path) if video_index_path.exists() else {}

    failures: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []

    def add_issue(kind: str, title: str, details: str, severity: str = "failure") -> None:
        target = failures if severity == "failure" else warnings
        target.append({"kind": kind, "title": title, "details": details})

    derived_paths = {
        "current_context": context_path,
        "artifact_index": index_path,
        "image_evidence_index": image_index_path,
        "video_evidence_index": video_index_path,
    }
    missing_derived = [label for label, path in derived_paths.items() if not path.exists()]
    if missing_derived:
        add_issue(
            "derived_missing",
            "Derived project context artifacts are missing",
            f"Missing: {', '.join(missing_derived)}",
        )

    source_paths: list[Path] = []
    for rel_path in fresh_report.get("authoritative_files", []):
        source_paths.append((platform_root / rel_path).resolve())
    source_paths.extend((platform_root / path).resolve() for path in fresh_report.get("decisions", []))
    source_paths.extend((platform_root / path).resolve() for path in fresh_report.get("lessons", []))
    for section in ("active", "recent_closed"):
        for ticket in fresh_report.get("tickets", {}).get(section, []):
            source_paths.append((platform_root / ticket["path"]).resolve())
    source_paths = [path for path in source_paths if path.exists()]

    if source_paths and not missing_derived:
        newest_source = max(path.stat().st_mtime for path in source_paths)
        stale = [
            label
            for label, path in derived_paths.items()
            if path.exists() and path.stat().st_mtime + 1 < newest_source
        ]
        if stale:
            add_issue(
                "derived_stale",
                "Derived project artifacts are older than canonical sources",
                f"Refresh needed for: {', '.join(stale)}",
            )

    missing_authoritative = [
        rel_path
        for rel_path in fresh_report.get("authoritative_files", [])
        if not (platform_root / rel_path).exists()
    ]
    if missing_authoritative:
        add_issue(
            "authoritative_missing",
            "Authoritative files referenced by the project context do not exist",
            ", ".join(missing_authoritative[:8]),
        )

    actual_current_review = ((actual_index.get("reviews") or {}).get("current_review") or {}).get("path", "")
    fresh_current_review = ((fresh_report.get("reviews") or {}).get("current_review") or {}).get("path", "")
    if actual_index and actual_current_review != fresh_current_review:
        add_issue(
            "current_review_mismatch",
            "Artifact index points at a stale current review",
            f"Indexed: `{actual_current_review or 'none'}` vs fresh: `{fresh_current_review or 'none'}`",
        )

    actual_authoritative = actual_index.get("authoritative_files") or []
    fresh_authoritative = fresh_report.get("authoritative_files") or []
    if actual_index and actual_authoritative != fresh_authoritative:
        add_issue(
            "authoritative_mismatch",
            "Artifact index authoritative file set drifted",
            "Derived artifact index no longer matches fresh project context output.",
        )

    actual_phase = actual_index.get("current_phase")
    actual_wave = actual_index.get("current_wave", "")
    if actual_index and actual_phase != fresh_report.get("current_phase"):
        add_issue(
            "phase_mismatch",
            "Artifact index current phase drifted",
            f"Indexed phase `{actual_phase}` vs fresh phase `{fresh_report.get('current_phase')}`",
        )
    if actual_index and actual_wave != fresh_report.get("current_wave", ""):
        add_issue(
            "wave_mismatch",
            "Artifact index current wave drifted",
            f"Indexed wave `{actual_wave or 'none'}` vs fresh wave `{fresh_report.get('current_wave') or 'none'}`",
            severity="warning",
        )

    actual_image_paths = set(actual_image_index.get("semantic_image_corpus") or [])
    fresh_image_paths = set(fresh_image_report.get("semantic_image_corpus") or [])
    if actual_image_index and actual_image_paths != fresh_image_paths:
        add_issue(
            "image_index_mismatch",
            "Image evidence index drifted from current visual evidence",
            "Indexed image corpus no longer matches fresh image evidence discovery.",
            severity="warning",
        )

    actual_video_paths = set(actual_video_index.get("semantic_video_corpus") or [])
    fresh_video_paths = set(fresh_video_report.get("semantic_video_corpus") or [])
    if actual_video_index and actual_video_paths != fresh_video_paths:
        add_issue(
            "video_index_mismatch",
            "Video evidence index drifted from current walkthrough evidence",
            "Indexed video corpus no longer matches fresh video evidence discovery.",
            severity="warning",
        )

    current_phase_value = fresh_report.get("current_phase")
    current_review_label = ((fresh_report.get("reviews") or {}).get("current_review") or {}).get("kind_label", "")
    current_phase_title = fresh_report.get("current_phase_title", "")
    overdue_assumptions: list[str] = []
    for row in (fresh_report.get("assumptions", {}) or {}).get("active", []):
        target = str(row.get("Target Phase/Gate", "")).strip()
        assumption_id = str(row.get("ID", "?")).strip()
        target_phase = parse_phase_target(target)
        delivery_due = "delivery" in target.lower() and (
            "delivery" in current_review_label.lower() or "delivery" in current_phase_title.lower()
        )
        if target_phase is not None and isinstance(current_phase_value, int) and target_phase <= current_phase_value:
            overdue_assumptions.append(f"{assumption_id} -> {target}")
        elif delivery_due:
            overdue_assumptions.append(f"{assumption_id} -> {target}")
    if overdue_assumptions:
        add_issue(
            "assumption_overdue",
            "Active assumptions have outlived their target phase/gate",
            "; ".join(overdue_assumptions[:8]),
            severity="warning",
        )

    if failures:
        verdict = "FAIL"
    elif warnings:
        verdict = "WARN"
    else:
        verdict = "PASS"

    recommended_actions: list[str] = []
    if any(issue["kind"] in {"derived_missing", "derived_stale", "current_review_mismatch", "authoritative_mismatch", "phase_mismatch"} for issue in failures + warnings):
        recommended_actions.append("Refresh derived context artifacts and project indexes.")
    if any(issue["kind"] == "image_index_mismatch" for issue in warnings):
        recommended_actions.append("Refresh project image evidence and selective image embeddings.")
    if any(issue["kind"] == "video_index_mismatch" for issue in warnings):
        recommended_actions.append("Refresh project video evidence and selective video embeddings.")
    if any(issue["kind"] == "assumption_overdue" for issue in warnings):
        recommended_actions.append("Resolve, defer explicitly, or accept-risk the overdue assumptions in the plan.")
    if any(issue["kind"] == "authoritative_missing" for issue in failures):
        recommended_actions.append("Repair or supersede missing authoritative artifact references before the next gate.")

    return {
        "generated_at": now(),
        "project": fresh_report.get("project"),
        "client": fresh_report.get("client"),
        "verdict": verdict,
        "paths": {
            "project_file": relative_to_platform(project_file, platform_root),
            "project_plan": fresh_report.get("paths", {}).get("project_plan", ""),
            "current_context": relative_to_platform(context_path, platform_root),
            "artifact_index": relative_to_platform(index_path, platform_root),
            "image_evidence_index": relative_to_platform(image_index_path, platform_root),
            "video_evidence_index": relative_to_platform(video_index_path, platform_root),
        },
        "current_phase": fresh_report.get("current_phase"),
        "current_phase_display": fresh_report.get("current_phase_display"),
        "current_wave": fresh_report.get("current_wave", ""),
        "current_review": (fresh_report.get("reviews") or {}).get("current_review") or {},
        "failures": failures,
        "warnings": warnings,
        "recommended_actions": recommended_actions,
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Project Drift Detection",
        "",
        f"- Generated: {report['generated_at']}",
        f"- Project: `{report['project']}`",
        f"- Verdict: **{report['verdict']}**",
        f"- Current phase: {report.get('current_phase_display', report.get('current_phase', 'unknown'))}",
    ]
    if report.get("current_wave"):
        lines.append(f"- Current wave: {report['current_wave']}")
    current_review = report.get("current_review") or {}
    if current_review.get("kind_label"):
        label = current_review["kind_label"]
        if current_review.get("grade"):
            label += f" ({current_review['grade']})"
        lines.append(f"- Current review: {label}")

    lines.extend(["", "## Failures", ""])
    if not report.get("failures"):
        lines.append("- None.")
    else:
        for issue in report["failures"]:
            lines.append(f"- **{issue['title']}** — {issue['details']}")

    lines.extend(["", "## Warnings", ""])
    if not report.get("warnings"):
        lines.append("- None.")
    else:
        for issue in report["warnings"]:
            lines.append(f"- **{issue['title']}** — {issue['details']}")

    lines.extend(["", "## Recommended Actions", ""])
    if not report.get("recommended_actions"):
        lines.append("- No action needed.")
    else:
        for action in report["recommended_actions"]:
            lines.append(f"- {action}")

    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    report = build_report(args)
    write_output(args.json_out, json.dumps(report, indent=2))
    write_output(args.markdown_out, render_markdown(report))
    return 1 if report["verdict"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
