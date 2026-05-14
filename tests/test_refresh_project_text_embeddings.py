from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "refresh_project_text_embeddings.py"


def load_module(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def write_manifest(path: Path, *, project: str = "sample-project", client: str = "acme", semantic_corpus: list[str] | None = None) -> None:
    semantic_corpus = semantic_corpus or []
    path.write_text(
        yaml.safe_dump(
            {
                "project": project,
                "client": client,
                "semantic_corpus": semantic_corpus,
            },
            sort_keys=False,
            allow_unicode=False,
        ),
        encoding="utf-8",
    )


def test_refresh_project_text_embeddings_noops_when_corpus_unchanged(tmp_path, monkeypatch):
    module = load_module("refresh_project_text_embeddings_noop_under_test", SCRIPT_PATH)
    corpus_file = tmp_path / "note.md"
    corpus_file.write_text("# Note\n\nUseful content.\n", encoding="utf-8")
    manifest_path = tmp_path / "sample-project.artifact-index.yaml"
    write_manifest(manifest_path, semantic_corpus=[str(corpus_file)])

    module.STATE_PATH = tmp_path / "project_text_embedding_state.json"
    target_paths, _target_metadata, _manifest_data, manifest_text = module.load_target_manifest(manifest_path)
    digest = module.corpus_digest(manifest_text, target_paths)
    module.save_state(
        {
            str(manifest_path): {
                "digest": digest,
                "updated_at": "2026-04-13T12:00:00 EDT -0400",
            }
        }
    )

    called = {"value": False}

    def fake_index_project_text_corpus(_manifest_path: Path):
        called["value"] = True
        return {"added": 1}

    monkeypatch.setattr(module, "index_project_text_corpus", fake_index_project_text_corpus)
    result = module.refresh_project_text_embeddings(manifest_path)

    assert result["status"] == "noop"
    assert result["reason"] == "unchanged"
    assert called["value"] is False


def test_refresh_project_text_embeddings_refreshes_when_corpus_file_changes(tmp_path, monkeypatch):
    module = load_module("refresh_project_text_embeddings_refresh_under_test", SCRIPT_PATH)
    corpus_file = tmp_path / "note.md"
    corpus_file.write_text("# Note\n\nOld content.\n", encoding="utf-8")
    manifest_path = tmp_path / "sample-project.artifact-index.yaml"
    write_manifest(manifest_path, semantic_corpus=[str(corpus_file)])

    module.STATE_PATH = tmp_path / "project_text_embedding_state.json"
    target_paths, _target_metadata, _manifest_data, manifest_text = module.load_target_manifest(manifest_path)
    old_digest = module.corpus_digest(manifest_text, target_paths)
    module.save_state({str(manifest_path): {"digest": old_digest}})
    corpus_file.write_text("# Note\n\nNew content after edit.\n", encoding="utf-8")

    monkeypatch.setattr(
        module,
        "index_project_text_corpus",
        lambda _manifest_path: {"added": 0, "updated": 1, "removed": 0, "skipped": 0, "errors": 0},
    )
    result = module.refresh_project_text_embeddings(manifest_path)

    assert result["status"] == "refreshed"
    saved = json.loads(module.STATE_PATH.read_text(encoding="utf-8"))
    assert saved[str(manifest_path)]["last_status"] == "refreshed"
    assert saved[str(manifest_path)]["semantic_corpus_count"] == 1


def test_parse_args_accepts_project_file_mode(tmp_path, monkeypatch):
    module = load_module("refresh_project_text_embeddings_parse_under_test", SCRIPT_PATH)
    project_file = tmp_path / "sample-project.md"
    project_file.write_text("# Sample Project\n", encoding="utf-8")

    monkeypatch.setattr(sys, "argv", ["refresh_project_text_embeddings.py", "--project-file", str(project_file)])
    args = module.parse_args()

    assert args.project_file == str(project_file)
    assert args.manifest is None
