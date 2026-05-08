#!/usr/bin/env python3
from __future__ import annotations

"""
Hybrid project retrieval: exact project context + text semantic results + image semantic results.
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from build_project_context import default_index_path, default_video_index_path
from project_text_retrieval import REPO_ROOT
from project_text_retrieval import search_project_text
from search_media import search as search_media

RETRIEVAL_USAGE_DIR = REPO_ROOT / "logs" / "retrieval"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query", help="Natural-language project retrieval query.")
    parser.add_argument("--project-file", help="Project markdown path; manifests will be derived automatically.")
    parser.add_argument("--artifact-index", help="Explicit artifact-index manifest path.")
    parser.add_argument("--top-text", type=int, default=6, help="Number of text results to return.")
    parser.add_argument("--top-images", type=int, default=4, help="Number of image results to return.")
    args = parser.parse_args()
    if bool(args.project_file) == bool(args.artifact_index):
        parser.error("Provide exactly one of --project-file or --artifact-index.")
    return args


def load_yaml(path: Path) -> dict[str, Any]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        data = {}
    return data if isinstance(data, dict) else {}


def summarize_exact_context(report: dict[str, Any]) -> dict[str, Any]:
    current_review = ((report.get("reviews") or {}).get("current_review") or {})
    phase_label = ""
    current_phase_display = report.get("current_phase_display")
    total_phases = report.get("total_phases")
    if current_phase_display is not None:
        phase_label = f"Phase {current_phase_display}"
        if total_phases:
            phase_label += f"/{total_phases}"
        if report.get("current_phase_title"):
            phase_label += f" — {report['current_phase_title']}"
    code_workspaces = report.get("code_workspaces") or []
    primary_workspace = next(
        (
            workspace
            for workspace in code_workspaces
            if isinstance(workspace, dict) and workspace.get("role") == "primary"
        ),
        {},
    )
    return {
        "project": report.get("project", ""),
        "client": report.get("client", ""),
        "title": report.get("title", ""),
        "goal": report.get("goal", ""),
        "status": report.get("status", ""),
        "phase": phase_label,
        "current_wave": report.get("current_wave", ""),
        "current_review": {
            "kind": current_review.get("kind_label", ""),
            "grade": current_review.get("grade", ""),
            "path": current_review.get("path", ""),
        }
        if current_review
        else {},
        "current_context_path": ((report.get("paths") or {}).get("current_context") or ""),
        "artifact_index_path": ((report.get("paths") or {}).get("artifact_index") or ""),
        "image_evidence_index_path": ((report.get("paths") or {}).get("image_evidence_index") or ""),
        "video_evidence_index_path": ((report.get("paths") or {}).get("video_evidence_index") or ""),
        "authoritative_files": (report.get("authoritative_files") or [])[:10],
        "active_ticket_count": len(((report.get("tickets") or {}).get("active") or [])),
        "blocked_ticket_count": len(((report.get("tickets") or {}).get("blocked") or [])),
        "active_assumption_count": len(((report.get("assumptions") or {}).get("active") or [])),
        "code_workspace_count": len(code_workspaces),
        "primary_code_workspace": {
            "root": primary_workspace.get("root", ""),
            "exists": bool(primary_workspace.get("exists")),
            "gitnexus_ready": bool(primary_workspace.get("gitnexus_ready")),
        }
        if primary_workspace
        else {},
    }


def append_retrieval_usage_event(event: dict[str, Any]) -> None:
    try:
        RETRIEVAL_USAGE_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().astimezone()
        payload = {
            "timestamp": stamp.isoformat(),
            "date": stamp.strftime("%Y-%m-%d"),
            **event,
        }
        log_path = RETRIEVAL_USAGE_DIR / f"retrieval-{stamp.strftime('%Y-%m-%d')}.jsonl"
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True) + "\n")
    except Exception:
        return


def search_project_hybrid(
    query: str,
    *,
    artifact_index_path: Path,
    top_text: int = 6,
    top_images: int = 4,
) -> dict[str, Any]:
    report = load_yaml(artifact_index_path)
    exact_context = summarize_exact_context(report)
    project = str(report.get("project") or "").strip()
    client = str(report.get("client") or "").strip()
    image_manifest_rel = str(((report.get("paths") or {}).get("image_evidence_index") or "")).strip()
    video_manifest_rel = str(((report.get("paths") or {}).get("video_evidence_index") or "")).strip()
    # The artifact-index lives inside the project's `<slug>.derived/` folder; the
    # image/video evidence indexes are siblings, and the canonical project markdown
    # is one level up (parent of `.derived/`).
    derived_dir = artifact_index_path.parent
    project_slug = derived_dir.stem
    if project_slug.endswith(".derived"):
        project_slug = project_slug[: -len(".derived")]
    project_md_path = derived_dir.parent / f"{project_slug}.md"
    fallback_image_manifest_path = derived_dir / "image-evidence-index.yaml"
    fallback_video_manifest_path = default_video_index_path(project_md_path)
    image_manifest_path = (REPO_ROOT / image_manifest_rel).resolve() if image_manifest_rel else fallback_image_manifest_path
    if not image_manifest_path.exists():
        image_manifest_path = fallback_image_manifest_path
    image_manifest = load_yaml(image_manifest_path) if image_manifest_path.exists() else {}
    video_manifest_path = (REPO_ROOT / video_manifest_rel).resolve() if video_manifest_rel else fallback_video_manifest_path
    if not video_manifest_path.exists():
        video_manifest_path = fallback_video_manifest_path
    video_manifest = load_yaml(video_manifest_path) if video_manifest_path.exists() else {}

    text_results = search_project_text(query, artifact_index_path, top_k=top_text)
    image_results: list[dict[str, Any]] = []
    video_results: list[dict[str, Any]] = []
    if (image_manifest.get("image_evidence") or {}).get("images"):
        image_results = search_media(
            query,
            top_k=max(1, top_images),
            client_filter=client,
            project_filter=project,
            media_kind_filter="image",
        )
    if (video_manifest.get("video_evidence") or {}).get("videos"):
        video_results = search_media(
            query,
            top_k=max(1, top_images),
            client_filter=client,
            project_filter=project,
            media_kind_filter="video",
            category_prefix="video_",
        )

    result = {
        "query": query,
        "project": project,
        "client": client,
        "exact_context": exact_context,
        "text_results": text_results.get("results", []),
        "image_results": image_results,
        "video_results": video_results,
        "counts": {
            "authoritative_files": len(exact_context.get("authoritative_files") or []),
            "text_results": len(text_results.get("results") or []),
            "image_results": len(image_results),
            "video_results": len(video_results),
        },
    }
    append_retrieval_usage_event(
        {
            "kind": "project_hybrid_search",
            "query": query,
            "project": project,
            "client": client,
            "artifact_index_path": str(artifact_index_path),
            "ticket_id": os.environ.get("AGENT_PLATFORM_TICKET_ID", ""),
            "task_type": os.environ.get("AGENT_PLATFORM_TASK_TYPE", ""),
            "counts": result["counts"],
        }
    )
    return result


def main() -> int:
    args = parse_args()
    artifact_index_path = (
        Path(args.artifact_index).expanduser().resolve()
        if args.artifact_index
        else default_index_path(Path(args.project_file).expanduser().resolve())
    )
    result = search_project_hybrid(
        args.query,
        artifact_index_path=artifact_index_path,
        top_text=args.top_text,
        top_images=args.top_images,
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
