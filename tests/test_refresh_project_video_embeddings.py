from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "refresh_project_video_embeddings.py"


def load_module(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def write_manifest(path: Path, *, project: str = "sample-project", client: str = "acme", video_paths: list[str] | None = None) -> None:
    video_paths = video_paths or []
    path.write_text(
        yaml.safe_dump(
            {
                "project": project,
                "client": client,
                "video_evidence": {
                    "videos": [
                        {
                            "path": raw_path,
                            "category": "walkthrough",
                            "source_docs": [f"vault/clients/{client}/snapshots/2026-01-04-quality-check-{project}.md"],
                            "duration_seconds": 9.76,
                        }
                        for raw_path in video_paths
                    ]
                },
                "semantic_video_corpus": video_paths,
            },
            sort_keys=False,
            allow_unicode=False,
        ),
        encoding="utf-8",
    )


def test_refresh_project_video_embeddings_noops_when_manifest_unchanged(tmp_path, monkeypatch):
    module = load_module("refresh_project_video_embeddings_noop_under_test", SCRIPT_PATH)
    repo_root = tmp_path / "platform"
    manifest_path = repo_root / "sample-project.video-evidence-index.yaml"
    video_path = repo_root / "vault" / "clients" / "acme" / "snapshots" / "walkthrough.webm"
    video_path.parent.mkdir(parents=True, exist_ok=True)
    video_path.write_bytes(b"video")
    write_manifest(
        manifest_path,
        video_paths=["vault/clients/acme/snapshots/walkthrough.webm"],
    )

    module.REPO_ROOT = repo_root
    module.STATE_PATH = tmp_path / "project_video_embedding_state.json"

    digest = module.manifest_digest(manifest_path.read_text(encoding="utf-8"), [video_path.resolve()])
    manifest_key = module.relative_to_platform(manifest_path, module.REPO_ROOT)
    module.save_state({manifest_key: {"digest": digest, "updated_at": "2026-01-04T09:00:00 EST -0500"}})

    called = {"value": False}

    def fake_index_media(*args, **kwargs):
        called["value"] = True
        return {"added": 1, "updated": 0, "skipped": 0, "errors": 0}

    monkeypatch.setattr(module, "index_media", fake_index_media)
    result = module.refresh_project_video_embeddings(manifest_path)

    assert result["status"] == "noop"
    assert result["reason"] == "unchanged"
    assert called["value"] is False


def test_refresh_project_video_embeddings_refreshes_and_writes_state(tmp_path, monkeypatch):
    module = load_module("refresh_project_video_embeddings_refresh_under_test", SCRIPT_PATH)
    repo_root = tmp_path / "platform"
    manifest_path = repo_root / "sample-project.video-evidence-index.yaml"
    video_path = repo_root / "vault" / "clients" / "acme" / "snapshots" / "walkthrough.webm"
    video_path.parent.mkdir(parents=True, exist_ok=True)
    video_path.write_bytes(b"video")
    write_manifest(
        manifest_path,
        video_paths=["vault/clients/acme/snapshots/walkthrough.webm"],
    )

    module.REPO_ROOT = repo_root
    module.STATE_PATH = tmp_path / "project_video_embedding_state.json"
    module.KEYFRAME_ROOT = tmp_path / "project_video_keyframes"

    def fake_extract(video: Path, output_dir: Path, *, duration_seconds=None):
        output_dir.mkdir(parents=True, exist_ok=True)
        frame_path = output_dir / "frame-01-000500ms.png"
        frame_path.write_bytes(b"frame")
        return [{"path": frame_path, "timestamp_seconds": 0.5, "timestamp_label": "00:00"}]

    monkeypatch.setattr(module, "extract_keyframes", fake_extract)
    monkeypatch.setattr(
        module,
        "index_media",
        lambda **kwargs: {"added": 1, "updated": 0, "skipped": 0, "errors": 0},
    )

    result = module.refresh_project_video_embeddings(manifest_path)

    assert result["status"] == "refreshed"
    assert result["project"] == "sample-project"
    saved = json.loads(module.STATE_PATH.read_text(encoding="utf-8"))
    manifest_key = module.relative_to_platform(manifest_path, module.REPO_ROOT)
    assert saved[manifest_key]["project"] == "sample-project"
    assert saved[manifest_key]["client"] == "acme"
    assert saved[manifest_key]["video_count"] == 1
    assert saved[manifest_key]["keyframe_count"] == 1
    assert saved[manifest_key]["last_status"] == "refreshed"


def test_parse_args_accepts_project_file_mode(tmp_path, monkeypatch):
    module = load_module("refresh_project_video_embeddings_parse_under_test", SCRIPT_PATH)
    project_file = tmp_path / "sample-project.md"
    project_file.write_text("# Sample Project\n", encoding="utf-8")

    monkeypatch.setattr(sys, "argv", ["refresh_project_video_embeddings.py", "--project-file", str(project_file)])
    args = module.parse_args()

    assert args.project_file == str(project_file)
    assert args.manifest is None
