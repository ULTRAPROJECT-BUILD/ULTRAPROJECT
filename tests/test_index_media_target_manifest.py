from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
INDEX_MEDIA_PATH = REPO_ROOT / "scripts" / "index_media.py"


def load_module(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def test_load_target_manifest_reads_project_image_index(tmp_path):
    module = load_module("index_media_manifest_under_test", INDEX_MEDIA_PATH)
    manifest_path = tmp_path / "sample-project.image-evidence-index.yaml"
    manifest_path.write_text(
        yaml.safe_dump(
            {
                "project": "sample-project",
                "client": "acme",
                "image_evidence": {
                    "images": [
                        {
                            "path": "vault/clients/acme/snapshots/qc-screenshot-dashboard-health.png",
                            "category": "qc_screenshot",
                            "source_docs": ["vault/clients/acme/snapshots/2026-01-04-quality-check-sample-project.md"],
                        }
                    ]
                },
                "semantic_image_corpus": ["vault/clients/acme/snapshots/qc-screenshot-dashboard-health.png"],
            },
            sort_keys=False,
            allow_unicode=False,
        ),
        encoding="utf-8",
    )

    paths, metadata = module.load_target_manifest(manifest_path)

    assert len(paths) == 1
    assert paths[0] == (REPO_ROOT / "vault" / "clients" / "acme" / "snapshots" / "qc-screenshot-dashboard-health.png").resolve()
    assert metadata["vault/clients/acme/snapshots/qc-screenshot-dashboard-health.png"]["project"] == "sample-project"
    assert metadata["vault/clients/acme/snapshots/qc-screenshot-dashboard-health.png"]["client"] == "acme"
    assert metadata["vault/clients/acme/snapshots/qc-screenshot-dashboard-health.png"]["evidence_category"] == "qc_screenshot"
