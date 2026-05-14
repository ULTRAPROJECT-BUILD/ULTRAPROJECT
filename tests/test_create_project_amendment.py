from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "create_project_amendment.py"


def load_module():
    spec = importlib.util.spec_from_file_location("create_project_amendment_under_test", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def write_markdown(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_classify_request_covers_change_control_buckets():
    module = load_module()

    assert module.classify_request("Fix the wording on the approvals button and tighten spacing.")[0] == "minor_ticket_delta"
    assert module.classify_request("Also add a new review surface and export workflow in this phase.")[0] == "phase_amendment"
    assert module.classify_request("We need to change the architecture and add a browser extension too.")[0] == "project_replan"
    assert module.classify_request("Stop this and pivot to a different product.")[0] == "pivot"


def test_create_project_amendment_writes_snapshot_and_updates_project(tmp_path):
    root = tmp_path / "platform"
    project_file = root / "vault" / "clients" / "acme" / "projects" / "sample-project.md"
    snapshots_dir = root / "vault" / "clients" / "acme" / "snapshots"
    tickets_dir = root / "vault" / "clients" / "acme" / "tickets"

    write_markdown(
        project_file,
        [
            "---",
            'type: project',
            'title: "Sample Project"',
            "status: active",
            'goal: "Build the operator console."',
            "---",
            "",
            "# Sample Project",
            "",
        ],
    )
    write_markdown(
        snapshots_dir / "2026-04-13-project-plan-sample-project.md",
        [
            "---",
            "type: snapshot",
            "subtype: project-plan",
            'project: "sample-project"',
            "current_phase: 1",
            "total_phases: 4",
            "captured: 2026-04-13T12:00",
            "---",
            "",
            "# Project Plan — Sample Project",
            "",
            "## Phases",
            "",
            "### Phase 1: Foundation (active)",
            "**Goal:** Build the shell.",
            "**Exit criteria:**",
            "- Shell exists",
            "",
        ],
    )
    write_markdown(
        tickets_dir / "T-101-shell.md",
        [
            "---",
            "type: ticket",
            "id: T-101",
            'title: "Build shell"',
            "status: open",
            'project: "sample-project"',
            "created: 2026-04-13T12:05",
            "updated: 2026-04-13T12:05",
            "blocked_by: []",
            "---",
            "",
            "# Build shell",
            "",
        ],
    )

    request_text = "Also add a handoff surface and export workflow in this phase."
    subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--project-file",
            str(project_file),
            "--request-text",
            request_text,
            "--source-kind",
            "email",
            "--source-subject",
            "Can we also add export?",
            "--source-message-id",
            "msg-123",
            "--captured-at",
            "2026-04-13T13:30:00 EDT -0400",
        ],
        cwd=root,
        check=True,
    )

    amendment_paths = sorted(snapshots_dir.glob("*project-amendment-sample-project-*.md"))
    assert len(amendment_paths) == 1
    amendment_text = amendment_paths[0].read_text(encoding="utf-8")
    assert "## Classification" in amendment_text
    assert "phase_amendment" in amendment_text
    assert "## Recommended Actions" in amendment_text

    payload = yaml.safe_load(amendment_text.split("---", 2)[1])
    assert payload["classification"] == "phase_amendment"
    assert payload["apply_mode"] == "phase_brief_delta"
    assert payload["requires_phase_brief_update"] is True
    assert payload["requires_ticket_reblock"] is True

    project_text = project_file.read_text(encoding="utf-8")
    assert "## Pending Amendments" in project_text
    assert "project-amendment-sample-project" in project_text
    assert "phase_amendment [pending]" in project_text
