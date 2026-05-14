"""
Test type: static contract tests for the research-context markdown skill.

These tests use grep-style text assertions and make no live network calls.
"""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL = REPO_ROOT / "skills" / "research-context.md"


def read_skill() -> str:
    return SKILL.read_text(encoding="utf-8")


def test_research_context_skill_exists_with_frontmatter_contract():
    text = read_skill()

    assert SKILL.exists()
    assert "type: skill" in text
    assert "name: research-context" in text
    for input_name in [
        "project",
        "client",
        "goal",
        "project_file_path",
        "snapshots_path",
        "trigger_reason",
        "model_cutoff",
    ]:
        assert f"- {input_name} " in text


def test_research_context_skill_names_categories_and_completion_standard():
    text = read_skill()

    for category in [
        "Recent launches in genre",
        "Current tool/library versions",
        "Deprecated patterns",
        "New capabilities since cutoff",
        "Current best practices in domain",
    ]:
        assert category in text
    assert "Research each category until the project's questions in that category are genuinely answered" in text
    assert "skill's own self-judgment governs completion" in text
    assert "not a call-count cap" in text


def test_research_context_skill_enforces_reservation_and_citation_rules():
    text = read_skill()

    assert "Do not call WebSearch or WebFetch unless" in text
    assert "scripts/research_context_budget.py reserve" in text
    assert "URL plus citation date within last 12 months" in text
    assert "[INFERRED:]" in text
    assert "low_confidence: true" in text
    assert "more than 30 percent" in text
    assert "scripts/check_research_context.py" in text


def test_research_context_skill_forbids_disallowed_research_paths():
    text = read_skill()

    assert "paid X API" in text
    assert "browser-driven X login" in text
    assert "browser-driven vendor login" in text
    assert "scraping behind authentication" in text


def test_research_context_skill_states_cooperation_runtime_boundary():
    text = read_skill()

    assert "Reservations are an audit ledger, not a gate" in text
    assert "reserve` always allows valid category/kind calls" in text
    assert "every search/fetch call still goes through the ledger" in text
