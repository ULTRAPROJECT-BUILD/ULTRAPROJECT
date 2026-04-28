#!/usr/bin/env python3
"""
Build a selective per-project video evidence index.

This writes a derived file into the project's `<slug>.derived/` sibling folder:

- `<slug>.derived/video-evidence-index.yaml`

The index is intentionally selective. It captures project-relevant walkthroughs,
QC recordings, demo proofs, and other review-surface videos that the
orchestrator may need for fast project navigation or targeted video embedding
refreshes.
See vault/SCHEMA.md → "Project Derived Context" for the layout contract.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from build_project_context import (
    collect_project_docs,
    collect_tickets,
    derived_dir,
    discover_project_layout,
    relative_to_platform,
)
from build_review_pack import find_files_by_name
from check_ticket_evidence import parse_frontmatter_map

VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v", ".webm", ".avi"}
VIDEO_REF_RE = re.compile(r"\b([A-Za-z0-9._/\-]+\.(?:mp4|mov|m4v|webm|avi))\b", re.IGNORECASE)
WALKTHROUGH_RE = re.compile(r"(walkthrough|playthrough|screen[-_ ]?record(?:ing)?|demo)", re.IGNORECASE)
STITCH_HINT_RE = re.compile(r"(stitch|runtime-vs-stitch|composition-anchor)", re.IGNORECASE)
REVIEW_DOC_HINT_RE = re.compile(
    r"(quality.?check|artifact polish|delivery review|phase gate|stitch gate|credibility gate|review pack|self review|qc)",
    re.IGNORECASE,
)
SNAPSHOT_TS_KEYS = ("captured", "updated", "completed", "created")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-file", required=True, help="Project markdown path.")
    parser.add_argument("--index-out", help="Optional explicit output path.")
    return parser.parse_args()


def now() -> str:
    return datetime.now().astimezone().strftime("%Y-%m-%dT%H:%M:%S %Z %z")


def default_video_index_path(project_file: Path) -> Path:
    return derived_dir(project_file) / "video-evidence-index.yaml"


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


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


def project_doc_timestamp(path: Path) -> str:
    data = parse_frontmatter_map(path)
    candidates = [parse_timestamp(data.get(key)) for key in SNAPSHOT_TS_KEYS]
    candidates = [candidate for candidate in candidates if candidate is not None]
    if not candidates:
        return ""
    return max(candidates).isoformat(timespec="seconds")


def is_review_like_doc(path: Path) -> bool:
    frontmatter = parse_frontmatter_map(path)
    signal = " ".join(
        [
            str(frontmatter.get("subtype", "")),
            str(frontmatter.get("review_type", "")),
            str(frontmatter.get("title", "")),
            path.name,
        ]
    )
    return bool(REVIEW_DOC_HINT_RE.search(signal))


def classify_video(path: Path, source_docs: list[str]) -> str:
    lower_name = path.name.lower()
    joined_docs = " ".join(source_docs).lower()
    if WALKTHROUGH_RE.search(lower_name):
        return "walkthrough"
    if STITCH_HINT_RE.search(lower_name) or STITCH_HINT_RE.search(joined_docs):
        return "stitch_demo"
    if REVIEW_DOC_HINT_RE.search(joined_docs):
        return "review_video"
    if "approval" in lower_name:
        return "approval_demo"
    return "project_video"


def resolve_video_reference(
    token: str,
    doc_path: Path,
    layout: dict[str, Any],
    platform_root: Path,
    filename_cache: dict[str, list[Path]],
) -> list[Path]:
    normalized = token.strip().strip("`").strip('"').strip("'")
    if not normalized:
        return []

    candidates: list[Path] = []
    token_path = Path(normalized)

    if token_path.is_absolute():
        candidates.append(token_path)
    else:
        candidates.append((doc_path.parent / normalized).resolve())
        candidates.append((Path(layout["snapshots_dir"]) / normalized).resolve())
        candidates.append((Path(layout["deliverables_root"]) / normalized).resolve())
        if normalized.startswith("vault/"):
            candidates.append((platform_root / normalized).resolve())

    basename = token_path.name
    if basename == normalized and basename not in filename_cache:
        filename_cache[basename] = [
            candidate.resolve()
            for candidate in (
                doc_path.parent / basename,
                Path(layout["snapshots_dir"]) / basename,
                Path(layout["deliverables_root"]) / basename,
            )
            if candidate.exists() and candidate.is_file()
        ]
    if basename == normalized:
        candidates.extend(filename_cache.get(basename, []))

    resolved: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        candidate = candidate.resolve()
        if candidate.suffix.lower() not in VIDEO_EXTENSIONS or not candidate.exists() or not candidate.is_file():
            continue
        key = str(candidate)
        if key in seen:
            continue
        seen.add(key)
        resolved.append(candidate)
    return resolved


def collect_source_docs(layout: dict[str, Any], project: str, project_file: Path) -> list[Path]:
    docs: list[Path] = [project_file.resolve()]
    docs.extend(collect_project_docs(Path(layout["snapshots_dir"]), project))
    docs.extend(collect_project_docs(Path(layout["decisions_dir"]), project))
    docs.extend(collect_project_docs(Path(layout["lessons_dir"]), project))
    tickets = collect_tickets(layout, project)
    docs.extend(Path(ticket["path"]).resolve() for ticket in tickets)

    ordered: list[Path] = []
    seen: set[str] = set()
    for path in docs:
        key = str(path.resolve())
        if key in seen or not path.exists():
            continue
        seen.add(key)
        ordered.append(path.resolve())
    return ordered


def collect_implicit_review_videos(source_docs: list[Path]) -> list[tuple[Path, Path]]:
    findings: list[tuple[Path, Path]] = []
    seen: set[str] = set()
    for doc_path in source_docs:
        if not is_review_like_doc(doc_path):
            continue
        for ext in VIDEO_EXTENSIONS:
            patterns = [f"qc-walkthrough-dashboard{ext}", f"qc-walkthrough{ext}"]
            for pattern in patterns:
                for candidate in sorted(doc_path.parent.glob(pattern)):
                    if not candidate.is_file():
                        continue
                    key = f"{candidate.resolve()}::{doc_path.resolve()}"
                    if key in seen:
                        continue
                    seen.add(key)
                    findings.append((candidate.resolve(), doc_path.resolve()))
    return findings


def probe_video_metadata(path: Path) -> dict[str, Any]:
    command = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=width,height,r_frame_rate,avg_frame_rate,codec_name:format=duration,size",
        "-of",
        "json",
        str(path),
    ]
    try:
        proc = subprocess.run(command, capture_output=True, text=True, check=True, timeout=15)
        data = json.loads(proc.stdout or "{}")
    except Exception:
        data = {}

    streams = data.get("streams") or []
    stream = streams[0] if streams else {}
    fmt = data.get("format") or {}

    def safe_float(value: object) -> float | None:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def safe_int(value: object) -> int | None:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    return {
        "duration_seconds": safe_float(fmt.get("duration")),
        "size_bytes": safe_int(fmt.get("size")) or path.stat().st_size if path.exists() else 0,
        "width": safe_int(stream.get("width")),
        "height": safe_int(stream.get("height")),
        "codec": str(stream.get("codec_name") or "").strip(),
        "avg_frame_rate": str(stream.get("avg_frame_rate") or stream.get("r_frame_rate") or "").strip(),
    }


def build_report(project_file: Path) -> dict[str, Any]:
    layout = discover_project_layout(project_file)
    platform_root = Path(layout["platform_root"])
    project = layout["project"]
    project_frontmatter = parse_frontmatter_map(project_file)
    source_docs = collect_source_docs(layout, project, project_file)
    filename_cache: dict[str, list[Path]] = {}

    video_sources: dict[str, dict[str, Any]] = {}

    def add_video(path: Path, source_doc: Path) -> None:
        path = path.resolve()
        if path.suffix.lower() not in VIDEO_EXTENSIONS or not path.exists() or not path.is_file():
            return
        key = str(path)
        rel_doc = relative_to_platform(source_doc, platform_root)
        entry = video_sources.setdefault(
            key,
            {
                "path": path,
                "source_docs": [],
                "source_doc_timestamps": [],
            },
        )
        if rel_doc not in entry["source_docs"]:
            entry["source_docs"].append(rel_doc)
        doc_ts = project_doc_timestamp(source_doc)
        if doc_ts and doc_ts not in entry["source_doc_timestamps"]:
            entry["source_doc_timestamps"].append(doc_ts)

    for doc_path in source_docs:
        text = read_text(doc_path)
        for match in VIDEO_REF_RE.finditer(text):
            for resolved in resolve_video_reference(match.group(1), doc_path, layout, platform_root, filename_cache):
                add_video(resolved, doc_path)

    for video_path, doc_path in collect_implicit_review_videos(source_docs):
        add_video(video_path, doc_path)

    videos: list[dict[str, Any]] = []
    for raw in video_sources.values():
        path = raw["path"]
        source_docs_rel = sorted(raw["source_docs"])
        captured = sorted(raw["source_doc_timestamps"])[-1] if raw["source_doc_timestamps"] else ""
        meta = probe_video_metadata(path)
        videos.append(
            {
                "path": relative_to_platform(path, platform_root),
                "filename": path.name,
                "category": classify_video(path, source_docs_rel),
                "captured_at": captured,
                "source_docs": source_docs_rel,
                "source_doc_count": len(source_docs_rel),
                "duration_seconds": meta.get("duration_seconds"),
                "size_bytes": meta.get("size_bytes", 0),
                "width": meta.get("width"),
                "height": meta.get("height"),
                "codec": meta.get("codec", ""),
                "avg_frame_rate": meta.get("avg_frame_rate", ""),
                "eligible_for_embedding": True,
            }
        )

    videos.sort(key=lambda item: (-item["source_doc_count"], item["category"], item["path"]))
    category_counts = dict(sorted(Counter(video["category"] for video in videos).items()))
    semantic_video_corpus = [video["path"] for video in videos]

    return {
        "generated_at": now(),
        "scope": layout["scope"],
        "client": layout["client"],
        "project": project,
        "title": str(project_frontmatter.get("title", project)).strip().strip('"'),
        "paths": {
            "project_file": relative_to_platform(project_file, platform_root),
            "snapshots_dir": relative_to_platform(Path(layout["snapshots_dir"]), platform_root),
            "deliverables_root": relative_to_platform(Path(layout["deliverables_root"]), platform_root),
            "video_evidence_index": relative_to_platform(default_video_index_path(project_file), platform_root),
        },
        "video_evidence": {
            "count": len(videos),
            "category_counts": category_counts,
            "videos": videos,
        },
        "evidence_docs": sorted({source_doc for video in videos for source_doc in video.get("source_docs", [])}),
        "semantic_video_corpus": semantic_video_corpus,
    }


def write_index(report: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(yaml.safe_dump(report, sort_keys=False, allow_unicode=False), encoding="utf-8")


def main() -> int:
    args = parse_args()
    project_file = Path(args.project_file).expanduser().resolve()
    report = build_report(project_file)
    output_path = Path(args.index_out).expanduser().resolve() if args.index_out else default_video_index_path(project_file)
    report["paths"]["video_evidence_index"] = relative_to_platform(output_path, Path(discover_project_layout(project_file)["platform_root"]))
    write_index(report, output_path)
    print(f"Wrote {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
