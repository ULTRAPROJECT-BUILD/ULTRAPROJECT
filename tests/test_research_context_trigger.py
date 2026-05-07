"""
Test type: behavior fixture tests for the research-context trigger helper.

These tests create temporary project files and make no live network calls.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "research_context_trigger.py"


def run_trigger(project_file: Path, goal: str, tmp_path: Path) -> tuple[subprocess.CompletedProcess[str], dict]:
    json_out = tmp_path / "trigger.json"
    markdown_out = tmp_path / "trigger.md"
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--project-file",
            str(project_file),
            "--goal",
            goal,
            "--json-out",
            str(json_out),
            "--markdown-out",
            str(markdown_out),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    payload = json.loads(json_out.read_text(encoding="utf-8"))
    return result, payload


def write_project(path: Path, frontmatter: str, body: str = "") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\n{frontmatter}---\n{body}", encoding="utf-8")
    return path


def test_missing_project_file_exits_error(tmp_path):
    result, payload = run_trigger(tmp_path / "missing.md", "launch video", tmp_path)

    assert result.returncode == 1
    assert payload["decision"] == "error"
    assert "missing_or_unreadable_project_file" in payload["reason"]


def test_malformed_yaml_frontmatter_exits_error(tmp_path):
    project = tmp_path / "projects" / "broken.md"
    project.parent.mkdir(parents=True, exist_ok=True)
    project.write_text("---\ntags: [video, launch\n---\n## Goal\nBuild a video.\n", encoding="utf-8")

    result, payload = run_trigger(project, "Build a video.", tmp_path)

    assert result.returncode == 1
    assert payload["decision"] == "error"
    assert "malformed_yaml_frontmatter" in payload["reason"]


def test_missing_tags_and_missing_goal_defaults_required(tmp_path):
    project = write_project(
        tmp_path / "projects" / "ambiguous.md",
        'project: "ambiguous"\n',
        "## Context\nNo explicit goal is present.\n",
    )

    result, payload = run_trigger(project, "", tmp_path)

    assert result.returncode == 0
    assert payload["decision"] == "required"
    assert payload["reason"] == "missing_goal_and_tags_safe_default"


def test_operator_skip_override_wins_over_keywords_and_tags(tmp_path):
    project = write_project(
        tmp_path / "projects" / "skip.md",
        'project: "skip"\nresearch_context: skip\ntags: [video, launch, ai]\n',
        "## Goal\nCreate the latest launch video with current references.\n",
    )

    result, payload = run_trigger(project, "latest launch video", tmp_path)

    assert result.returncode == 0
    assert payload["decision"] == "skip"
    assert payload["reason"] == "operator_override_skip"
    assert "latest" in payload["matched_keywords"]
    assert "video" in payload["matched_tags"]


def test_operator_required_override_wins_over_local_only_tags(tmp_path):
    project = write_project(
        tmp_path / "projects" / "required.md",
        'project: "required"\nresearch_context: required\ntags: [cleanup]\n',
        "## Goal\nRename local files only.\n",
    )

    result, payload = run_trigger(project, "Rename local files only.", tmp_path)

    assert result.returncode == 0
    assert payload["decision"] == "required"
    assert payload["reason"] == "operator_override_required"
    assert payload["local_only"] is True


def test_no_tags_with_goal_and_no_currentness_is_optional(tmp_path):
    project = write_project(
        tmp_path / "projects" / "optional.md",
        'project: "optional"\n',
        "## Goal\nReformat local markdown files.\n",
    )

    result, payload = run_trigger(project, "Reformat local markdown files.", tmp_path)

    assert result.returncode == 0
    assert payload["decision"] == "optional"
    assert payload["reason"] == "no_currentness_signals"
