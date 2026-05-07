#!/usr/bin/env python3
from __future__ import annotations

"""
Refresh project-scoped text embeddings from an artifact-index semantic corpus.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from build_project_context import default_index_path
from project_text_retrieval import (
    REPO_ROOT,
    corpus_digest,
    load_target_manifest,
    now,
    relative_to_platform,
    index_project_text_corpus,
)

STATE_PATH = REPO_ROOT / "data" / "project_text_embedding_state.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", help="Artifact index manifest path.")
    parser.add_argument("--project-file", help="Project markdown path; artifact index path will be derived automatically.")
    parser.add_argument("--force", action="store_true", help="Refresh even if the corpus digest is unchanged.")
    args = parser.parse_args()
    if bool(args.manifest) == bool(args.project_file):
        parser.error("Provide exactly one of --manifest or --project-file.")
    return args


def load_state() -> dict[str, Any]:
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_state(state: dict[str, Any]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def refresh_project_text_embeddings(manifest_path: Path, *, force: bool = False) -> dict[str, Any]:
    manifest_path = manifest_path.expanduser().resolve()
    target_paths, _target_metadata, manifest_data, manifest_text = load_target_manifest(manifest_path)
    digest = corpus_digest(manifest_text, target_paths)
    manifest_key = relative_to_platform(manifest_path)
    state = load_state()
    previous = state.get(manifest_key, {})
    project = str(manifest_data.get("project") or "").strip()
    client = str(manifest_data.get("client") or "").strip()
    semantic_corpus = manifest_data.get("semantic_corpus") or []

    if not force and previous.get("digest") == digest:
        return {
            "status": "noop",
            "reason": "unchanged",
            "project": project,
            "client": client,
            "manifest": manifest_key,
            "semantic_corpus_count": len(semantic_corpus),
        }

    if not semantic_corpus:
        state[manifest_key] = {
            "digest": digest,
            "updated_at": now(),
            "project": project,
            "client": client,
            "semantic_corpus_count": 0,
            "last_status": "no_text_corpus",
        }
        save_state(state)
        return {
            "status": "noop",
            "reason": "no_text_corpus",
            "project": project,
            "client": client,
            "manifest": manifest_key,
            "semantic_corpus_count": 0,
        }

    stats = index_project_text_corpus(manifest_path)
    state[manifest_key] = {
        "digest": digest,
        "updated_at": now(),
        "project": project,
        "client": client,
        "semantic_corpus_count": len(semantic_corpus),
        "last_status": "refreshed",
        "stats": stats,
    }
    save_state(state)
    return {
        "status": "refreshed",
        "project": project,
        "client": client,
        "manifest": manifest_key,
        "semantic_corpus_count": len(semantic_corpus),
        "stats": stats,
    }


def main() -> int:
    args = parse_args()
    manifest_path = (
        Path(args.manifest)
        if args.manifest
        else default_index_path(Path(args.project_file).expanduser().resolve())
    )
    result = refresh_project_text_embeddings(manifest_path, force=args.force)
    if result["status"] == "refreshed":
        stats = result.get("stats") or {}
        print(
            "Refreshed text embeddings for "
            f"{result.get('project') or 'project'} "
            f"({stats.get('added', 0)} added, {stats.get('updated', 0)} updated, "
            f"{stats.get('removed', 0)} removed, {stats.get('skipped', 0)} skipped)."
        )
    else:
        print(
            "Skipped text embedding refresh for "
            f"{result.get('project') or 'project'} "
            f"({result.get('reason', 'noop')})."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
