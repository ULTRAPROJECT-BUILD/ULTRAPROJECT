from __future__ import annotations

import subprocess
import sys
import shutil
from pathlib import Path

import pytest
import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "build_project_video_evidence.py"


def write_markdown(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_video(path: Path, *, seconds: float = 1.0) -> None:
    if not shutil.which("ffmpeg"):
        pytest.skip("ffmpeg is required to synthesize video fixture files")
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=black:s=160x90:r=10",
            "-t",
            str(seconds),
            str(path),
        ],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def test_build_project_video_evidence_collects_referenced_and_review_videos(tmp_path):
    root = tmp_path / "platform"
    project_file = root / "vault" / "clients" / "acme" / "projects" / "sample-project.md"
    snapshots_dir = root / "vault" / "clients" / "acme" / "snapshots"

    write_markdown(
        project_file,
        [
            "---",
            'type: project',
            'title: "Sample Project"',
            'status: active',
            'goal: "Ship a project with walkthrough evidence."',
            "---",
            "",
            "# Sample Project",
            "",
        ],
    )

    write_markdown(
        snapshots_dir / "2026-01-04-quality-check-sample-project.md",
        [
            "---",
            "type: snapshot",
            "subtype: quality-check",
            'project: "sample-project"',
            'title: "Quality Check — Sample Project"',
            "captured: 2026-01-04T09:10",
            "---",
            "",
            "# QC",
            "",
            "Referenced `qc-walkthrough-dashboard.webm` and `demo-approval-flow.mp4`.",
        ],
    )
    write_markdown(
        snapshots_dir / "2026-01-04-delivery-review-sample-project.md",
        [
            "---",
            "type: report",
            "review_type: delivery-review",
            'project: "sample-project"',
            'title: "Delivery Review — Sample Project"',
            "captured: 2026-01-04T09:30",
            "---",
            "",
            "# Delivery Review",
            "",
            "Walkthrough video present and required.",
        ],
    )
    write_markdown(
        snapshots_dir / "2026-01-04-quality-check-other-project.md",
        [
            "---",
            "type: snapshot",
            "subtype: quality-check",
            'project: "other-project"',
            'title: "Quality Check — Other Project"',
            "captured: 2026-01-04T09:40",
            "---",
            "",
            "# QC",
            "",
            "Referenced `qc-walkthrough-other-project.webm`.",
        ],
    )

    write_video(snapshots_dir / "qc-walkthrough-dashboard.webm")
    write_video(snapshots_dir / "demo-approval-flow.mp4")
    write_video(snapshots_dir / "qc-walkthrough-other-project.webm")

    subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--project-file", str(project_file)],
        cwd=root,
        check=True,
    )

    index_path = project_file.parent / "sample-project.derived" / "video-evidence-index.yaml"
    assert index_path.exists()

    report = yaml.safe_load(index_path.read_text(encoding="utf-8"))
    assert report["project"] == "sample-project"
    assert report["video_evidence"]["count"] >= 2
    video_paths = {video["path"] for video in report["video_evidence"]["videos"]}
    assert "vault/clients/acme/snapshots/qc-walkthrough-dashboard.webm" in video_paths
    assert "vault/clients/acme/snapshots/demo-approval-flow.mp4" in video_paths
    assert "vault/clients/acme/snapshots/qc-walkthrough-other-project.webm" not in video_paths

    videos_by_path = {video["path"]: video for video in report["video_evidence"]["videos"]}
    assert videos_by_path["vault/clients/acme/snapshots/qc-walkthrough-dashboard.webm"]["category"] == "walkthrough"
    assert videos_by_path["vault/clients/acme/snapshots/qc-walkthrough-dashboard.webm"]["duration_seconds"] is not None
    assert "vault/clients/acme/snapshots/qc-walkthrough-dashboard.webm" in report["semantic_video_corpus"]


def test_build_project_video_evidence_handles_project_shell_without_videos(tmp_path):
    root = tmp_path / "platform"
    project_file = root / "vault" / "clients" / "acme" / "projects" / "queued-project.md"

    write_markdown(
        project_file,
        [
            "---",
            'type: project',
            'title: "Queued Project"',
            'status: planning',
            'goal: "Wait for activation."',
            "---",
            "",
            "# Queued Project",
            "",
        ],
    )

    subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--project-file", str(project_file)],
        cwd=root,
        check=True,
    )

    index_path = project_file.parent / "queued-project.derived" / "video-evidence-index.yaml"
    report = yaml.safe_load(index_path.read_text(encoding="utf-8"))
    assert report["video_evidence"]["count"] == 0
    assert report["semantic_video_corpus"] == []
