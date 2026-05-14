#!/usr/bin/env python3
"""Generate cohort-controlled aesthetic preset change proposals from outcome telemetry."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from visual_spec_telemetry_common import (
    PROPOSAL_SCHEMA_PATH,
    load_outcomes_with_metadata,
    mean,
    outcome_operator_id,
    outcome_primary_reviewer,
    parse_timestamp_from_path,
    pct,
    platform_value,
    proposal_regression_status,
    repo_relative,
    utc_now_iso,
    validate_artifact,
    write_json,
)


@dataclass
class Candidate:
    key: tuple[str, str, str]
    axis_or_token: str
    current_value: Any
    proposed_value: Any
    override_records: list[dict[str, Any]]
    baseline_records: list[dict[str, Any]]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--outcomes-dir", required=True, help="Directory containing visual-spec-outcome-*.json files.")
    parser.add_argument("--preset", required=True, help="Preset name to evaluate.")
    parser.add_argument("--out", help="Optional markdown output override.")
    parser.add_argument("--json-out", help="Optional path to write JSON output.")
    return parser.parse_args()


def scalar_key(value: Any) -> str:
    """Normalize scalar-ish values for grouping."""
    return json.dumps(value, sort_keys=True, ensure_ascii=True)


def build_candidates(outcomes: list[dict[str, Any]], preset: str) -> list[Candidate]:
    """Group same-direction overrides into proposal candidates."""
    by_key: dict[tuple[str, str, str], list[tuple[dict[str, Any], dict[str, Any]]]] = defaultdict(list)
    for outcome in outcomes:
        if outcome.get("visual_quality_target_preset") != preset:
            continue
        overrides = outcome.get("preset_default_overrides")
        if not isinstance(overrides, list):
            continue
        for override in overrides:
            if not isinstance(override, dict):
                continue
            if override.get("override_reason") != "aesthetic-default-wrong":
                continue
            key = (
                str(override.get("axis_or_token") or ""),
                scalar_key(override.get("preset_default")),
                scalar_key(override.get("project_value")),
            )
            by_key[key].append((outcome, override))

    candidates: list[Candidate] = []
    for key, records in by_key.items():
        axis_or_token = key[0]
        override_records = []
        override_projects = {str(outcome.get("project") or "") for outcome, _override in records}
        for outcome, override in records:
            override_records.append({"outcome": outcome, "override": override})
        baseline_records = []
        for outcome in outcomes:
            if outcome.get("visual_quality_target_preset") != preset:
                continue
            if str(outcome.get("project") or "") in override_projects:
                continue
            overrides = outcome.get("preset_default_overrides")
            axis_seen = False
            if isinstance(overrides, list):
                for override in overrides:
                    if isinstance(override, dict) and str(override.get("axis_or_token") or "") == axis_or_token:
                        axis_seen = True
                        break
            if not axis_seen:
                baseline_records.append(outcome)
        current_value = records[0][1].get("preset_default")
        proposed_value = records[0][1].get("project_value")
        candidates.append(Candidate(key, axis_or_token, current_value, proposed_value, override_records, baseline_records))

    candidates.sort(key=lambda item: (-len(item.override_records), item.axis_or_token, scalar_key(item.proposed_value)))
    return candidates


def grade_points(outcome: dict[str, Any]) -> float | None:
    """Return delivery-grade points for one outcome."""
    from visual_spec_telemetry_common import grade_to_points

    return grade_to_points(outcome.get("delivery_review_grade"))


def acceptance_rate(records: list[dict[str, Any]]) -> float:
    """Return positive operator acceptance percentage."""
    from visual_spec_telemetry_common import acceptance_positive

    if not records:
        return 0.0
    accepted = sum(1 for record in records if acceptance_positive(record.get("operator_acceptance")))
    return pct(accepted, len(records))


def revisions_mean(records: list[dict[str, Any]]) -> float | None:
    """Return mean revision count."""
    values = [float(record.get("revision_count_during_build")) for record in records if record.get("revision_count_during_build") is not None]
    return mean(values)


def grade_mean(records: list[dict[str, Any]]) -> float | None:
    """Return mean delivery grade points."""
    values = [points for points in (grade_points(record) for record in records) if points is not None]
    return mean(values)


def project_timestamp(outcome: dict[str, Any]) -> Any:
    """Return stable timestamp for ordering."""
    return outcome.get("_timestamp") or parse_timestamp_from_path(Path(str(outcome.get("_source_path") or "")))


def candidate_metrics(candidate: Candidate) -> dict[str, Any]:
    """Compute cohort and effect-size metrics for a candidate."""
    override_outcomes = [record["outcome"] for record in candidate.override_records]
    baseline_outcomes = candidate.baseline_records
    distinct_clients = {str(item.get("client_id") or "") for item in override_outcomes if str(item.get("client_id") or "").strip()}
    distinct_orgs = {str(item.get("client_organization_id") or "") for item in override_outcomes if str(item.get("client_organization_id") or "").strip()}
    distinct_domains = {str(item.get("client_domain") or "") for item in override_outcomes if str(item.get("client_domain") or "").strip()}
    reviewers = [outcome_primary_reviewer(item) or "" for item in override_outcomes]
    reviewer_counts = Counter([item for item in reviewers if item])
    domain_counts = Counter([str(item.get("client_domain") or "") for item in override_outcomes if str(item.get("client_domain") or "").strip()])
    operators = [outcome_operator_id(item) or "" for item in override_outcomes]
    operator_known = all(bool(item) for item in operators) and bool(operators)
    pair_counts = Counter(
        [
            f"{reviewer}|{operator}"
            for reviewer, operator in zip(reviewers, operators)
            if reviewer and operator
        ]
    )
    override_grade_mean = grade_mean(override_outcomes)
    baseline_grade_mean = grade_mean(baseline_outcomes)
    override_revisions_mean = revisions_mean(override_outcomes)
    baseline_revisions_mean = revisions_mean(baseline_outcomes)
    override_acceptance = acceptance_rate(override_outcomes)
    baseline_acceptance = acceptance_rate(baseline_outcomes)

    if baseline_revisions_mean and baseline_revisions_mean > 0 and override_revisions_mean is not None:
        revision_reduction_pct = round(((baseline_revisions_mean - override_revisions_mean) / baseline_revisions_mean) * 100.0, 2)
    else:
        revision_reduction_pct = 0.0
    grade_delta = round((override_grade_mean or 0.0) - (baseline_grade_mean or 0.0), 3) if override_grade_mean is not None and baseline_grade_mean is not None else None

    return {
        "project_count": len(override_outcomes),
        "distinct_clients": len(distinct_clients),
        "distinct_organizations": len(distinct_orgs),
        "distinct_domains": len(distinct_domains),
        "max_domain_concentration_pct": pct(max(domain_counts.values(), default=0), len(override_outcomes)) if override_outcomes else 0.0,
        "max_reviewer_concentration_pct": pct(max(reviewer_counts.values(), default=0), len(override_outcomes)) if override_outcomes else 0.0,
        "reviewer_diversity_count": len(reviewer_counts),
        "reviewer_operator_coupling_pct": pct(max(pair_counts.values(), default=0), len(override_outcomes)) if pair_counts else None,
        "operator_attribution_complete": operator_known,
        "override_grade_mean": override_grade_mean,
        "baseline_grade_mean": baseline_grade_mean,
        "delivery_grade_delta": grade_delta,
        "override_revisions_mean": override_revisions_mean,
        "baseline_revisions_mean": baseline_revisions_mean,
        "revision_reduction_pct": revision_reduction_pct,
        "override_acceptance_rate_pct": override_acceptance,
        "baseline_acceptance_rate_pct": baseline_acceptance,
        "projects": [str(item.get("project") or "") for item in override_outcomes],
        "override_outcomes": override_outcomes,
        "baseline_outcomes": baseline_outcomes,
    }


def holdout_metrics(candidate: Candidate, metrics: dict[str, Any], min_projects: int, holdout_min: int) -> dict[str, Any]:
    """Split override projects into training and holdout sets."""
    ordered = sorted(
        metrics["override_outcomes"],
        key=lambda item: (project_timestamp(item) or datetime.min.replace(tzinfo=timezone.utc), str(item.get("project") or "")),
    )
    training = ordered[:min_projects]
    holdout = ordered[min_projects : min_projects + holdout_min]
    if len(training) < min_projects or len(holdout) < holdout_min:
        return {
            "training_count": len(training),
            "holdout_count": len(holdout),
            "pass": False,
            "reason": "insufficient_holdout_projects",
            "grade_delta": None,
            "revision_reduction_pct": None,
            "acceptance_rate_pct": None,
        }
    baseline = metrics["baseline_outcomes"]
    holdout_grade = grade_mean(holdout)
    baseline_grade = grade_mean(baseline)
    holdout_revision_mean = revisions_mean(holdout)
    baseline_revision_mean = revisions_mean(baseline)
    holdout_acceptance = acceptance_rate(holdout)
    baseline_acceptance = acceptance_rate(baseline)
    if baseline_revision_mean and baseline_revision_mean > 0 and holdout_revision_mean is not None:
        holdout_revision_delta = round(((baseline_revision_mean - holdout_revision_mean) / baseline_revision_mean) * 100.0, 2)
    else:
        holdout_revision_delta = 0.0
    holdout_grade_delta = round((holdout_grade or 0.0) - (baseline_grade or 0.0), 3) if holdout_grade is not None and baseline_grade is not None else None
    passes = bool(
        holdout_grade_delta is not None
        and holdout_grade_delta > 0
        and holdout_revision_delta > 0
        and holdout_acceptance >= baseline_acceptance
    )
    return {
        "training_count": len(training),
        "holdout_count": len(holdout),
        "pass": passes,
        "reason": "ok" if passes else "holdout_direction_mismatch",
        "grade_delta": holdout_grade_delta,
        "revision_reduction_pct": holdout_revision_delta,
        "acceptance_rate_pct": holdout_acceptance,
    }


def run_subprocess_json(command: list[str]) -> dict[str, Any]:
    """Run a helper script and parse its JSON stdout."""
    completed = subprocess.run(command, capture_output=True, text=True, check=False, cwd=SCRIPT_DIR.parent)
    if completed.returncode not in {0, 1}:
        raise RuntimeError(f"{command[0]} exited {completed.returncode}: {completed.stderr.strip()}")
    payload = json.loads(completed.stdout or "{}")
    return payload if isinstance(payload, dict) else {}


def run_tag_audit(outcomes_dir: Path, preset: str) -> dict[str, Any]:
    """Run the independent override-tag audit."""
    llm_mode = os.environ.get("VISUAL_TELEMETRY_AUDIT_LLM_MODE", "stub")
    command = [
        sys.executable,
        str((SCRIPT_DIR / "audit_override_tags.py").resolve()),
        "--outcomes-dir",
        str(outcomes_dir),
        "--preset",
        preset,
        "--llm-mode",
        llm_mode,
    ]
    return run_subprocess_json(command)


def infer_medium_plugin(metrics: dict[str, Any]) -> Path | None:
    """Infer the medium plugin path from cohort outcomes."""
    mediums = Counter(str(item.get("visual_quality_target_medium") or "") for item in metrics["override_outcomes"])
    if not mediums:
        return None
    medium = mediums.most_common(1)[0][0]
    candidate = (SCRIPT_DIR.parent / "vault" / "archive" / "visual-aesthetics" / "mediums" / f"{medium}.md").resolve()
    return candidate if candidate.exists() else None


def regression_report_path(preset: str, axis_or_token: str, proposed_value: Any) -> Path:
    """Return the default regression report path."""
    safe = scalar_key(proposed_value).strip('"').replace("/", "-").replace(" ", "-")
    stem = f"{preset}-{axis_or_token.replace('.', '-')}-{safe}".replace("--", "-")
    stem = "".join(char if char.isalnum() or char in {"-", "_", "."} else "-" for char in stem).strip("-")
    root_override = os.environ.get("VISUAL_SPEC_REGRESSION_REPORT_DIR")
    root = Path(root_override).expanduser() if root_override else SCRIPT_DIR.parent / "vault" / "archive" / "visual-aesthetics" / "proposals" / "reports"
    return (root / f"{stem}-regression.json").resolve()


def run_regression(preset: str, candidate: Candidate, outcomes_dir: Path, report_path: Path) -> dict[str, Any]:
    """Run the replay-based regression check."""
    report_path.parent.mkdir(parents=True, exist_ok=True)
    medium_plugin = infer_medium_plugin(candidate_metrics(candidate))
    if medium_plugin is None:
        payload = {
            "proposal_id": f"{preset}-{candidate.axis_or_token}",
            "method": "simulate_only",
            "mockups_re_rendered": 0,
            "semantic_layout_regressions": [],
            "hierarchy_contrast_regressions": [],
            "pass": False,
            "regression_status": "operator_review_required",
            "unsupported_mediums": [],
        }
        report_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return payload
    command = [
        sys.executable,
        str((SCRIPT_DIR / "preset_regression_check.py").resolve()),
        "--proposed-change",
        f"{candidate.axis_or_token}={candidate.proposed_value}",
        "--preset",
        preset,
        "--historical-vs-dir",
        str(outcomes_dir),
        "--medium-plugin",
        str(medium_plugin),
        "--json-out",
        str(report_path),
    ]
    return run_subprocess_json(command)


def rejected_alternatives(candidate: Candidate, candidates: list[Candidate]) -> list[dict[str, Any]]:
    """Generate at least two rejected alternatives."""
    alternatives = [
        {"value": candidate.current_value, "reason": "Keeping the current default leaves the same override cluster unresolved."}
    ]
    alternate_values = []
    for item in candidates:
        if item.axis_or_token != candidate.axis_or_token:
            continue
        if scalar_key(item.proposed_value) == scalar_key(candidate.proposed_value):
            continue
        alternate_values.append(item.proposed_value)
    if alternate_values:
        alternatives.append(
            {
                "value": alternate_values[0],
                "reason": "A different override value appeared less often than the proposed direction in historical outcomes.",
            }
        )
    else:
        alternatives.append(
            {
                "value": candidate.proposed_value,
                "reason": "Project-by-project manual overrides alone do not improve the preset default for future work.",
            }
        )
    return alternatives[:2]


def cohort_pass(metrics: dict[str, Any]) -> tuple[bool, list[str]]:
    """Evaluate hard cohort diversity thresholds."""
    reasons: list[str] = []
    min_projects = int(platform_value("visual_spec_aesthetic_proposal_min_projects", 5))
    min_orgs = int(platform_value("visual_spec_telemetry_distinct_organizations_min", 3))
    max_domain_pct = float(platform_value("visual_spec_telemetry_max_domain_concentration_pct", 50))
    max_reviewer_pct = float(platform_value("visual_spec_telemetry_max_reviewer_concentration_pct", 40))
    max_coupling_pct = float(platform_value("visual_spec_telemetry_reviewer_operator_coupling_max_pct", 60))

    if metrics["project_count"] < min_projects:
        reasons.append(f"fewer than {min_projects} override projects")
    if metrics["distinct_organizations"] < min_orgs:
        reasons.append(f"fewer than {min_orgs} distinct organizations")
    if metrics["max_domain_concentration_pct"] > max_domain_pct:
        reasons.append(f"single-domain concentration {metrics['max_domain_concentration_pct']:.2f}% exceeds {max_domain_pct}%")
    if metrics["max_reviewer_concentration_pct"] > max_reviewer_pct:
        reasons.append(f"single-reviewer concentration {metrics['max_reviewer_concentration_pct']:.2f}% exceeds {max_reviewer_pct}%")
    if metrics["operator_attribution_complete"] and (metrics["reviewer_operator_coupling_pct"] or 0.0) > max_coupling_pct:
        reasons.append(f"reviewer/operator coupling {metrics['reviewer_operator_coupling_pct']:.2f}% exceeds {max_coupling_pct}%")
    return (not reasons), reasons


def effect_pass(metrics: dict[str, Any]) -> tuple[bool, list[str]]:
    """Evaluate effect-size thresholds."""
    reasons: list[str] = []
    min_grade = float(platform_value("visual_spec_telemetry_min_effect_size_grade_points", 0.5))
    min_revision_reduction = float(platform_value("visual_spec_telemetry_min_revision_reduction_pct", 30))
    min_acceptance = float(platform_value("visual_spec_telemetry_min_operator_acceptance_pct", 80))

    if metrics["delivery_grade_delta"] is None or metrics["delivery_grade_delta"] < min_grade:
        reasons.append(f"delivery grade delta {metrics['delivery_grade_delta']} is below {min_grade}")
    if metrics["revision_reduction_pct"] < min_revision_reduction:
        reasons.append(f"revision reduction {metrics['revision_reduction_pct']:.2f}% is below {min_revision_reduction}%")
    if metrics["override_acceptance_rate_pct"] < min_acceptance:
        reasons.append(f"operator acceptance {metrics['override_acceptance_rate_pct']:.2f}% is below {min_acceptance}%")
    return (not reasons), reasons


def promising_signal(metrics: dict[str, Any]) -> bool:
    """Return true when a candidate is directionally positive but underpowered."""
    min_projects = int(platform_value("visual_spec_telemetry_promising_signal_min_projects", 2))
    if metrics["project_count"] < min_projects:
        return False
    grade_positive = metrics["delivery_grade_delta"] is not None and metrics["delivery_grade_delta"] > 0
    revisions_positive = metrics["revision_reduction_pct"] > 0
    acceptance_positive = metrics["override_acceptance_rate_pct"] >= metrics["baseline_acceptance_rate_pct"]
    return grade_positive and revisions_positive and acceptance_positive


def proposal_output_path(args: argparse.Namespace, preset: str, promising: bool = False) -> Path:
    """Resolve the markdown output path."""
    if args.out:
        return Path(args.out).expanduser().resolve()
    if promising:
        root = platform_value(
            "visual_spec_telemetry_promising_signals_path",
            "vault/archive/visual-aesthetics/proposals/_promising-but-insufficient/",
        )
        return (SCRIPT_DIR.parent / str(root) / f"{preset}-{utc_now_iso()[:10]}-promising.md").resolve()
    return (SCRIPT_DIR.parent / "vault" / "archive" / "visual-aesthetics" / "proposals" / f"{preset}-{utc_now_iso()[:10]}-proposal.md").resolve()


def body_markdown(candidate: Candidate, metrics: dict[str, Any], holdout: dict[str, Any], regression: dict[str, Any], rejected: list[dict[str, Any]], recommended_action: str) -> str:
    """Render proposal markdown body."""
    proposal_title = f"# Proposal: {candidate.axis_or_token} {candidate.current_value} -> {candidate.proposed_value}"
    evidence_table = [
        "| Metric | Override Cohort | Baseline Cohort | Delta |",
        "|--------|-----------------|-----------------|-------|",
        f"| Projects | {metrics['project_count']} | {len(metrics['baseline_outcomes'])} | — |",
        f"| Mean delivery grade (points) | {metrics['override_grade_mean']} | {metrics['baseline_grade_mean']} | {metrics['delivery_grade_delta']} |",
        f"| Mean revisions during build | {metrics['override_revisions_mean']} | {metrics['baseline_revisions_mean']} | {metrics['revision_reduction_pct']:.2f}% reduction |",
        f"| Operator acceptance rate | {metrics['override_acceptance_rate_pct']:.2f}% | {metrics['baseline_acceptance_rate_pct']:.2f}% | {metrics['override_acceptance_rate_pct'] - metrics['baseline_acceptance_rate_pct']:.2f} pts |",
        f"| Holdout validation | {holdout['holdout_count']} projects | — | {'pass' if holdout['pass'] else holdout['reason']} |",
    ]
    regression_projects = sorted(
        {item["project"] for item in regression.get("semantic_layout_regressions", []) + regression.get("hierarchy_contrast_regressions", [])}
    )
    cache_dir = SCRIPT_DIR.parent / "vault" / "cache" / "visual-spec" / "regression" / regression.get("proposal_id", "")
    thumbnail_lines = []
    if cache_dir.exists():
        for before in sorted(cache_dir.rglob("before.png"))[:6]:
            after = before.with_name("after.png")
            if after.exists():
                thumbnail_lines.append(f"- Before: {repo_relative(before)}")
                thumbnail_lines.append(f"- After: {repo_relative(after)}")
    if not thumbnail_lines:
        thumbnail_lines.append("- No replay thumbnails were generated.")

    rejected_lines = [f"- {item['value']}: {item['reason']}" for item in rejected]
    return "\n".join(
        [
            proposal_title,
            "",
            "## Evidence summary",
            *evidence_table,
            "",
            "## Before/after thumbnails",
            *thumbnail_lines,
            "",
            "## Regression check details",
            f"- Method: {regression.get('method')}",
            f"- Status: {proposal_regression_status({'regression_check': {'status': regression.get('regression_status')}}) or regression.get('regression_status')}",
            f"- Mockups re-rendered: {regression.get('mockups_re_rendered')}",
            f"- Regressed projects: {', '.join(regression_projects) if regression_projects else 'none'}",
            "",
            "## Rejected alternatives",
            *rejected_lines,
            "",
            "## Recommended action",
            f"{recommended_action}",
            "",
            "Operator: pending",
            "",
        ]
    )


def write_markdown(path: Path, frontmatter: dict[str, Any], body: str) -> dict[str, Any]:
    """Write markdown with YAML frontmatter and validate it."""
    path.parent.mkdir(parents=True, exist_ok=True)
    yaml_text = yaml.safe_dump(frontmatter, sort_keys=False, allow_unicode=False).strip()
    content = f"---\n{yaml_text}\n---\n\n{body}"
    path.write_text(content, encoding="utf-8")
    validation = validate_artifact(path, PROPOSAL_SCHEMA_PATH, "yaml-frontmatter")
    return validation


def promising_payload(args: argparse.Namespace, preset: str, candidate: Candidate, metrics: dict[str, Any], reasons: list[str]) -> dict[str, Any]:
    """Write a promising-but-insufficient signal artifact."""
    path = proposal_output_path(args, preset, promising=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    frontmatter = {
        "type": "promising-telemetry-signal",
        "preset": preset,
        "proposed_change": f"{candidate.axis_or_token} {candidate.current_value} -> {candidate.proposed_value}",
        "projects_observed": metrics["project_count"],
        "distinct_organizations": metrics["distinct_organizations"],
        "direction_consistent": True,
        "positive_outcome_indicator": True,
        "data_richness": "insufficient_for_auto_proposal",
        "status": "promising",
    }
    body = "\n".join(
        [
            f"# Promising Telemetry — {preset} {candidate.axis_or_token}",
            "",
            "## Signal summary",
            f"{metrics['project_count']} projects show consistent improvement with override. {', '.join(reasons)}.",
            "",
            "## Recommended action",
            "- Continue collecting data",
            "- Operator may manually approve preset update if accumulated experience supports it",
            "- Re-evaluate when data richness improves",
            "",
            "## Manual approval path (operator override)",
            'If operator approves manually with reasoning recorded, preset update lands as v1.x but is tracked as "low-data manual approval".',
            "",
        ]
    )
    path.write_text(f"---\n{yaml.safe_dump(frontmatter, sort_keys=False).strip()}\n---\n\n{body}", encoding="utf-8")
    return {
        "status": "promising_signal",
        "written_path": repo_relative(path),
        "recommended_action": "collect_more_data_or_manual_low_data_review",
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    outcomes_dir = Path(args.outcomes_dir).expanduser().resolve()
    outcomes, invalid_outcomes = load_outcomes_with_metadata(outcomes_dir)
    preset_outcomes = [outcome for outcome in outcomes if outcome.get("visual_quality_target_preset") == args.preset]
    if not preset_outcomes:
        return {
            "preset": args.preset,
            "generated_at": utc_now_iso(),
            "verdict": "no_data_yet",
            "recommended_action": "await_more_outcomes",
            "written_path": None,
            "evaluated_candidates": [],
            "invalid_outcomes": invalid_outcomes,
        }

    min_projects = int(platform_value("visual_spec_aesthetic_proposal_min_projects", 5))
    holdout_min = int(platform_value("visual_spec_telemetry_holdout_min_projects", 3))
    candidates = build_candidates(outcomes, args.preset)
    evaluated: list[dict[str, Any]] = []
    audit = run_tag_audit(outcomes_dir, args.preset)
    best: tuple[Candidate, dict[str, Any], dict[str, Any], list[str], list[str]] | None = None
    promising_best: tuple[Candidate, dict[str, Any], list[str]] | None = None

    for candidate in candidates:
        metrics = candidate_metrics(candidate)
        cohort_ok, cohort_reasons = cohort_pass(metrics)
        effect_ok, effect_reasons = effect_pass(metrics)
        holdout = holdout_metrics(candidate, metrics, min_projects, holdout_min)
        record = {
            "axis_or_token": candidate.axis_or_token,
            "current_value": candidate.current_value,
            "proposed_value": candidate.proposed_value,
            "metrics": metrics,
            "cohort_pass": cohort_ok,
            "cohort_fail_reasons": cohort_reasons,
            "effect_pass": effect_ok,
            "effect_fail_reasons": effect_reasons,
            "holdout": holdout,
        }
        evaluated.append(record)
        if promising_signal(metrics) and (promising_best is None or metrics["project_count"] > promising_best[1]["project_count"]):
            promising_best = (candidate, metrics, cohort_reasons + effect_reasons + ([] if holdout["pass"] else [holdout["reason"]]))
        if best is None and metrics["project_count"] >= min_projects:
            best = (candidate, metrics, holdout, cohort_reasons, effect_reasons)

    if best is None:
        if promising_best is not None:
            candidate, metrics, reasons = promising_best
            promising = promising_payload(args, args.preset, candidate, metrics, reasons or ["below auto-proposal threshold"])
            return {
                "preset": args.preset,
                "generated_at": utc_now_iso(),
                "verdict": "promising_signal",
                "recommended_action": promising["recommended_action"],
                "written_path": promising["written_path"],
                "evaluated_candidates": evaluated,
                "invalid_outcomes": invalid_outcomes,
                "audit": audit,
            }
        return {
            "preset": args.preset,
            "generated_at": utc_now_iso(),
            "verdict": "no_data_yet",
            "recommended_action": "await_more_outcomes",
            "written_path": None,
            "evaluated_candidates": evaluated,
            "invalid_outcomes": invalid_outcomes,
            "audit": audit,
        }

    candidate, metrics, holdout, cohort_reasons, effect_reasons = best
    if cohort_reasons:
        return {
            "preset": args.preset,
            "generated_at": utc_now_iso(),
            "verdict": "insufficient_cohort_diversity",
            "recommended_action": "collect_more_distinct_cohort_evidence",
            "written_path": None,
            "evaluated_candidates": evaluated,
            "invalid_outcomes": invalid_outcomes,
            "audit": audit,
            "cohort_fail_reasons": cohort_reasons,
        }

    regression_path = regression_report_path(args.preset, candidate.axis_or_token, candidate.proposed_value)
    regression = run_regression(args.preset, candidate, outcomes_dir, regression_path)
    audit_pass = audit.get("verdict") == "pass"
    rejected = rejected_alternatives(candidate, candidates)
    cohort_ok = not cohort_reasons
    effect_ok = not effect_reasons
    regression_ok = regression.get("regression_status") == "pass"
    holdout_ok = holdout.get("pass") is True

    if metrics["project_count"] < min_projects and promising_best is not None:
        candidate, metrics, reasons = promising_best
        promising = promising_payload(args, args.preset, candidate, metrics, reasons or ["below auto-proposal threshold"])
        return {
            "preset": args.preset,
            "generated_at": utc_now_iso(),
            "verdict": "promising_signal",
            "recommended_action": promising["recommended_action"],
            "written_path": promising["written_path"],
            "evaluated_candidates": evaluated,
            "invalid_outcomes": invalid_outcomes,
            "audit": audit,
        }

    if not effect_ok:
        return {
            "preset": args.preset,
            "generated_at": utc_now_iso(),
            "verdict": "insufficient_effect_size",
            "recommended_action": "collect_more_signal",
            "written_path": None,
            "evaluated_candidates": evaluated,
            "invalid_outcomes": invalid_outcomes,
            "audit": audit,
            "regression": regression,
        }

    if not audit_pass:
        recommended_action = "manual_tag_audit_review"
    elif not cohort_ok:
        recommended_action = "insufficient_cohort_diversity_operator_review"
    elif not holdout_ok:
        recommended_action = "holdout_validation_failed"
    elif not regression_ok:
        recommended_action = "regression_blocks_proposal"
    else:
        recommended_action = "approve"

    frontmatter = {
        "type": "preset-update-proposal",
        "preset": args.preset,
        "proposed_axis_or_token": candidate.axis_or_token,
        "current_value": candidate.current_value,
        "proposed_value": candidate.proposed_value,
        "projects_overriding": sorted(set(metrics["projects"])),
        "projects_with_aesthetic-default-wrong_reason": sorted(set(metrics["projects"])),
        "outcome_delta": {
            "revision_count_delta": round((metrics["override_revisions_mean"] or 0.0) - (metrics["baseline_revisions_mean"] or 0.0), 3),
            "operator_acceptance_delta_pct": round(metrics["override_acceptance_rate_pct"] - metrics["baseline_acceptance_rate_pct"], 2),
            "delivery_grade_delta": metrics["delivery_grade_delta"] or 0.0,
            "sample_size": len(metrics["override_outcomes"]) + len(metrics["baseline_outcomes"]),
        },
        "regression_check_result": regression.get("regression_status", "not_run"),
        "regression_check_projects_evaluated": int(regression.get("mockups_re_rendered", 0)),
        "regression_check_worse_projects": sorted(
            {
                item["project"]
                for item in regression.get("semantic_layout_regressions", []) + regression.get("hierarchy_contrast_regressions", [])
                if isinstance(item, dict) and item.get("project")
            }
        ),
        "rejected_alternatives": rejected,
        "cohort_check": {
            "distinct_clients": metrics["distinct_clients"],
            "distinct_organizations": metrics["distinct_organizations"],
            "distinct_domains": metrics["distinct_domains"],
            "reviewer_diversity_pass": metrics["reviewer_diversity_count"] >= 3 and metrics["max_reviewer_concentration_pct"] <= float(platform_value("visual_spec_telemetry_max_reviewer_concentration_pct", 40)),
            "holdout_validation_pass": holdout_ok,
        },
        "tag_audit": {
            "audited_projects": int(audit.get("sample_size", 0)),
            "invalid_tags": sorted({item.get("project", "") for item in audit.get("items", []) if item.get("auditor_classification") != "aesthetic-default-wrong" and item.get("project")}),
            "pass": audit_pass,
        },
        "regression_check": {
            "method": "manual_review" if regression.get("regression_status") == "operator_review_required" else regression.get("method", "simulate_only"),
            "status": regression.get("regression_status", "not_run"),
            "report_path": repo_relative(regression_path),
        },
        "operator_decision": "pending",
        "created": utc_now_iso(),
    }

    out_path = proposal_output_path(args, args.preset, promising=False)
    validation = write_markdown(out_path, frontmatter, body_markdown(candidate, metrics, holdout, regression, rejected, recommended_action))
    if not validation.get("valid"):
        raise RuntimeError(f"proposal frontmatter validation failed: {validation['errors']}")

    return {
        "preset": args.preset,
        "generated_at": utc_now_iso(),
        "verdict": "pass" if recommended_action == "approve" else "fail",
        "recommended_action": recommended_action,
        "written_path": repo_relative(out_path),
        "proposal_frontmatter": frontmatter,
        "proposal_validation": validation,
        "evaluated_candidates": evaluated,
        "invalid_outcomes": invalid_outcomes,
        "audit": audit,
        "regression": regression,
        "cohort_pass": cohort_ok,
        "effect_pass": effect_ok,
        "holdout_pass": holdout_ok,
    }


def main() -> int:
    args = parse_args()
    try:
        payload = build_payload(args)
        write_json(payload, args.json_out)
        return 0 if payload["verdict"] in {"pass", "promising_signal", "no_data_yet"} else 1
    except Exception as exc:
        write_json(
            {
                "preset": args.preset,
                "generated_at": utc_now_iso(),
                "verdict": "fail",
                "recommended_action": "error",
                "written_path": None,
                "error": str(exc),
            },
            args.json_out,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
