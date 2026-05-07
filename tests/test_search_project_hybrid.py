from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "search_project_hybrid.py"


def load_module(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def test_search_project_hybrid_combines_exact_text_and_image_results(tmp_path, monkeypatch):
    module = load_module("search_project_hybrid_under_test", SCRIPT_PATH)
    derived_dir = tmp_path / "sample-project.derived"
    derived_dir.mkdir(parents=True, exist_ok=True)
    artifact_index = derived_dir / "artifact-index.yaml"
    image_index = derived_dir / "image-evidence-index.yaml"
    video_index = derived_dir / "video-evidence-index.yaml"

    artifact_index.write_text(
        yaml.safe_dump(
            {
                "project": "sample-project",
                "client": "acme",
                "title": "Sample Project",
                "goal": "Build something good.",
                "status": "active",
                "current_phase_display": 1,
                "total_phases": 4,
                "current_phase_title": "Design",
                "current_wave": "Wave 1",
                "authoritative_files": [
                    "vault/clients/acme/projects/sample-project.md",
                    "vault/clients/acme/snapshots/2026-04-13-project-plan-sample-project.md",
                ],
                "tickets": {"active": [{"id": "T-001"}], "blocked": []},
                "assumptions": {"active": [{"ID": "A-1"}]},
                "reviews": {
                    "current_review": {
                        "kind_label": "Delivery Review",
                        "grade": "B",
                        "path": "vault/clients/acme/snapshots/2026-04-13-delivery-review-sample-project.md",
                    }
                },
                "paths": {
                    "current_context": "vault/clients/acme/projects/sample-project.derived/current-context.md",
                    "artifact_index": "vault/clients/acme/projects/sample-project.derived/artifact-index.yaml",
                    "image_evidence_index": "vault/clients/acme/projects/sample-project.derived/image-evidence-index.yaml",
                    "video_evidence_index": "vault/clients/acme/projects/sample-project.derived/video-evidence-index.yaml",
                },
            },
            sort_keys=False,
            allow_unicode=False,
        ),
        encoding="utf-8",
    )
    image_index.write_text(
        yaml.safe_dump(
            {
                "project": "sample-project",
                "client": "acme",
                "image_evidence": {
                    "images": [
                        {"path": "vault/clients/acme/snapshots/qc-screenshot-dashboard.png", "category": "qc_screenshot"}
                    ]
                },
            },
            sort_keys=False,
            allow_unicode=False,
        ),
        encoding="utf-8",
    )
    video_index.write_text(
        yaml.safe_dump(
            {
                "project": "sample-project",
                "client": "acme",
                "video_evidence": {
                    "videos": [
                        {"path": "vault/clients/acme/snapshots/qc-walkthrough-dashboard.webm", "category": "walkthrough"}
                    ]
                },
            },
            sort_keys=False,
            allow_unicode=False,
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        module,
        "search_project_text",
        lambda query, manifest_path, top_k=6: {
            "query": query,
            "results": [
                {
                    "path": "vault/clients/acme/snapshots/2026-04-13-project-plan-sample-project.md",
                    "similarity": 0.91,
                    "title": "Plan",
                    "type": "snapshot",
                    "preview": "Preview",
                }
            ],
        },
    )
    def fake_search_media(query, top_k=4, client_filter="", project_filter="", media_kind_filter="", category_prefix=""):
        if media_kind_filter == "video":
            return [
                {
                    "path": "data/project_video_keyframes/sample-project/frame-01.png",
                    "similarity": 0.86,
                    "project": project_filter,
                    "source_video": "vault/clients/acme/snapshots/qc-walkthrough-dashboard.webm",
                    "timestamp_label": "00:03",
                }
            ]
        return [
            {
                "path": "vault/clients/acme/snapshots/qc-screenshot-dashboard.png",
                "similarity": 0.88,
                "project": project_filter,
            }
        ]

    monkeypatch.setattr(module, "search_media", fake_search_media)

    result = module.search_project_hybrid(
        "dashboard proof",
        artifact_index_path=artifact_index,
        top_text=5,
        top_images=3,
    )

    assert result["project"] == "sample-project"
    assert result["exact_context"]["phase"] == "Phase 1/4 — Design"
    assert result["exact_context"]["current_review"]["kind"] == "Delivery Review"
    assert len(result["text_results"]) == 1
    assert len(result["image_results"]) == 1
    assert len(result["video_results"]) == 1
    assert result["counts"]["authoritative_files"] == 2
    assert result["counts"]["video_results"] == 1


def test_search_project_hybrid_logs_usage_event(tmp_path, monkeypatch):
    module = load_module("search_project_hybrid_logging_under_test", SCRIPT_PATH)
    derived_dir = tmp_path / "sample-project.derived"
    derived_dir.mkdir(parents=True, exist_ok=True)
    artifact_index = derived_dir / "artifact-index.yaml"
    artifact_index.write_text(
        yaml.safe_dump(
            {
                "project": "sample-project",
                "client": "acme",
                "title": "Sample Project",
                "status": "active",
                "paths": {},
                "tickets": {"active": [], "blocked": []},
                "assumptions": {"active": []},
                "reviews": {},
            },
            sort_keys=False,
            allow_unicode=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "RETRIEVAL_USAGE_DIR", tmp_path / "logs" / "retrieval")
    monkeypatch.setattr(module, "search_project_text", lambda query, manifest_path, top_k=6: {"query": query, "results": []})
    monkeypatch.setattr(module, "search_media", lambda *args, **kwargs: [])
    monkeypatch.setenv("AGENT_PLATFORM_TICKET_ID", "T-123")
    monkeypatch.setenv("AGENT_PLATFORM_TASK_TYPE", "quality_check")

    result = module.search_project_hybrid("route family parity", artifact_index_path=artifact_index)

    assert result["counts"]["text_results"] == 0
    log_files = list((tmp_path / "logs" / "retrieval").glob("retrieval-*.jsonl"))
    assert len(log_files) == 1
    lines = log_files[0].read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    event = json.loads(lines[0])
    assert event["kind"] == "project_hybrid_search"
    assert event["ticket_id"] == "T-123"
    assert event["task_type"] == "quality_check"
    assert event["project"] == "sample-project"
