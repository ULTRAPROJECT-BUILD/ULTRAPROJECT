from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CHECK_QUALITY_CONTRACT_PATH = REPO_ROOT / "scripts" / "check_quality_contract.py"


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


def build_args(project_file: Path, plan_path: Path, brief_paths: list[Path] | None = None) -> argparse.Namespace:
    return argparse.Namespace(
        project_file=str(project_file),
        project_plan=str(plan_path),
        brief=[str(path) for path in (brief_paths or [])],
        json_out=None,
        markdown_out=None,
    )


def write_project(project_file: Path, *, status: str = "active", tags: list[str] | None = None) -> None:
    tags_text = "[" + ", ".join(tags or []) + "]"
    write_markdown(
        project_file,
        [
            "---",
            'type: project',
            'title: "Demo Project"',
            f"status: {status}",
            'goal: "Build a trustworthy delivery system."',
            f"tags: {tags_text}",
            "---",
            "",
            "# Demo Project",
            "",
        ],
    )


def write_plan(plan_path: Path, *, include_assumptions: bool = True) -> None:
    lines = [
        "---",
        "type: snapshot",
        "subtype: project-plan",
        'project: "demo-project"',
        "execution_model: capability-waves",
        "current_phase: 1",
        "total_phases: 4",
        "---",
        "",
        "# Project Plan — Demo Project",
        "",
        "## Goal Contract",
        "",
        "- **Rigor tier:** frontier",
        "- **Mission:** Deliver a trustworthy system without silent scope downgrades.",
        "- **Primary evaluator:** skeptical clean-room reviewer",
        "- **Mission success:** The platform can prove what it claims and name what it cannot.",
        "- **Primary success metrics:** mission traces stay covered, assumptions stay actionable, and proof contracts stay coherent.",
        "- **Primary risks:** silent scope drift, hidden assumptions, and proof theater.",
        "- **Human-owned decisions:** approve descopes, accept residual risk, and judge strategic tradeoffs.",
        "- **Agent-owned execution:** compile the mission, maintain the contract, and route remediation work.",
        "- **Proof shape:** structured mission contract + brief proof strategy + local checkers + gate reviews.",
        "- **In scope:** planning, briefing, gates, and proof contracts",
        "- **Out of scope:** UI productization and portfolio intelligence",
        "- **Partial-coverage rule:** Partial coverage is only honest when explicitly labeled and justified.",
        "",
        "### Goal Workstreams",
        "",
        "| Goal / Workstream | Type | Priority | Success Signal | Evaluator | Scale / Scope |",
        "|-------------------|------|----------|----------------|-----------|---------------|",
        "| WS-1 mission clarity | quality | critical | Goal contract governs plan and briefing | admin | platform-wide |",
        "| WS-2 explicit assumptions | risk | critical | Hidden bets surface in the plan and gates | clean-room reviewer | platform-wide |",
        "",
    ]
    if include_assumptions:
        lines.extend(
            [
                "## Assumption Register",
                "",
                "| ID | Assumption | Category | Risk | Validation Method | Owner | Target Phase/Gate | Status | Evidence / Resolution |",
                "|----|------------|----------|------|-------------------|-------|-------------------|--------|-----------------------|",
                "| A-001 | Existing gate flow can absorb the new contract checks | process | high | Run local gate fixtures and quality-contract checker | orchestrator | plan QA | validating | Pending first integrated pass |",
                "| A-002 | Briefs can stay lean while adding proof strategy | UX | medium | Review generated brief length and gate outcomes | creative-brief | brief gate | open | Not yet measured |",
                "",
            ]
        )
    lines.extend(
        [
            "## Phases",
            "",
            "### Phase 1: Foundation (active)",
            "**Exit criteria:**",
            "- Goal contract written and traced [EXECUTABLE] [TRACES: WS-1 mission clarity]",
            "- Assumption register present and actionable [EXECUTABLE] [TRACES: WS-2 explicit assumptions]",
            "",
        ]
    )
    write_markdown(plan_path, lines)


