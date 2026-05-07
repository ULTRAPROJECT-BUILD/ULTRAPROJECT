#!/usr/bin/env python3
from __future__ import annotations

"""
Refresh project-scoped image embeddings only when the evidence manifest changed.
"""

import argparse
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from build_project_image_evidence import default_image_index_path
from build_project_context import relative_to_platform
from index_media import index_media, load_target_manifest

STATE_PATH = REPO_ROOT / "data" / "project_image_embedding_state.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", help="Project image evidence manifest path.")
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


def manifest_digest(manifest_text: str) -> str:
    return hashlib.sha256(manifest_text.encode("utf-8")).hexdigest()


def load_manifest_data(manifest_path: Path) -> tuple[dict[str, Any], str]:
    text = manifest_path.read_text(encoding="utf-8")
    data = yaml.safe_load(text) or {}
    if not isinstance(data, dict):
        data = {}
    return data, text


def refresh_project_image_embeddings(manifest_path: Path, *, force: bool = False) -> dict[str, Any]:
    manifest_path = manifest_path.expanduser().resolve()
    manifest_data, manifest_text = load_manifest_data(manifest_path)
    digest = manifest_digest(manifest_text)
    manifest_key = relative_to_platform(manifest_path, REPO_ROOT)
    state = load_state()
    previous = state.get(manifest_key, {})

    images = ((manifest_data.get("image_evidence") or {}).get("images") or [])
    semantic_corpus = manifest_data.get("semantic_image_corpus") or []
    project = str(manifest_data.get("project") or "").strip()
    client = str(manifest_data.get("client") or "").strip()

    if not force and previous.get("digest") == digest:
        return {
            "status": "noop",
            "reason": "unchanged",
            "project": project,
            "client": client,
            "image_count": len(images),
            "manifest": manifest_key,
        }

    if not images:
        state[manifest_key] = {
            "digest": digest,
            "updated_at": now(),
            "project": project,
            "client": client,
            "image_count": 0,
            "semantic_corpus_count": 0,
            "last_status": "no_images",
        }
        save_state(state)
        return {
            "status": "noop",
            "reason": "no_images",
            "project": project,
            "client": client,
            "image_count": 0,
            "manifest": manifest_key,
        }

    target_paths, target_metadata = load_target_manifest(manifest_path)
    stats = index_media(full=False, target_paths=target_paths, target_metadata=target_metadata)
    state[manifest_key] = {
        "digest": digest,
        "updated_at": now(),
        "project": project,
        "client": client,
        "image_count": len(images),
        "semantic_corpus_count": len(semantic_corpus),
        "last_status": "refreshed",
        "stats": stats,
    }
    save_state(state)
    return {
        "status": "refreshed",
        "project": project,
        "client": client,
        "image_count": len(images),
        "manifest": manifest_key,
        "stats": stats,
    }


def main() -> int:
    args = parse_args()
    manifest_path = (
        Path(args.manifest)
        if args.manifest
        else default_image_index_path(Path(args.project_file).expanduser().resolve())
    )
    result = refresh_project_image_embeddings(manifest_path, force=args.force)
    if result["status"] == "refreshed":
        stats = result.get("stats") or {}
        print(
            "Refreshed image embeddings for "
            f"{result.get('project') or 'project'} "
            f"({stats.get('added', 0)} added, {stats.get('updated', 0)} updated, {stats.get('skipped', 0)} skipped)."
        )
    else:
        print(
            "Skipped image embedding refresh for "
            f"{result.get('project') or 'project'} "
            f"({result.get('reason', 'noop')})."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
