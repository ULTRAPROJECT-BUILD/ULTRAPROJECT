"""Tests for check_plan_compliance.py — the Plan QA mechanical pre-check.

These tests verify that the checker catches the specific compliance gaps the
rubber-stamp gate review missed: missing [PARTIAL-COVERAGE] tags, untraced
workstreams, exit criteria without taxonomy tags, and missing required sections.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "scripts" / "check_plan_compliance.py"


def load_module():
    spec = importlib.util.spec_from_file_location("check_plan_compliance_under_test", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["check_plan_compliance_under_test"] = module
    spec.loader.exec_module(module)
    return module


def write_plan(path: Path, body: str, *, tags: list[str] | None = None, capability_waves: bool = True) -> None:
    """Write a synthetic plan with the given body and frontmatter."""
    tags_str = "[" + ", ".join(tags or ["plan"]) + "]"
    exec_model = "execution_model: capability-waves\n" if capability_waves else ""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\n"
        "type: snapshot\n"
        "subtype: project-plan\n"
        'project: "demo"\n'
        f"{exec_model}"
        f"tags: {tags_str}\n"
        "---\n\n"
        + body,
        encoding="utf-8",
    )


def get_check(report: dict, name: str) -> dict:
    for c in report["checks"]:
        if c["name"] == name:
            return c
    raise AssertionError(f"check {name!r} not found in report; have: {[c['name'] for c in report['checks']]}")


def has_failure(report: dict, name: str) -> bool:
    try:
        return not get_check(report, name)["ok"]
    except AssertionError:
        return False


# Minimal valid plan body — passes all checks.
MINIMAL_VALID_BODY = """\
# Project Plan — Demo

## Current Research Inputs

- **Trigger report:** /tmp/trigger.json
- **Trigger decision:** skip — local_only_tags
- **Research-context snapshot:** not required
- **Confidence:** not available
- **Cost and coverage:** not applicable
- **Planning implications:** none
- **Assumptions from low-confidence research:** none

## Architecture Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Stack | Python | sensible default |

## Playbook Usage Contract

- Reuse mode: pattern_only
- Matched playbooks: none

## Why This Cannot Just Be The Playbook

This is a frontier project. No prior art exists.

## Goal Contract

- **Rigor tier:** frontier
- **Mission:** Build the thing.
- **Primary evaluator:** smoke harness
- **Mission success:** smoke exits 0
- **Primary success metrics:** harness pass
- **Primary risks:** rate limits
- **Human-owned decisions:** approval
- **Agent-owned execution:** all code
- **Proof shape:** smoke + screenshots
- **In scope:** the build
- **Out of scope:** hosting
- **Partial-coverage rule:** none

### Goal Workstreams

| Goal / Workstream | Type | Priority | Success Signal | Evaluator | Scale / Scope |
|-------------------|------|----------|----------------|-----------|---------------|
| WS-1 core path | functional | critical | works end to end | harness | one path |

## Assumption Register

| ID | Assumption | Category | Risk | Validation Method | Owner | Target Phase/Gate | Status | Evidence / Resolution |
|----|------------|----------|------|-------------------|-------|-------------------|--------|-----------------------|
| A-001 | API key present | operational | high | env check at smoke time | harness | Phase 1 | open | — |

## Capability Register

| Capability | Current Verdict | Target Verdict | Proof Status | Blocking Subsystem | Active Wave | Next Proof |
|------------|-----------------|----------------|--------------|--------------------|-------------|------------|
| core | Not started | Ready | none | core | Wave A | Phase 1 |

## Dynamic Wave Log

| Wave | Status | Anchor Phase | Capability Lanes | Purpose | Success Signal | Tickets |
|------|--------|--------------|------------------|---------|----------------|---------|
| Wave A | active | Phase 1 | core | prove the path | smoke passes | TBD |

## Phases

### Phase 1: Vertical Slice

