from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "build_project_rehearsal.py"


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


def build_args(project_file: Path, plan_path: Path | None = None, transition: str | None = None) -> argparse.Namespace:
    return argparse.Namespace(
        project_file=str(project_file),
        project_plan=str(plan_path) if plan_path else None,
        transition=transition,
        json_out=None,
        markdown_out=None,
    )


def seed_project(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "platform"
    project_file = root / "vault" / "clients" / "acme" / "projects" / "control-platform.md"
    plan_path = root / "vault" / "clients" / "acme" / "snapshots" / "2026-01-04-project-plan-control-platform.md"
    brief_path = root / "vault" / "clients" / "acme" / "snapshots" / "2026-01-04-creative-brief-control-platform.md"
    review_path = root / "vault" / "clients" / "acme" / "snapshots" / "2026-01-04-delivery-review-control-platform.md"
    ticket_path = root / "vault" / "clients" / "acme" / "tickets" / "T-201-approvals.md"

    write_markdown(
        project_file,
        [
            "---",
            'type: project',
            'title: "Employee Agent Control Platform"',
            'status: active',
            'goal: "Build a premium operator console for approvals, feedback, handoff, and memory."',
            "---",
            "",
            "# Employee Agent Control Platform",
            "",
            "Current wave: Wave 2B — Delivery Hardening",
            "",
        ],
    )

    write_markdown(
        plan_path,
        [
            "---",
            "type: snapshot",
            "subtype: project-plan",
            'project: "control-platform"',
            "current_phase: 4",
            "total_phases: 6",
            "captured: 2026-01-04T09:00",
            "---",
            "",
            "# Plan",
            "",
            "## Goal Contract",
            "",
            "- **Rigor tier:** frontier",
            "- **Mission:** Build a premium operator console that remains truthful to canonical files.",
            "- **Primary evaluator:** skeptical manager-operator",
            "- **Mission success:** approvals, comments, handoff, and memory feel obvious and trustworthy.",
            "- **Primary success metrics:** primary workflows are obvious, claims are honest, and delivery artifacts stay aligned.",
            "- **Primary risks:** generic admin-dashboard drift and fake source-of-truth UI behavior.",
            "- **Human-owned decisions:** final product feel, rollout acceptance, and risk acceptance.",
            "- **Agent-owned execution:** delivery, verification, and operator-surface implementation.",
            "- **Proof shape:** Stitch-grounded design, runtime screenshots, QC walkthroughs, and delivery review.",
            "- **In scope:** operator console truthfulness and usability",
            "- **Out of scope:** hosted backend parity",
            "- **Partial-coverage rule:** partial scope must be explicit and accepted.",
            "",
            "### Goal Workstreams",
            "",
            "| Goal / Workstream | Type | Priority | Success Signal | Evaluator | Scale / Scope |",
            "|-------------------|------|----------|----------------|-----------|---------------|",
            "| WS-1 approvals UX | quality | critical | approvals and feedback are obvious | skeptical manager-operator | core product |",
            "",
            "## Assumption Register",
            "",
            "| ID | Assumption | Category | Risk | Validation Method | Owner | Target Phase/Gate | Status | Evidence / Resolution |",
            "|----|------------|----------|------|-------------------|-------|-------------------|--------|-----------------------|",
            "| A-001 | managers will find the feedback flow intuitive | user | high | rehearsal before delivery | orchestrator | delivery gate | validating | Needs rehearsal |",
            "",
            "## Phases",
            "",
            "### Phase 4: Delivery Hardening (active)",
            "**Goal:** delivery-ready operator surface",
            "**Exit criteria:**",
            "- Delivery package is trustworthy [EXECUTABLE] [TRACES: WS-1 approvals UX]",
            "",
        ],
    )

    write_markdown(
        brief_path,
        [
            "---",
            "type: snapshot",
            "subtype: creative-brief",
            'project: "control-platform"',
            'title: "Creative Brief — Control Platform"',
            "captured: 2026-01-04T09:10",
            "---",
            "",
            "# Brief",
            "",
            "## Proof Strategy",
            "",
            "- **Rigor tier:** frontier",
            "- **Evaluator lens:** skeptical manager-operator and clean-room delivery reviewer",
            "- **Proof posture:** project brief is enough until the delivery surface or reviewer lens changes materially.",
            "- **Primary evidence modes:** runtime screenshots, walkthroughs, review pack, delivery review",
            "- **False-pass risks:** approvals are present but buried, UI overstates autonomy, comments feel bolted on",
            "- **Adversarial / skeptical checks:** try to falsify whether the UI is truthful to canonical files and whether feedback is actually operable",
            "- **Rehearsal lenses:** tired operator, manager giving feedback, skeptical stakeholder",
            "- **Drift sentinels:** stale screenshots, stale review-pack claims, stale trust/autonomy language",
            "- **Supplement trigger:** create a narrower proof packet when delivery or QC artifacts change after remediation",
            "- **Gate impact:** QC, delivery review, and admin acceptance depend on this strategy",
            "",
        ],
    )

    write_markdown(
        review_path,
        [
            "---",
            "type: report",
            "review_type: delivery-review",
            'project: "control-platform"',
            'title: "Delivery Review — Control Platform"',
            "captured: 2026-01-04T09:40",
            'grade: "B"',
            "---",
            "",
            "# Delivery Review",
            "",
        ],
    )

    write_markdown(
        ticket_path,
        [
            "---",
            "type: ticket",
            'id: "T-201"',
            'title: "Fix approvals IA"',
            "status: blocked",
            'project: "control-platform"',
            "created: 2026-01-04T09:15",
            "updated: 2026-01-04T09:41",
            "blocked_by: [T-200]",
            "---",
            "",
            "# Ticket",
            "",
        ],
    )

    return project_file, plan_path


def test_build_project_rehearsal_infers_delivery_transition_and_operator_lenses(tmp_path):
    module = load_module("build_project_rehearsal_under_test", SCRIPT_PATH)
    project_file, plan_path = seed_project(tmp_path)

    report = module.build_report(build_args(project_file, plan_path))

    assert report["transition"] == "delivery"
    labels = [lens["label"].lower() for lens in report["lenses"]]
    assert "skeptical reviewer" in labels
    assert "tired operator" in labels
    assert "manager giving feedback" in labels
    assert report["ticket_recommended"] is True
    assert report["recommended_task_type"] == "simulation_rehearsal"


def test_build_project_rehearsal_carries_proof_strategy_signals(tmp_path):
    module = load_module("build_project_rehearsal_signals_under_test", SCRIPT_PATH)
    project_file, plan_path = seed_project(tmp_path)

    report = module.build_report(build_args(project_file, plan_path, transition="phase_gate"))

    assert report["transition"] == "phase_gate"
    assert "stale screenshots" in [item.lower() for item in report["proof_strategy"]["drift_sentinels"]]
    assert "approvals are present but buried" in [item.lower() for item in report["proof_strategy"]["false_pass_risks"]]
    assert report["proof_strategy"]["supplement_trigger"]


def test_build_project_rehearsal_ignores_stale_explicit_plan_path(tmp_path):
    module = load_module("build_project_rehearsal_stale_plan_under_test", SCRIPT_PATH)
    project_file, plan_path = seed_project(tmp_path)
    stale_plan = plan_path.with_name("2026-01-05-project-plan-control-platform.md")

    report = module.build_report(build_args(project_file, stale_plan))

    assert report["transition"] == "delivery"
    assert report["proof_strategy"]["supplement_trigger"]
    assert report["ticket_recommended"] is True
