"""
Static contract tests for research-context ownership.

These tests make no live network calls. They guard the failure mode where the
orchestrator skips advisory research instructions and spawns project-plan anyway.
"""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PROJECT_PLAN = REPO_ROOT / "skills" / "project-plan.md"
ORCHESTRATOR = REPO_ROOT / "skills" / "orchestrator.md"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_project_plan_owns_step_zero_research_gate():
    text = read(PROJECT_PLAN)

    assert "## Step 0: Research Context Gate (MANDATORY)" in text
    assert "Project-plan owns currentness research" in text
    assert "scripts/research_context_trigger.py" in text
    assert "run [[research-context]] immediately before Step 1" in text
    assert "before any architecture decisions" in text
    assert "must not produce architecture decisions" in text


def test_project_plan_requires_current_research_inputs_section():
    text = read(PROJECT_PLAN)

    assert "Always write `## Current Research Inputs`" in text
    assert "## Current Research Inputs" in text
    assert "**Trigger decision:**" in text
    assert "**Research-context snapshot:**" in text
    assert "low_confidence: true" in text
    assert "Assumption Register" in text
    assert "Open Questions" in text


def test_orchestrator_delegates_research_to_project_plan():
    text = read(ORCHESTRATOR)

    assert "project-plan skill owns the Research Context Gate" in text
    assert "records `## Current Research Inputs`" in text
    assert "scripts/research_context_trigger.py" not in text
    assert "Research Context Trigger (MANDATORY before [[project-plan]]" not in text


def test_plan_qa_audits_research_context():
    text = read(PROJECT_PLAN)

    assert "RESEARCH-CONTEXT AUDIT" in text
    assert "Current Research Inputs" in text
    assert "fresh citation" in text
    assert "does not authorize unavailable tooling" in text