**Goal:** end-to-end one debate
**Exit criteria:**
- smoke harness exits 0 [EXECUTABLE] [TRACES: WS-1]
"""


def test_minimal_valid_plan_passes(tmp_path):
    mod = load_module()
    plan_path = tmp_path / "plan.md"
    write_plan(plan_path, MINIMAL_VALID_BODY, tags=["plan", "frontier"])

    report = mod.validate_plan_compliance(plan_path)
    failures = [c for c in report["checks"] if not c["ok"]]
    assert not failures, f"unexpected failures: {[c['name'] + ': ' + c['details'] for c in failures]}"


def test_missing_required_section_fails(tmp_path):
    mod = load_module()
    body = MINIMAL_VALID_BODY.replace("## Architecture Decisions", "## Removed Section")
    plan_path = tmp_path / "plan.md"
    write_plan(plan_path, body, tags=["plan", "frontier"])

    report = mod.validate_plan_compliance(plan_path)
    assert has_failure(report, "section_architecture_decisions_present")


def test_missing_current_research_inputs_fails(tmp_path):
    mod = load_module()
    body = MINIMAL_VALID_BODY.replace(
        "## Current Research Inputs\n\n"
        "- **Trigger report:** /tmp/trigger.json\n"
        "- **Trigger decision:** skip — local_only_tags\n"
        "- **Research-context snapshot:** not required\n"
        "- **Confidence:** not available\n"
        "- **Cost and coverage:** not applicable\n"
        "- **Planning implications:** none\n"
        "- **Assumptions from low-confidence research:** none\n\n",
        "",
    )
    plan_path = tmp_path / "plan.md"
    write_plan(plan_path, body, tags=["plan", "frontier"])

    report = mod.validate_plan_compliance(plan_path)
    assert has_failure(report, "section_current_research_inputs_present")


def test_frontier_missing_playbook_section_fails(tmp_path):
    mod = load_module()
    body = MINIMAL_VALID_BODY.replace("## Playbook Usage Contract", "## Other Section")
    plan_path = tmp_path / "plan.md"
    write_plan(plan_path, body, tags=["plan", "frontier"])

    report = mod.validate_plan_compliance(plan_path)
    assert has_failure(report, "frontier_section_playbook_usage_contract_present")


def test_frontier_non_pattern_only_fails(tmp_path):
    mod = load_module()
    body = MINIMAL_VALID_BODY.replace(
        "- Reuse mode: pattern_only",
        "- Reuse mode: template_allowed",
    )
    plan_path = tmp_path / "plan.md"
    write_plan(plan_path, body, tags=["plan", "frontier"])

    report = mod.validate_plan_compliance(plan_path)
    assert has_failure(report, "frontier_reuse_mode_pattern_only")


def test_capability_waves_missing_register_fails(tmp_path):
    mod = load_module()
    body = MINIMAL_VALID_BODY.replace("## Capability Register", "## Other Section")
    plan_path = tmp_path / "plan.md"
    write_plan(plan_path, body, tags=["plan", "frontier"], capability_waves=True)

    report = mod.validate_plan_compliance(plan_path)
    assert has_failure(report, "capability_waves_section_capability_register_present")


def test_untraced_workstream_fails(tmp_path):
    """A workstream declared in the table but never referenced in [TRACES:] must fail."""
    mod = load_module()
    body = MINIMAL_VALID_BODY + "\n\n_extra:_ another workstream WS-2 added below.\n"
    body = body.replace(
        "| WS-1 core path | functional | critical | works end to end | harness | one path |",
        "| WS-1 core path | functional | critical | works end to end | harness | one path |\n"
        "| WS-2 untraced | functional | medium | (no exit criterion traces this) | harness | n/a |",
    )
    plan_path = tmp_path / "plan.md"
    write_plan(plan_path, body, tags=["plan", "frontier"])

    report = mod.validate_plan_compliance(plan_path)
    failure = get_check(report, "reverse_trace_coverage")
    assert not failure["ok"]
    assert "WS-2" in failure["details"]


def test_exit_criterion_missing_taxonomy_tag_fails(tmp_path):
    """An exit criterion line without [EXECUTABLE]/[INFRASTRUCTURE-DEPENDENT]/[MANUAL] must fail."""
    mod = load_module()
    body = MINIMAL_VALID_BODY.replace(
        "- smoke harness exits 0 [EXECUTABLE] [TRACES: WS-1]",
        "- smoke harness exits 0 [TRACES: WS-1]",
    )
    plan_path = tmp_path / "plan.md"
    write_plan(plan_path, body, tags=["plan", "frontier"])

    report = mod.validate_plan_compliance(plan_path)
    assert has_failure(report, "exit_criteria_taxonomy_tags")


def test_parameterized_taxonomy_tag_passes(tmp_path):
    """[INFRASTRUCTURE-DEPENDENT — display server required] must count as a taxonomy tag."""
    mod = load_module()
    body = MINIMAL_VALID_BODY.replace(
        "- smoke harness exits 0 [EXECUTABLE] [TRACES: WS-1]",
        "- smoke harness exits 0 [INFRASTRUCTURE-DEPENDENT — display server required] [TRACES: WS-1]",
    )
    plan_path = tmp_path / "plan.md"
    write_plan(plan_path, body, tags=["plan", "frontier"])

    report = mod.validate_plan_compliance(plan_path)
    check = get_check(report, "exit_criteria_taxonomy_tags")
    assert check["ok"], f"parameterized tag should pass; details: {check['details']}"


def test_partial_coverage_prose_without_tag_fails(tmp_path):
    """The exact rubber-stamp case from debate-arena: prose names a workstream as
    partial coverage but no [PARTIAL-COVERAGE] tag exists in any phase."""
    mod = load_module()
    body = MINIMAL_VALID_BODY.replace(
        "- **Partial-coverage rule:** none",
        '- **Partial-coverage rule:** "Public-URL capability" is proven via deploy doc, '
        "not by maintaining a live URL. Honest partial coverage.",
    )
    plan_path = tmp_path / "plan.md"
    write_plan(plan_path, body, tags=["plan", "frontier"])

    report = mod.validate_plan_compliance(plan_path)
    failure = get_check(report, "partial_coverage_tag_present")
    assert not failure["ok"]
    assert "PARTIAL-COVERAGE" in failure["details"]


def test_partial_coverage_prose_with_tag_passes(tmp_path):
    """Same as above but with one exit criterion tagged [PARTIAL-COVERAGE]."""
    mod = load_module()
    body = MINIMAL_VALID_BODY.replace(
        "- **Partial-coverage rule:** none",
        '- **Partial-coverage rule:** "Public-URL capability" is proven via deploy doc.',
    ).replace(
        "- smoke harness exits 0 [EXECUTABLE] [TRACES: WS-1]",
        "- smoke harness exits 0 [EXECUTABLE] [TRACES: WS-1]\n"
        "- deploy doc reviewed [PARTIAL-COVERAGE] [MANUAL] [TRACES: WS-1]",
    )
    plan_path = tmp_path / "plan.md"
    write_plan(plan_path, body, tags=["plan", "frontier"])

    report = mod.validate_plan_compliance(plan_path)
    check = get_check(report, "partial_coverage_tag_present")
    assert check["ok"], f"plan with [PARTIAL-COVERAGE] should pass; details: {check['details']}"


def test_partial_coverage_ws_ref_missing_tag_fails(tmp_path):
    """If the Partial-coverage rule names WS-N explicitly, that WS's exit lines must carry the tag."""
    mod = load_module()
    body = MINIMAL_VALID_BODY.replace(
        "- **Partial-coverage rule:** none",
        "- **Partial-coverage rule:** WS-1 is met at reduced scope (documented only).",
    )
    plan_path = tmp_path / "plan.md"
    write_plan(plan_path, body, tags=["plan", "frontier"])

    report = mod.validate_plan_compliance(plan_path)
    failure = get_check(report, "partial_coverage_tag_per_workstream")
    assert not failure["ok"]
    assert "WS-1" in failure["details"]


