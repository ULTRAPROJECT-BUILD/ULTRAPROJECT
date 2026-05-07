from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "refresh_project_image_embeddings.py"


def load_module(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def write_manifest(path: Path, *, project: str = "sample-project", client: str = "acme", image_paths: list[str] | None = None) -> None:
    image_paths = image_paths or []
    path.write_text(
        yaml.safe_dump(
            {
                "project": project,
                "client": client,
                "image_evidence": {
                    "images": [
                        {
                            "path": raw_path,
                            "category": "qc_screenshot",
                            "source_docs": [f"vault/clients/{client}/snapshots/2026-01-04-quality-check-{project}.md"],
                        }
                        for raw_path in image_paths
                    ]
                },
                "semantic_image_corpus": image_paths,
            },
            sort_keys=False,
            allow_unicode=False,
        ),
        encoding="utf-8",
    )


def test_refresh_project_image_embeddings_noops_when_manifest_unchanged(tmp_path, monkeypatch):
    module = load_module("refresh_project_image_embeddings_noop_under_test", SCRIPT_PATH)
    manifest_path = tmp_path / "sample-project.image-evidence-index.yaml"
    write_manifest(
        manifest_path,
        image_paths=["vault/clients/acme/snapshots/qc-screenshot-dashboard-health.png"],
    )

    module.STATE_PATH = tmp_path / "project_image_embedding_state.json"
    digest = module.manifest_digest(manifest_path.read_text(encoding="utf-8"))
    module.save_state(
        {
            str(manifest_path): {
                "digest": digest,
                "updated_at": "2026-01-04T09:00:00 EST -0500",
            }
        }
    )

    called = {"value": False}

    def fake_index_media(*args, **kwargs):
        called["value"] = True
        return {"added": 1, "updated": 0, "skipped": 0, "errors": 0}

    monkeypatch.setattr(module, "index_media", fake_index_media)
    result = module.refresh_project_image_embeddings(manifest_path)

    assert result["status"] == "noop"
    assert result["reason"] == "unchanged"
    assert called["value"] is False


def test_refresh_project_image_embeddings_refreshes_and_writes_state(tmp_path, monkeypatch):
    module = load_module("refresh_project_image_embeddings_refresh_under_test", SCRIPT_PATH)
    manifest_path = tmp_path / "sample-project.image-evidence-index.yaml"
    write_manifest(
        manifest_path,
        image_paths=["vault/clients/acme/snapshots/qc-screenshot-dashboard-health.png"],
    )

    module.STATE_PATH = tmp_path / "project_image_embedding_state.json"

    def fake_load_target_manifest(path: Path):
        assert path == manifest_path.resolve()
        return [REPO_ROOT / "vault" / "clients" / "acme" / "snapshots" / "qc-screenshot-dashboard-health.png"], {
            "vault/clients/acme/snapshots/qc-screenshot-dashboard-health.png": {
                "project": "sample-project",
                "client": "acme",
                "evidence_category": "qc_screenshot",
            }
        }

    monkeypatch.setattr(module, "load_target_manifest", fake_load_target_manifest)
    monkeypatch.setattr(
        module,
        "index_media",
        lambda **kwargs: {"added": 1, "updated": 0, "skipped": 0, "errors": 0},
    )

    result = module.refresh_project_image_embeddings(manifest_path)

    assert result["status"] == "refreshed"
    assert result["project"] == "sample-project"
    saved = json.loads(module.STATE_PATH.read_text(encoding="utf-8"))
    manifest_key = str(manifest_path)
    assert saved[manifest_key]["project"] == "sample-project"
    assert saved[manifest_key]["client"] == "acme"
    assert saved[manifest_key]["image_count"] == 1
    assert saved[manifest_key]["last_status"] == "refreshed"


def test_parse_args_accepts_project_file_mode(tmp_path, monkeypatch):
    module = load_module("refresh_project_image_embeddings_parse_under_test", SCRIPT_PATH)
    project_file = tmp_path / "sample-project.md"
    project_file.write_text("# Sample Project\n", encoding="utf-8")

    monkeypatch.setattr(sys, "argv", ["refresh_project_image_embeddings.py", "--project-file", str(project_file)])
    args = module.parse_args()

    assert args.project_file == str(project_file)
    assert args.manifest is None
