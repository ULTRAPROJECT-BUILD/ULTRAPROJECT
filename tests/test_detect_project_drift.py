from __future__ import annotations

import argparse
import base64
import importlib.util
import sys
import time
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
DETECT_DRIFT_PATH = REPO_ROOT / "scripts" / "detect_project_drift.py"
BUILD_CONTEXT_PATH = REPO_ROOT / "scripts" / "build_project_context.py"
BUILD_IMAGE_INDEX_PATH = REPO_ROOT / "scripts" / "build_project_image_evidence.py"
BUILD_VIDEO_INDEX_PATH = REPO_ROOT / "scripts" / "build_project_video_evidence.py"

PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO2W3gAAAABJRU5ErkJggg=="
)


def load_module(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def write_markdown(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_image(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(PNG_1X1)


def build_args(project_file: Path, plan_path: Path | None = None) -> argparse.Namespace:
    return argparse.Namespace(
        project_file=str(project_file),
        project_plan=str(plan_path) if plan_path else None,
        json_out=None,
        markdown_out=None,
    )


def seed_project(tmp_path: Path, *, current_phase: int = 2, assumption_target: str = "Phase 3", add_image: bool = False) -> tuple[Path, Path]:
    root = tmp_path / "platform"
    project_file = root / "vault" / "clients" / "acme" / "projects" / "sample-project.md"
    plan_path = root / "vault" / "clients" / "acme" / "snapshots" / "2026-01-04-project-plan-sample-project.md"
    brief_path = root / "vault" / "clients" / "acme" / "snapshots" / "2026-01-04-creative-brief-sample-project.md"
    review_path = root / "vault" / "clients" / "acme" / "snapshots" / "2026-01-04-delivery-review-sample-project.md"
    ticket_path = root / "vault" / "clients" / "acme" / "tickets" / "T-101-polish.md"

    write_markdown(
        project_file,
        [
            "---",
            'type: project',
            'title: "Sample Project"',
            'status: active',
            'goal: "Ship a trustworthy operator console."',
            "---",
            "",
            "# Sample Project",
            "",
            "Current wave: Wave 3A — Delivery",
            "",
            "## Orchestrator Log",
            "",
            "- 2026-01-04T09:45: ORCH-CHECKPOINT: Delivery review is now the active blocker.",
        ],
    )

    write_markdown(
        plan_path,
        [
            "---",
            "type: snapshot",
            "subtype: project-plan",
            'project: "sample-project"',
            f"current_phase: {current_phase}",
            "total_phases: 5",
            "captured: 2026-01-04T09:00",
            "---",
            "",
            "# Project Plan",
            "",
            "## Goal Contract",
            "",
            "- **Rigor tier:** frontier",
            "- **Mission:** Ship a trustworthy operator console.",
            "- **Primary evaluator:** skeptical delivery reviewer",
            "- **Mission success:** Delivery package and runtime truth stay aligned.",
            "- **Primary success metrics:** current review surface, docs, and evidence all agree.",
            "- **Primary risks:** stale artifacts and overclaimed review notes.",
            "- **Human-owned decisions:** accept residual risk and judge final product feel.",
            "- **Agent-owned execution:** maintain project truth, fix drift, and refresh evidence.",
            "- **Proof shape:** plan contract + proof strategy + drift detection + delivery review.",
            "- **In scope:** project truth and delivery alignment",
            "- **Out of scope:** portfolio reporting",
            "- **Partial-coverage rule:** partial coverage must be explicit and approved.",
            "",
            "### Goal Workstreams",
            "",
            "| Goal / Workstream | Type | Priority | Success Signal | Evaluator | Scale / Scope |",
            "|-------------------|------|----------|----------------|-----------|---------------|",
            "| WS-1 delivery truth | quality | critical | current review points at the right artifacts | delivery reviewer | project-wide |",
            "",
            "## Assumption Register",
            "",
            "| ID | Assumption | Category | Risk | Validation Method | Owner | Target Phase/Gate | Status | Evidence / Resolution |",
            "|----|------------|----------|------|-------------------|-------|-------------------|--------|-----------------------|",
            f"| A-001 | Review pack will stay aligned with the latest gate | proof | high | run drift detection before delivery | orchestrator | {assumption_target} | validating | Pending drift pass |",
            "",
            "## Phases",
            "",
            f"### Phase {current_phase}: Delivery (active)",
            "**Goal:** Close the delivery surface cleanly.",
            "**Exit criteria:**",
            "- Delivery review is current [EXECUTABLE] [TRACES: WS-1 delivery truth]",
            "",
            "## Artifact Manifest",
            "",
            "| Artifact | Path | Produced by | Date |",
            "|----------|------|-------------|------|",
            "| Delivery Review | vault/clients/acme/snapshots/2026-01-04-delivery-review-sample-project.md | T-101 | 2026-01-04 |",
            "",
        ],
    )

    write_markdown(
        brief_path,
        [
            "---",
            "type: snapshot",
            "subtype: creative-brief",
            'project: "sample-project"',
            'title: "Creative Brief — Sample Project"',
            "captured: 2026-01-04T09:10",
            "---",
            "",
            "# Brief",
            "",
            "## Proof Strategy",
            "",
            "- **Rigor tier:** frontier",
            "- **Evaluator lens:** skeptical delivery reviewer",
            "- **Proof posture:** the project brief is enough until the delivery surface changes materially.",
            "- **Primary evidence modes:** current context, delivery review, screenshots",
            "- **False-pass risks:** stale delivery artifacts and overclaimed cleanup notes",
            "- **Adversarial / skeptical checks:** check whether the current review surface is still the latest artifact.",
            "- **Rehearsal lenses:** skeptical reviewer, delivery receiver",
            "- **Drift sentinels:** stale delivery review, stale authoritative paths",
            "- **Supplement trigger:** create a narrower proof packet when delivery artifacts drift after remediation.",
            "- **Gate impact:** delivery review and admin acceptance depend on this proof strategy.",
            "",
        ],
    )

    review_body = ["# Delivery Review", ""]
    if add_image:
        review_body.append("Referenced `qc-screenshot-dashboard-health.png`.")
    write_markdown(
        review_path,
        [
            "---",
            "type: report",
            "review_type: delivery-review",
            'project: "sample-project"',
            'title: "Delivery Review — Sample Project"',
            "captured: 2026-01-04T09:30",
            'grade: "A"',
            "---",
            "",
            *review_body,
        ],
    )

    if add_image:
        write_image(review_path.parent / "qc-screenshot-dashboard-health.png")

    write_markdown(
        ticket_path,
        [
            "---",
            "type: ticket",
            'id: "T-101"',
            'title: "Polish delivery artifacts"',
            "status: closed",
            'project: "sample-project"',
            "created: 2026-01-04T08:45",
            "updated: 2026-01-04T09:35",
            "completed: 2026-01-04T09:35",
            "---",
            "",
            "# Ticket",
            "",
        ],
    )

    build_context = load_module("build_project_context_for_drift_tests", BUILD_CONTEXT_PATH)
    build_images = load_module("build_project_image_for_drift_tests", BUILD_IMAGE_INDEX_PATH)
    build_videos = load_module("build_project_video_for_drift_tests", BUILD_VIDEO_INDEX_PATH)
    report = build_context.build_report(build_args(project_file, plan_path))
    derived_dir = project_file.parent / "sample-project.derived"
    derived_dir.mkdir(parents=True, exist_ok=True)
    build_context.write_outputs(report, derived_dir / "current-context.md", derived_dir / "artifact-index.yaml")
    build_images.write_index(build_images.build_report(project_file), derived_dir / "image-evidence-index.yaml")
    build_videos.write_index(build_videos.build_report(project_file), derived_dir / "video-evidence-index.yaml")
    return project_file, plan_path


def test_detect_project_drift_passes_when_context_is_aligned(tmp_path):
    module = load_module("detect_project_drift_pass_under_test", DETECT_DRIFT_PATH)
    project_file, plan_path = seed_project(tmp_path, current_phase=2, assumption_target="Phase 3", add_image=False)

    report = module.build_report(build_args(project_file, plan_path))

    assert report["verdict"] == "PASS"
    assert report["failures"] == []
    assert report["warnings"] == []


def test_detect_project_drift_fails_when_current_review_surface_is_stale(tmp_path):
    module = load_module("detect_project_drift_fail_under_test", DETECT_DRIFT_PATH)
    project_file, plan_path = seed_project(tmp_path, current_phase=2, assumption_target="Phase 3", add_image=False)
    snapshots_dir = plan_path.parent

    time.sleep(1.1)
    write_markdown(
        snapshots_dir / "2026-01-04-delivery-review-v2-sample-project.md",
        [
            "---",
            "type: report",
            "review_type: delivery-review",
            'project: "sample-project"',
            'title: "Delivery Review V2 — Sample Project"',
            "captured: 2026-01-04T09:45",
            'grade: "B"',
            "---",
            "",
            "# Delivery Review V2",
            "",
        ],
    )

    report = module.build_report(build_args(project_file, plan_path))

    assert report["verdict"] == "FAIL"
    failure_kinds = {issue["kind"] for issue in report["failures"]}
    assert "derived_stale" in failure_kinds or "current_review_mismatch" in failure_kinds


def test_detect_project_drift_warns_on_overdue_active_assumptions(tmp_path):
    module = load_module("detect_project_drift_warn_under_test", DETECT_DRIFT_PATH)
    project_file, plan_path = seed_project(tmp_path, current_phase=3, assumption_target="Phase 2", add_image=True)

    report = module.build_report(build_args(project_file, plan_path))

    assert report["verdict"] == "WARN"
    warning_kinds = {issue["kind"] for issue in report["warnings"]}
    assert "assumption_overdue" in warning_kinds


def test_detect_project_drift_ignores_stale_explicit_plan_path(tmp_path):
    module = load_module("detect_project_drift_stale_plan_under_test", DETECT_DRIFT_PATH)
    project_file, plan_path = seed_project(tmp_path, current_phase=2, assumption_target="Phase 3", add_image=False)
    stale_plan = plan_path.with_name("2026-01-05-project-plan-sample-project.md")

    report = module.build_report(build_args(project_file, stale_plan))

    assert report["verdict"] == "PASS"
