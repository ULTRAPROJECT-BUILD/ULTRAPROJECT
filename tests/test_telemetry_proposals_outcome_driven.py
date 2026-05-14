from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path

from visual_spec_test_utils import REPO_ROOT, load_json, run_script, vstest_tmp


AXES = {
    "density": "dense",
    "topology": "list_detail",
    "expressiveness": "restrained",
    "motion": "subtle",
    "platform": "web_native",
    "trust": "financial",
}


def outcome(
    project: str,
    *,
    org: str,
    domain: str,
    reviewer: str,
    override: bool,
    grade: str,
    revisions: int,
) -> dict:
    return {
        "project": project,
        "client_id": f"client-{project}",
        "client_organization_id": org,
        "client_domain": domain,
        "visual_quality_target_medium": "web_ui",
        "visual_quality_target_preset": "operator_triage",
        "visual_axes": AXES,
        "preset_default_overrides": [
            {
                "axis_or_token": "visual_axes.density",
                "preset_default": "balanced",
                "project_value": "dense",
                "override_reason": "aesthetic-default-wrong",
                "operator_approved": True,
            }
        ]
        if override
        else [],
        "visual_gate_first_attempt": "REVISE",
        "visual_gate_final": "PASS",
        "visual_gate_revision_rounds": revisions,
        "reviewer_grades": [{"reviewer_session_id": reviewer, "grade": grade, "verdict": "PASS"}],
        "operator_acceptance": "accepted",
        "revision_count_during_build": revisions,
        "delivery_review_grade": grade,
        "build_duration_hours": 4.0,
        "vs_phase_duration_hours": 1.0,
    }


def write_outcomes(root: Path, records: list[dict]) -> None:
    root.mkdir(parents=True, exist_ok=True)
    for index, record in enumerate(records, start=1):
        path = root / f"visual-spec-outcome-2026-05-{index:02d}-{record['project']}.json"
        path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")


def run_proposer(outcomes: Path, proposal: Path, json_out: Path, regression_dir: Path):
    return run_script(
        "aesthetic_change_proposer.py",
        "--outcomes-dir",
        str(outcomes),
        "--preset",
        "operator_triage",
        "--out",
        str(proposal),
        "--json-out",
        str(json_out),
        env={
            "VISUAL_TELEMETRY_AUDIT_LLM_MODE": "stub",
            "VISUAL_SPEC_REGRESSION_REPORT_DIR": str(regression_dir),
        },
    )


def test_telemetry_proposals_require_outcome_diverse_cohorts() -> None:
    regression_dir = REPO_ROOT / "tests" / ".tmp" / f"vs-regression-{uuid.uuid4().hex[:8]}"
    try:
        with vstest_tmp("telemetry") as tmp:
            same_org = tmp / "same-org"
            same_org_records = [
                outcome(f"same-override-{idx}", org="org-one", domain="fintech", reviewer=f"rev-{idx % 3}", override=True, grade="A", revisions=1)
                for idx in range(5)
            ] + [
                outcome(f"same-base-{idx}", org=f"base-org-{idx}", domain="baseline", reviewer=f"base-rev-{idx}", override=False, grade="B", revisions=4)
                for idx in range(5)
            ]
            write_outcomes(same_org, same_org_records)
            fail_json = tmp / "same-org.json"
            fail = run_proposer(same_org, tmp / "same-org-proposal.md", fail_json, regression_dir)
            fail_payload = load_json(fail_json)
            assert fail.returncode == 1
            assert fail_payload["verdict"] == "insufficient_cohort_diversity"
            assert fail_payload["written_path"] is None
            assert "fewer than 3 distinct organizations" in fail_payload["cohort_fail_reasons"]

            diverse = tmp / "diverse"
            orgs = ["org-a", "org-b", "org-c", "org-a", "org-b"]
            domains = ["fintech", "health", "gov", "fintech", "retail"]
            reviewers = ["rev-a", "rev-b", "rev-c", "rev-a", "rev-b"]
            diverse_records = [
                outcome(f"diverse-override-{idx}", org=orgs[idx], domain=domains[idx], reviewer=reviewers[idx], override=True, grade="A", revisions=1)
                for idx in range(5)
            ] + [
                outcome(f"diverse-base-{idx}", org=f"base-org-{idx}", domain=f"base-domain-{idx}", reviewer=f"base-rev-{idx}", override=False, grade="B-", revisions=4)
                for idx in range(5)
            ]
            write_outcomes(diverse, diverse_records)
            pass_json = tmp / "diverse.json"
            proposal_path = tmp / "diverse-proposal.md"
            passed = run_proposer(diverse, proposal_path, pass_json, regression_dir)
            pass_payload = load_json(pass_json)

            assert passed.returncode in {0, 1}
            assert pass_payload["written_path"] is not None
            assert proposal_path.exists()
            assert pass_payload["cohort_pass"] is True
            assert pass_payload["effect_pass"] is True
            frontmatter = pass_payload["proposal_frontmatter"]
            assert frontmatter["cohort_check"]["distinct_organizations"] == 3
            assert frontmatter["cohort_check"]["distinct_domains"] == 4
            assert frontmatter["outcome_delta"]["delivery_grade_delta"] > 0
            assert frontmatter["outcome_delta"]["revision_count_delta"] < 0
            assert len(frontmatter["projects_overriding"]) == 5
    finally:
        shutil.rmtree(regression_dir, ignore_errors=True)
