from __future__ import annotations

import importlib.util
import sys
import textwrap
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PLAN_STRESS_RERUN_PATH = REPO_ROOT / "scripts" / "plan_stress_rerun.py"


def load_module(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def write_report(path: Path, text: str) -> None:
    path.write_text(textwrap.dedent(text).strip() + "\n", encoding="utf-8")


def test_full_catalog_fail_recommends_targeted_rerun_pack(tmp_path):
    planner = load_module("plan_stress_rerun_full_fail", PLAN_STRESS_RERUN_PATH)
    report_path = tmp_path / "report.md"
    write_report(
        report_path,
        """
        ---
        type: snapshot
        subtype: stress-test-report
        title: "Stress Test Report — Example App"
        verdict: FAIL
        ---

        # Stress Test Report — Example App

        ## Verdict

        **FAIL**

        - Blockers: `2`
        - Majors: `3`
        - Minors: `1`

        This run executed all 61 catalog scenarios.

        ## Findings

        | Severity | Scenario | Verdict | Evidence | Note |
        |---|---|---|---|---|
        | blocker | `A-3` | `FAIL` | log | Lint fails |
        | major | `C-6` | `FAIL` | screenshot | Handoff banner missing |
        | major | `CF-2` | `FAIL` | api | Approvals stale |
        """,
    )

    report = planner.parse_report(report_path)
    recommendation = planner.determine_recommendation(report)

    assert report["current_scope"] == "full_catalog"
    assert recommendation["next_scope"] == "targeted_plus_regressions"
    assert recommendation["next_action"] == "create_fix_tickets_then_rerun"
    assert "A-3" in recommendation["target_scenarios"]
    assert "C-6" in recommendation["target_scenarios"]
    assert "CF-2" in recommendation["target_scenarios"]


def test_targeted_rerun_with_one_remaining_major_recommends_targeted_findings(tmp_path):
    planner = load_module("plan_stress_rerun_targeted_fail", PLAN_STRESS_RERUN_PATH)
    report_path = tmp_path / "report.md"
    write_report(
        report_path,
        """
        ---
        type: snapshot
        subtype: stress-test-report
        title: "Stress Test Rerun v3 Report — Example App"
        verdict: FAIL
        ---

        # Stress Test Rerun v3 Report — Example App

        ## Verdict

        **FAIL**

        - Blockers: `0`
        - Majors: `1`
        - New issues in this targeted rerun scope: `0`
        - Failing scenario: `C-6`

        This rerun was not a full 61-scenario replay.

        ## Findings

        | Severity | Scenario | Verdict | Evidence | Note |
        |---|---|---|---|---|
        | major | `C-6` corrupt handoff frontmatter | `FAIL` | screenshot | Handoff banner missing |
        """,
    )

    report = planner.parse_report(report_path)
    recommendation = planner.determine_recommendation(report)

    assert report["current_scope"] == "targeted_plus_regressions"
    assert recommendation["next_scope"] == "targeted_findings"
    assert recommendation["target_scenarios"][0] == "C-6"


def test_clean_targeted_rerun_requires_final_confirmation(tmp_path):
    planner = load_module("plan_stress_rerun_targeted_pass", PLAN_STRESS_RERUN_PATH)
    report_path = tmp_path / "report.md"
    write_report(
        report_path,
        """
        ---
        type: snapshot
        subtype: stress-test-report
        title: "Stress Test Rerun v4 Report — Example App"
        verdict: PASS
        ---

        # Stress Test Rerun v4 Report — Example App

        ## Verdict

        **PASS**

        - Blockers: `0`
        - Majors: `0`
        - Minors: `0`

        This rerun was intentionally limited and was not a full 61-scenario replay.

        ## Scenario Verdicts

        | Scenario | Verdict | Evidence | Note |
        |---|---|---|---|
        | `C-6` | `PASS` | screenshot | Banner visible |
        | `D-10` | `PASS` | api | Bootstrap guard still holds |
        """,
    )

    report = planner.parse_report(report_path)
    recommendation = planner.determine_recommendation(report)

    assert recommendation["next_scope"] == "final_confirmation"
    assert recommendation["next_action"] == "run_final_confirmation"
    assert recommendation["final_confirmation_required"] is True
    assert "C-6" in recommendation["target_scenarios"]


def test_final_confirmation_pass_allows_phase_completion(tmp_path):
    planner = load_module("plan_stress_rerun_final_pass", PLAN_STRESS_RERUN_PATH)
    report_path = tmp_path / "report.md"
    write_report(
        report_path,
        """
        ---
        type: snapshot
        subtype: stress-test-report
        title: "Stress Test Final Confirmation Report — Example App"
        verdict: PASS
        rerun_scope: final_confirmation
        ---

        # Stress Test Final Confirmation Report — Example App

        ## Verdict

        **PASS**

        - Blockers: `0`
        - Majors: `0`
        - Minors: `0`
        """,
    )

    report = planner.parse_report(report_path)
    recommendation = planner.determine_recommendation(report)

    assert report["current_scope"] == "final_confirmation"
    assert recommendation["next_scope"] == "phase_complete"
    assert recommendation["next_action"] == "complete_phase"


def test_targeted_rerun_with_two_severe_families_recommends_targeted_plus_regressions(tmp_path):
    planner = load_module("plan_stress_rerun_two_family_fail", PLAN_STRESS_RERUN_PATH)
    report_path = tmp_path / "report.md"
    write_report(
        report_path,
        """
        ---
        type: snapshot
        subtype: stress-test-report
        title: "Stress Test Rerun v4 Report — Example App"
        verdict: FAIL
        ---

        # Stress Test Rerun v4 Report — Example App

        ## Verdict

        **FAIL**

        - Blockers: `1`
        - Majors: `1`
        - New issues in this targeted rerun scope: `1`

        This rerun was not a full 61-scenario replay.

        ## Findings

        | Severity | Scenario | Verdict | Evidence | Note |
        |---|---|---|---|---|
        | major | `C-6` | `FAIL` | screenshot | Handoff banner missing |
        | blocker | `D-10` | `FAIL` | api | Bootstrap guard reopened |

        ## Scenario Verdicts

        | Scenario | Verdict | Evidence | Note |
        |---|---|---|---|
        | `C-6` | `FAIL` | screenshot | Handoff banner missing |
        | `D-10` | `FAIL` | api | Bootstrap guard reopened |
        | `D-11` | `PASS` | api | Host header reject still works |
        """,
    )

    report = planner.parse_report(report_path)
    recommendation = planner.determine_recommendation(report)

    assert recommendation["next_scope"] == "targeted_plus_regressions"
    assert "C-6" in recommendation["target_scenarios"]
    assert "D-10" in recommendation["target_scenarios"]
    assert "D-11" in recommendation["target_scenarios"]
