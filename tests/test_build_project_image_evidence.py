from __future__ import annotations

import base64
import subprocess
import sys
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "build_project_image_evidence.py"

PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO2W3gAAAABJRU5ErkJggg=="
)


def write_markdown(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_image(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(PNG_1X1)


def test_build_project_image_evidence_collects_referenced_and_adjacent_images(tmp_path):
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
            'goal: "Ship a visual project with trustworthy proof."',
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
            "Referenced `qc-screenshot-dashboard-health.png` and `runtime-vs-stitch-home.png`.",
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
            "Referenced `qc-screenshot-dashboard-health.png`.",
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
            "Referenced `qc-screenshot-other-project.png`.",
        ],
    )

    write_image(snapshots_dir / "qc-screenshot-dashboard-health.png")
    write_image(snapshots_dir / "qc-screenshot-dashboard-trust.png")
    write_image(snapshots_dir / "runtime-vs-stitch-home.png")
    write_image(snapshots_dir / "qc-walkthrough-dashboard.png")
    write_image(snapshots_dir / "qc-slides" / "slide-01.png")
    write_image(snapshots_dir / "qc-screenshot-other-project.png")

    subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--project-file", str(project_file)],
        cwd=root,
        check=True,
    )

    index_path = project_file.parent / "sample-project.derived" / "image-evidence-index.yaml"
    assert index_path.exists()

    report = yaml.safe_load(index_path.read_text(encoding="utf-8"))
    assert report["project"] == "sample-project"
    assert report["image_evidence"]["count"] >= 4
    image_paths = {image["path"] for image in report["image_evidence"]["images"]}
    assert "vault/clients/acme/snapshots/qc-screenshot-dashboard-health.png" in image_paths
    assert "vault/clients/acme/snapshots/qc-screenshot-dashboard-trust.png" in image_paths
    assert "vault/clients/acme/snapshots/runtime-vs-stitch-home.png" in image_paths
    assert "vault/clients/acme/snapshots/qc-slides/slide-01.png" in image_paths
    assert "vault/clients/acme/snapshots/qc-screenshot-other-project.png" not in image_paths

    images_by_path = {image["path"]: image for image in report["image_evidence"]["images"]}
    assert images_by_path["vault/clients/acme/snapshots/qc-screenshot-dashboard-health.png"]["category"] == "qc_screenshot"
    assert images_by_path["vault/clients/acme/snapshots/runtime-vs-stitch-home.png"]["category"] == "stitch_reference"
    assert "vault/clients/acme/snapshots/2026-01-04-quality-check-sample-project.md" in images_by_path[
        "vault/clients/acme/snapshots/qc-screenshot-dashboard-health.png"
    ]["source_docs"]
    assert "vault/clients/acme/snapshots/qc-screenshot-dashboard-health.png" in report["semantic_image_corpus"]


def test_build_project_image_evidence_handles_project_shell_without_images(tmp_path):
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

    index_path = project_file.parent / "queued-project.derived" / "image-evidence-index.yaml"
    report = yaml.safe_load(index_path.read_text(encoding="utf-8"))
    assert report["image_evidence"]["count"] == 0
    assert report["semantic_image_corpus"] == []
