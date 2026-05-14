"""
Static downstream contract tests for project-plan and creative-brief.

These tests use markdown text assertions only and make no live network calls.
"""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PROJECT_PLAN = REPO_ROOT / "skills" / "project-plan.md"
CREATIVE_BRIEF = REPO_ROOT / "skills" / "creative-brief.md"


def test_project_plan_states_research_context_boundaries():
    text = PROJECT_PLAN.read_text(encoding="utf-8")

    assert "Research-context informs architecture; it does not replace proof." in text
    assert "does not authorize unavailable tooling" in text
    assert "Do not bloat the plan with raw research" in text
    assert "Low-confidence claims must be tracked as assumptions" in text


def test_creative_brief_reads_research_context_and_audits_usage():
    text = CREATIVE_BRIEF.read_text(encoding="utf-8")

    assert "research_context_path" in text
    assert "Research Context Used" in text
    assert "research-context.md" in text
    assert "research-context claim" in text
    assert "assumptions or risks" in text
    assert "available in this run" in text


def test_creative_brief_tracks_deprecated_and_version_findings():
    text = CREATIVE_BRIEF.read_text(encoding="utf-8")

    assert "Deprecated-pattern findings should appear in anti-patterns" in text
    assert "current version findings must prevent stale recommended-tooling claims" in text
    assert "No separate gate-review subagent is added" in text