def write_brief(brief_path: Path, *, include_proof_strategy: bool = True) -> None:
    lines = [
        "---",
        "type: snapshot",
        "subtype: creative-brief",
        'project: "demo-project"',
        "brief_scope: project",
        "---",
        "",
        "# Creative Brief — Demo Project",
        "",
        "## Mission Alignment Map",
        "",
        "| Mission Goal / Workstream | Acceptance Criteria | How Verified | Scale / Scope |",
        "|--------------------------|--------------------|--------------|---------------|",
        "| WS-1 mission clarity | Goal contract sections exist and are consumed | Plan QA + brief review | platform-wide |",
        "",
    ]
    if include_proof_strategy:
        lines.extend(
            [
                "## Proof Strategy",
                "",
                "- **Rigor tier:** frontier",
                "- **Evaluator lens:** skeptical platform maintainer and clean-room reviewer",
                "- **Proof posture:** Project brief defines the base contract; later phase briefs add proof deltas only when evaluator lens materially changes.",
                "- **Primary evidence modes:** plan QA, brief review, local checker output, gate reports",
                "- **False-pass risks:** duplicated prose with no enforcement, traces that do not map back to mission, assumptions hidden in narrative",
                "- **Adversarial / skeptical checks:** attempt to find mission goals with no traceability and high-risk assumptions with no validation target",
                "- **Rehearsal lenses:** skeptical maintainer, delivery reviewer, and operator resuming the project midstream.",
                "- **Drift sentinels:** stale traces, stale review packs, and unresolved high-risk assumptions that outlive their target gate.",
                "- **Supplement trigger:** create a narrower proof packet when a phase or wave introduces a materially different evaluator lens or evidence surface.",
                "- **Gate impact:** Plan QA and brief review must block if these sections are missing or incoherent.",
                "",
            ]
        )
    write_markdown(brief_path, lines)


def test_quality_contract_passes_with_complete_plan_and_brief(tmp_path):
    module = load_module("check_quality_contract_pass", CHECK_QUALITY_CONTRACT_PATH)
    project_file = tmp_path / "projects" / "demo-project.md"
    plan_path = tmp_path / "snapshots" / "project-plan-demo-project.md"
    brief_path = tmp_path / "snapshots" / "creative-brief-demo-project.md"

    write_project(project_file, tags=["admin-priority"])
    write_plan(plan_path, include_assumptions=True)
    write_brief(brief_path, include_proof_strategy=True)

    report = module.build_report(build_args(project_file, plan_path, [brief_path]))

    assert report["verdict"] == "PASS"
    plan_checks = {check["name"]: check for check in report["plan"]["checks"]}
    assert plan_checks["goal_contract_present"]["ok"] is True
    assert plan_checks["trace_coverage"]["ok"] is True
    assert plan_checks["high_risk_assumptions_actionable"]["ok"] is True
    brief_checks = {check["name"]: check for check in report["briefs"][0]["checks"]}
    assert brief_checks["proof_strategy_present"]["ok"] is True
    assert brief_checks["frontier_proof_strategy_adversarial"]["ok"] is True


def test_quality_contract_accepts_current_assumption_status_vocabulary(tmp_path):
    module = load_module("check_quality_contract_current_statuses", CHECK_QUALITY_CONTRACT_PATH)
    project_file = tmp_path / "projects" / "demo-project.md"
    plan_path = tmp_path / "snapshots" / "project-plan-demo-project.md"
    brief_path = tmp_path / "snapshots" / "creative-brief-demo-project.md"

    write_project(project_file, tags=["admin-priority"])
    write_plan(plan_path, include_assumptions=True)
    plan_text = plan_path.read_text(encoding="utf-8").replace(
        "| A-001 | Existing gate flow can absorb the new contract checks | process | high | Run local gate fixtures and quality-contract checker | orchestrator | plan QA | validating | Pending first integrated pass |",
        "| A-001 | Existing gate flow can absorb the new contract checks | process | high | Run local gate fixtures and quality-contract checker | orchestrator | plan QA | partial | Partially proven; follow-up gate remains active |",
    )
    plan_text = plan_text.replace(
        "| A-002 | Briefs can stay lean while adding proof strategy | UX | medium | Review generated brief length and gate outcomes | creative-brief | brief gate | open | Not yet measured |",
        "| A-002 | Briefs can stay lean while adding proof strategy | UX | medium | Review generated brief length and gate outcomes | creative-brief | brief gate | validated | Proven in prior gate |",
    )
    plan_path.write_text(plan_text, encoding="utf-8")
    write_brief(brief_path, include_proof_strategy=True)

    report = module.build_report(build_args(project_file, plan_path, [brief_path]))

    assert report["verdict"] == "PASS"
    plan_checks = {check["name"]: check for check in report["plan"]["checks"]}
    assert plan_checks["assumption_status_values"]["ok"] is True
    assert plan_checks["frontier_assumptions_explicit"]["ok"] is True


