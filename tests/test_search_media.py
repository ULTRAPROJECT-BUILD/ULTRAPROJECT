from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "search_media.py"


def load_module(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def test_search_media_logs_usage_event(tmp_path, monkeypatch):
    module = load_module("search_media_under_test", SCRIPT_PATH)

    class FakeCollection:
        def query(self, query_embeddings, n_results, where, include):
            return {
                "ids": [["doc-1"]],
                "metadatas": [[
                    {
                        "path": "vault/clients/acme/snapshots/qc-screenshot-dashboard.png",
                        "client": "acme",
                        "project": "sample-project",
                        "evidence_category": "qc_screenshot",
                        "description": "Dashboard screenshot",
                        "media_kind": "image",
                    }
                ]],
                "distances": [[0.1]],
            }

    monkeypatch.setattr(module, "_get_collection", lambda: FakeCollection())
    monkeypatch.setattr(module, "embed_text", lambda text: [0.1, 0.2, 0.3])
    monkeypatch.setattr(module, "RETRIEVAL_USAGE_DIR", tmp_path / "logs" / "retrieval")
    monkeypatch.setenv("AGENT_PLATFORM_TICKET_ID", "T-705")
    monkeypatch.setenv("AGENT_PLATFORM_TASK_TYPE", "stress_test")

    results = module.search(
        "dashboard screenshot",
        top_k=5,
        client_filter="acme",
        project_filter="sample-project",
        media_kind_filter="image",
    )

    assert len(results) == 1
    assert results[0]["project"] == "sample-project"

    log_files = list((tmp_path / "logs" / "retrieval").glob("retrieval-*.jsonl"))
    assert len(log_files) == 1
    event = json.loads(log_files[0].read_text(encoding="utf-8").strip())
    assert event["kind"] == "media_search"
    assert event["ticket_id"] == "T-705"
    assert event["task_type"] == "stress_test"
    assert event["project"] == "sample-project"
    assert event["result_count"] == 1