def test_partial_coverage_ws_ref_with_tag_passes(tmp_path):
    mod = load_module()
    body = MINIMAL_VALID_BODY.replace(
        "- **Partial-coverage rule:** none",
        "- **Partial-coverage rule:** WS-1 is met at reduced scope (documented only).",
    ).replace(
        "- smoke harness exits 0 [EXECUTABLE] [TRACES: WS-1]",
        "- smoke harness exits 0 [EXECUTABLE] [PARTIAL-COVERAGE] [TRACES: WS-1]",
    )
    plan_path = tmp_path / "plan.md"
    write_plan(plan_path, body, tags=["plan", "frontier"])

    report = mod.validate_plan_compliance(plan_path)
    check = get_check(report, "partial_coverage_tag_per_workstream")
    assert check["ok"]


def test_cli_exit_codes(tmp_path, monkeypatch, capsys):
    """End-to-end CLI: valid plan exits 0; invalid plan exits 1."""
    mod = load_module()
    plan_path = tmp_path / "plan.md"
    write_plan(plan_path, MINIMAL_VALID_BODY, tags=["plan", "frontier"])

    monkeypatch.setattr(sys, "argv", ["check_plan_compliance.py", "--plan", str(plan_path)])
    rc = mod.main()
    assert rc == 0

    bad_body = MINIMAL_VALID_BODY.replace("## Architecture Decisions", "## Other")
    write_plan(plan_path, bad_body, tags=["plan", "frontier"])

    monkeypatch.setattr(sys, "argv", ["check_plan_compliance.py", "--plan", str(plan_path)])
    rc = mod.main()
    assert rc == 1


def test_non_frontier_skips_frontier_checks(tmp_path):
    """Non-frontier projects shouldn't trigger frontier-specific checks."""
    mod = load_module()
    # Strip out frontier sections; project is not tagged frontier.
    body = MINIMAL_VALID_BODY.replace("## Playbook Usage Contract\n\n- Reuse mode: pattern_only\n- Matched playbooks: none\n\n", "")
    body = body.replace("## Why This Cannot Just Be The Playbook\n\nThis is a frontier project. No prior art exists.\n\n", "")
    plan_path = tmp_path / "plan.md"
    write_plan(plan_path, body, tags=["plan"])  # no "frontier" tag

    report = mod.validate_plan_compliance(plan_path)
    # Frontier-specific checks should be absent.
    check_names = {c["name"] for c in report["checks"]}
    assert "frontier_reuse_mode_pattern_only" not in check_names
    assert "frontier_section_playbook_usage_contract_present" not in check_names