def test_quality_contract_fails_when_assumption_register_is_missing(tmp_path):
    module = load_module("check_quality_contract_fail_assumptions", CHECK_QUALITY_CONTRACT_PATH)
    project_file = tmp_path / "projects" / "demo-project.md"
    plan_path = tmp_path / "snapshots" / "project-plan-demo-project.md"

    write_project(project_file, tags=["admin-priority"])
    write_plan(plan_path, include_assumptions=False)

    report = module.build_report(build_args(project_file, plan_path))

    assert report["verdict"] == "FAIL"
    plan_checks = {check["name"]: check for check in report["plan"]["checks"]}
    assert plan_checks["assumption_register_present"]["ok"] is False
    assert plan_checks["assumption_register_nonempty"]["ok"] is False


def test_quality_contract_fails_when_brief_lacks_proof_strategy(tmp_path):
    module = load_module("check_quality_contract_fail_proof", CHECK_QUALITY_CONTRACT_PATH)
    project_file = tmp_path / "projects" / "demo-project.md"
    plan_path = tmp_path / "snapshots" / "project-plan-demo-project.md"
    brief_path = tmp_path / "snapshots" / "creative-brief-demo-project.md"

    write_project(project_file, tags=["admin-priority"])
    write_plan(plan_path, include_assumptions=True)
    write_brief(brief_path, include_proof_strategy=False)

    report = module.build_report(build_args(project_file, plan_path, [brief_path]))

    assert report["verdict"] == "FAIL"
    brief_checks = {check["name"]: check for check in report["briefs"][0]["checks"]}
    assert brief_checks["proof_strategy_present"]["ok"] is False


def test_frontier_plan_requires_open_or_validating_assumption_not_just_deferred(tmp_path):
    module = load_module("check_quality_contract_frontier_active_assumptions", CHECK_QUALITY_CONTRACT_PATH)
    project_file = tmp_path / "projects" / "demo-project.md"
    plan_path = tmp_path / "snapshots" / "project-plan-demo-project.md"

    write_project(project_file, tags=["admin-priority"])
    write_plan(plan_path, include_assumptions=True)
    plan_text = plan_path.read_text(encoding="utf-8").replace(
        "| A-001 | Existing gate flow can absorb the new contract checks | process | high | Run local gate fixtures and quality-contract checker | orchestrator | plan QA | validating | Pending first integrated pass |",
        "| A-001 | Existing gate flow can absorb the new contract checks | process | high | Run local gate fixtures and quality-contract checker | orchestrator | plan QA | deferred | Waiting for next platform window |",
    )
    plan_text = plan_text.replace(
        "| A-002 | Briefs can stay lean while adding proof strategy | UX | medium | Review generated brief length and gate outcomes | creative-brief | brief gate | open | Not yet measured |",
        "| A-002 | Briefs can stay lean while adding proof strategy | UX | medium | Review generated brief length and gate outcomes | creative-brief | brief gate | invalidated | Brief already grew too much in a prior attempt |",
    )
    plan_path.write_text(plan_text, encoding="utf-8")

    report = module.build_report(build_args(project_file, plan_path))

    assert report["verdict"] == "FAIL"
    plan_checks = {check["name"]: check for check in report["plan"]["checks"]}
    assert plan_checks["frontier_assumptions_explicit"]["ok"] is False
