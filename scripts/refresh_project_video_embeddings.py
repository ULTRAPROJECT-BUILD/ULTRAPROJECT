#!/usr/bin/env python3
from __future__ import annotations

"""
Refresh project-scoped video embeddings only when the evidence manifest changed.

Videos are embedded through extracted keyframes plus project metadata. This keeps
the retrieval layer practical and cheap while still making walkthroughs and
recordings searchable.
"""

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from build_project_context import relative_to_platform
from build_project_video_evidence import default_video_index_path
from index_media import index_media

STATE_PATH = REPO_ROOT / "data" / "project_video_embedding_state.json"
KEYFRAME_ROOT = REPO_ROOT / "data" / "project_video_keyframes"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", help="Project video evidence manifest path.")
    parser.add_argument("--project-file", help="Project markdown path; manifest path will be derived automatically.")
    parser.add_argument("--force", action="store_true", help="Refresh even if the manifest digest is unchanged.")
    args = parser.parse_args()
    if bool(args.manifest) == bool(args.project_file):
        parser.error("Provide exactly one of --manifest or --project-file.")
    return args


def now() -> str:
    return datetime.now().astimezone().strftime("%Y-%m-%dT%H:%M:%S %Z %z")


def load_state() -> dict[str, Any]:
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_state(state: dict[str, Any]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_manifest_data(manifest_path: Path) -> tuple[dict[str, Any], str]:
    text = manifest_path.read_text(encoding="utf-8")
    data = yaml.safe_load(text) or {}
    if not isinstance(data, dict):
        data = {}
    return data, text


def file_fingerprint(path: Path) -> str:
    try:
        stat = path.stat()
    except OSError:
        return "missing"
    return f"{stat.st_mtime_ns}:{stat.st_size}"


def manifest_digest(manifest_text: str, video_paths: list[Path]) -> str:
    payload = {
        "manifest": manifest_text,
        "videos": {str(path): file_fingerprint(path) for path in video_paths},
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def format_timestamp_label(seconds: float) -> str:
    rounded = max(0, int(seconds))
    minutes, secs = divmod(rounded, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def choose_timestamps(duration_seconds: float | None, max_frames: int = 6) -> list[float]:
    if not duration_seconds or duration_seconds <= 0:
        return [0.0]
    if duration_seconds <= 4:
        frame_count = 2
    elif duration_seconds <= 12:
        frame_count = 4
    elif duration_seconds <= 30:
        frame_count = 6
    else:
        frame_count = max_frames
    frame_count = max(1, min(max_frames, frame_count))
    timestamps = [duration_seconds * (idx + 1) / (frame_count + 1) for idx in range(frame_count)]
    upper_bound = max(0.0, duration_seconds - 0.1)
    return [round(min(max(0.0, ts), upper_bound), 3) for ts in timestamps]


def extract_keyframes(video_path: Path, output_dir: Path, *, duration_seconds: float | None = None) -> list[dict[str, Any]]:
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamps = choose_timestamps(duration_seconds)
    frames: list[dict[str, Any]] = []
    for idx, seconds in enumerate(timestamps, start=1):
        output_path = output_dir / f"frame-{idx:02d}-{int(seconds * 1000):06d}ms.png"
        command = [
            "ffmpeg",
            "-y",
            "-ss",
            f"{seconds:.3f}",
            "-i",
            str(video_path),
            "-frames:v",
            "1",
            str(output_path),
        ]
        subprocess.run(command, capture_output=True, check=True)
        if output_path.exists():
            frames.append(
                {
                    "path": output_path.resolve(),
                    "timestamp_seconds": seconds,
                    "timestamp_label": format_timestamp_label(seconds),
                }
            )

    if not frames:
        fallback_path = output_dir / "frame-01-000000ms.png"
        command = [
            "ffmpeg",
            "-y",
            "-i",
            str(video_path),
            "-frames:v",
            "1",
            str(fallback_path),
        ]
        subprocess.run(command, capture_output=True, check=True)
        if fallback_path.exists():
            frames.append(
                {
                    "path": fallback_path.resolve(),
                    "timestamp_seconds": 0.0,
                    "timestamp_label": "00:00",
                }
            )
    return frames


def refresh_project_video_embeddings(manifest_path: Path, *, force: bool = False) -> dict[str, Any]:
    manifest_path = manifest_path.expanduser().resolve()
    manifest_data, manifest_text = load_manifest_data(manifest_path)
    videos = ((manifest_data.get("video_evidence") or {}).get("videos") or [])
    video_paths = [(REPO_ROOT / str(video.get("path", ""))).resolve() for video in videos if str(video.get("path", "")).strip()]
    digest = manifest_digest(manifest_text, video_paths)
    manifest_key = relative_to_platform(manifest_path, REPO_ROOT)
    state = load_state()
    previous = state.get(manifest_key, {})

    project = str(manifest_data.get("project") or "").strip()
    client = str(manifest_data.get("client") or "").strip()

    if not force and previous.get("digest") == digest:
        return {
            "status": "noop",
            "reason": "unchanged",
            "project": project,
            "client": client,
            "video_count": len(videos),
            "manifest": manifest_key,
        }

    if not videos:
        state[manifest_key] = {
            "digest": digest,
            "updated_at": now(),
            "project": project,
            "client": client,
            "video_count": 0,
            "keyframe_count": 0,
            "last_status": "no_videos",
        }
        save_state(state)
        return {
            "status": "noop",
            "reason": "no_videos",
            "project": project,
            "client": client,
            "video_count": 0,
            "manifest": manifest_key,
        }

    target_paths: list[Path] = []
    target_metadata: dict[str, dict[str, Any]] = {}
    generated_keyframes: list[str] = []

    for video in videos:
        raw_video_path = str(video.get("path", "")).strip()
        if not raw_video_path:
            continue
        video_path = (REPO_ROOT / raw_video_path).resolve()
        if not video_path.exists():
            continue
        video_hash = hashlib.sha256(f"{raw_video_path}:{file_fingerprint(video_path)}".encode("utf-8")).hexdigest()[:12]
        output_dir = KEYFRAME_ROOT / (project or "project") / f"{video_path.stem}-{video_hash}"
        frames = extract_keyframes(video_path, output_dir, duration_seconds=video.get("duration_seconds"))
        source_docs = ", ".join(video.get("source_docs") or [])
        for frame in frames:
            frame_path = Path(frame["path"]).resolve()
            rel_frame = relative_to_platform(frame_path, REPO_ROOT)
            target_paths.append(frame_path)
            generated_keyframes.append(rel_frame)
            target_metadata[rel_frame] = {
                "project": project,
                "client": client,
                "evidence_category": "video_keyframe",
                "source_docs": source_docs,
                "media_kind": "video",
                "source_video": raw_video_path,
                "source_video_category": str(video.get("category") or "").strip(),
                "timestamp_seconds": float(frame.get("timestamp_seconds") or 0.0),
                "timestamp_label": str(frame.get("timestamp_label") or "").strip(),
            }

    if not target_paths:
        state[manifest_key] = {
            "digest": digest,
            "updated_at": now(),
            "project": project,
            "client": client,
            "video_count": len(videos),
            "keyframe_count": 0,
            "last_status": "no_keyframes",
        }
        save_state(state)
        return {
            "status": "noop",
            "reason": "no_keyframes",
            "project": project,
            "client": client,
            "video_count": len(videos),
            "manifest": manifest_key,
        }

    stats = index_media(full=False, target_paths=target_paths, target_metadata=target_metadata)
    state[manifest_key] = {
        "digest": digest,
        "updated_at": now(),
        "project": project,
        "client": client,
        "video_count": len(videos),
        "keyframe_count": len(target_paths),
        "generated_keyframes": generated_keyframes,
        "last_status": "refreshed",
        "stats": stats,
    }
    save_state(state)
    return {
        "status": "refreshed",
        "project": project,
        "client": client,
        "video_count": len(videos),
        "keyframe_count": len(target_paths),
        "manifest": manifest_key,
        "stats": stats,
    }


def main() -> int:
    args = parse_args()
    manifest_path = (
        Path(args.manifest)
        if args.manifest
        else default_video_index_path(Path(args.project_file).expanduser().resolve())
    )
    result = refresh_project_video_embeddings(manifest_path, force=args.force)
    if result["status"] == "refreshed":
        stats = result.get("stats") or {}
        print(
            "Refreshed video embeddings for "
            f"{result.get('project') or 'project'} "
            f"({result.get('keyframe_count', 0)} keyframes, {stats.get('added', 0)} added, {stats.get('updated', 0)} updated, {stats.get('skipped', 0)} skipped)."
        )
    else:
        print(
            "Skipped video embedding refresh for "
            f"{result.get('project') or 'project'} "
            f"({result.get('reason', 'noop')})."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
