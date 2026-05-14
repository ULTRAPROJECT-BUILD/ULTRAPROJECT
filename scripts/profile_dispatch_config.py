#!/usr/bin/env python3
"""Profile dispatch config for ``check_visual_spec_gate.py``.

Each profile declares:
- description
- checks: ordered list of check IDs (integers 1..97) to run
- target_runtime_s: typical runtime expectation
- max_runtime_s: hard limit; gate ABORTs if exceeded
- skip_policy: how skipped checks affect the profile (``fail``, ``warn``, or ``pass``)
- cache_strategy: which cache categories to use
- execution_mode: ``sync`` or ``async``
"""

from __future__ import annotations

import argparse
import json
from typing import Any

ALL_CHECK_IDS = list(range(1, 99))

PROFILE_CACHE_CATEGORIES: dict[str, tuple[str, ...]] = {
    "none": (),
    "schema_and_lock_only": ("schema", "lock"),
    "phash_clip_render_full": ("phash", "clip", "render", "schema", "lock"),
    "phash_clip_full": ("phash", "clip", "render"),
    "render_full_with_persistent_cache": ("phash", "clip", "render", "schema", "lock", "telemetry"),
}

PROFILES: dict[str, dict[str, Any]] = {
    "brief": {
        "description": "Brief gate — specificity adequacy + collusion + frontmatter",
        "checks": [81, 82],
        "target_runtime_s": 5,
        "max_runtime_s": 30,
        "skip_policy": "warn",
        "cache_strategy": "none",
        "execution_mode": "sync",
    },
    "vs_fast": {
        "description": "VS lock fast path — validity + freshness + schema",
        "checks": [62, 63, 64, 72, 73, 79, 85, 86],
        "target_runtime_s": 5,
        "max_runtime_s": 15,
        "skip_policy": "fail",
        "cache_strategy": "schema_and_lock_only",
        "execution_mode": "sync",
    },
    "vs_full": {
        "description": "VS lock full gate — all 98 checks",
        "checks": ALL_CHECK_IDS,
        "target_runtime_s": 360,
        "max_runtime_s": 900,
        "skip_policy": "warn",
        "cache_strategy": "phash_clip_render_full",
        "execution_mode": "sync",
    },
    "runtime": {
        "description": "Runtime gate — post-build artifact verification",
        "checks": [
            18,
            21,
            22,
            35,
            36,
            37,
            38,
            39,
            40,
            44,
            45,
            46,
            52,
            53,
            54,
            55,
            56,
            57,
            66,
            77,
            80,
            87,
            88,
            89,
            90,
            91,
            92,
            93,
            94,
        ],
        "target_runtime_s": 300,
        "max_runtime_s": 900,
        "skip_policy": "fail",
        "cache_strategy": "phash_clip_full",
        "execution_mode": "sync",
    },
    "telemetry": {
        "description": "Telemetry regression — async, post-delivery",
        "checks": [74, 75, 76, 78, 82, 83, 84, 87, 88],
        "target_runtime_s": 1200,
        "max_runtime_s": 1800,
        "skip_policy": "warn",
        "cache_strategy": "render_full_with_persistent_cache",
        "execution_mode": "async",
    },
}

CHECK_DEFINITIONS: dict[int, dict[str, str]] = {
    1: {"name": "vs_exists", "description": "VS markdown exists at declared path"},
    2: {"name": "vs_frontmatter_visual_axes", "description": "VS frontmatter has visual_axes with all 6 values valid"},
    3: {"name": "vs_frontmatter_tokens_locked", "description": "VS frontmatter has tokens_locked: true"},
    4: {"name": "references_dir_exists", "description": "References dir exists at declared path"},
    5: {"name": "manifest_exists_parses", "description": "manifest.json exists, parses, contains required keys"},
    6: {"name": "min_3_reference_pngs", "description": "≥3 reference PNGs exist with non-zero size"},
    7: {"name": "min_1_antipattern_png", "description": "≥1 anti-pattern PNG exists"},
    8: {"name": "min_2_anchor_mockups_3_revisions", "description": "≥2 anchor mockups exist with ≥3 revisions each"},
    9: {"name": "all_token_families_present", "description": "All 8 token families present in manifest.tokens"},
    10: {"name": "token_completeness", "description": "≥10 colors, ≥5 type styles, ≥6 spacing, ≥4 radii, ≥3 motion timings"},
    11: {"name": "antipatterns_section_3_items", "description": "Anti-patterns section has ≥3 items, each ≥1 sentence"},
    12: {"name": "build_agent_gospel_present", "description": "Build agent gospel section present"},
    13: {"name": "signoff_exists", "description": "Sign-off exists with all reviewer questions answered"},
    14: {"name": "signoff_freshness", "description": "Sign-off within visual_spec_signoff_freshness_max_days of locked-at"},
    15: {"name": "png_dimensions", "description": "Every PNG has width ≥800 and height ≥600"},
    16: {"name": "png_nonblank", "description": "Shannon entropy + variance — reject single-color PNGs"},
    17: {"name": "reference_phash_uniqueness", "description": "Pairwise pHash distance > NOISE_FLOOR (8)"},
    18: {"name": "mockup_vs_antipattern_divergence", "description": "Mockup vs anti-pattern pHash distance > FORBIDDEN_PROXIMITY (12)"},
    19: {"name": "mockup_vs_reference_proximity_band", "description": "Mockup vs primary reference pHash in [TAKE_MIN, LITERAL_MAX] band"},
    20: {"name": "mockup_regen_parity_ssim", "description": "Regenerated mockup PNG SSIM ≥0.92 against captured PNG"},
    21: {"name": "css_token_ast_match", "description": "CSS AST extraction parity — manifest tokens match mockup CSS"},
    22: {"name": "wcag_aa_contrast", "description": "WCAG AA contrast on every text-color × surface-color combo"},
    23: {"name": "iteration_log_evidence", "description": "≥2 captured revisions per anchor with non-empty diffs"},
    24: {"name": "adjudication_session_uniqueness", "description": "Adjudication round reviewer_session_ids unique"},
    25: {"name": "adversarial_pass_session_uniqueness", "description": "Adversarial pass session distinct from adjudication sessions"},
    26: {"name": "adjudication_final_pass", "description": "Last adjudication round verdict is PASS"},
    27: {"name": "adversarial_pass_actionable", "description": "Adversarial pass verdict is ORIGINAL_DEFENDED or RESTART_REQUIRED"},
    28: {"name": "iteration_log_min_entries", "description": "iteration-log.md has ≥6 entries (2 anchors × ≥3 revisions)"},
    29: {"name": "token_semantic_naming", "description": "Color token keys are non-hex strings"},
    30: {"name": "token_consolidation_de76", "description": "No two color tokens with ΔE76 distance < 3"},
    31: {"name": "mtime_anti_laundering", "description": "PNG mtimes within ±1h of captured_at"},
    32: {"name": "reference_source_url_plausibility", "description": "Each reference source_url is plausible URL"},
    33: {"name": "adjudication_agent_identity", "description": "Adjudication reports written by recorded session IDs"},
    34: {"name": "no_author_self_signoff", "description": "Author session ID not in adjudication or adversarial pass reports"},
    35: {"name": "equal_weight_grid_detection", "description": "≥4 equal-weight siblings in flat grid → FAIL"},
    36: {"name": "hierarchy_contrast_ratio", "description": "max element weight / median ≥1.8"},
    37: {"name": "pane_dominance_ratio", "description": "Largest content pane area ≥1.5× second largest"},
    38: {"name": "component_role_mix", "description": "≥4 distinct component types"},
    39: {"name": "visible_token_instances", "description": "≥8 unique colors + ≥4 unique type styles in mockup"},
    40: {"name": "density_target_verification", "description": "Density: dense → ≥declared rows visible at 800pt"},
    41: {"name": "brand_application_diversity", "description": "Brand identity: ≥5 distinct application contexts"},
    42: {"name": "video_frame_motion", "description": "Video: sequential frame pHash distance > NOISE_FLOOR"},
    43: {"name": "render_lighting_sources", "description": "3D: ≥3 distinct light sources detected"},
    44: {"name": "mockup_clip_to_preset_centroid", "description": "Mockup CLIP distance in [0.20, 0.55] from preset centroid"},
    45: {"name": "mockup_clip_to_antipattern_centroid", "description": "Mockup CLIP distance > 0.50 from anti-pattern centroid"},
    46: {"name": "anchor_diversity_clip", "description": "Anchor mockup pairwise CLIP distance > 0.10"},
    47: {"name": "plugin_version_match", "description": "VS-declared medium_plugin_version matches current plugin file"},
    48: {"name": "mockup_format_match", "description": "Mockup files match medium plugin's declared format"},
    49: {"name": "anchor_count_meets_medium_min", "description": "Anchor count meets plugin's mockup_anchor_count_min"},
    50: {"name": "revisions_per_anchor_min", "description": "Per-anchor revisions meet plugin's min"},
    51: {"name": "token_family_completeness_per_medium", "description": "Each medium's token families all present and non-empty"},
    52: {"name": "domain_entity_coverage", "description": "≥80% of declared entities findable in mockup"},
    53: {"name": "workflow_signature_affordance_coverage", "description": "≥5 declared workflow verbs visible as UI controls"},
    54: {"name": "data_texture_match", "description": "Mockup data matches declared data_texture_requirements"},
    55: {"name": "brand_invariants_present", "description": "Each declared invariant visible at declared mockup_location"},
    56: {"name": "signature_affordance_count", "description": "≥3 declared signature affordances visible"},
    57: {"name": "forbidden_generic_signals_absent", "description": "Mockup contains NO declared forbidden phrase/layout/pattern"},
    58: {"name": "plugin_schema_validation", "description": "Medium plugin validates against schemas/medium-plugin.schema.json"},
    59: {"name": "mode_validation", "description": "visual_quality_target_mode is valid; preset/brand-system referenced exists"},
    60: {"name": "custom_mode_clip_centroid", "description": "When mode=custom, centroid computed from project references and used"},
    61: {"name": "brand_system_clip_centroid", "description": "When mode=brand_system, centroid from brand and used"},
    62: {"name": "immutable_vs_ids", "description": "visual_spec_id and revision_id are valid UUIDs; supersedes chain valid"},
    63: {"name": "active_deprecated_state", "description": "Only one revision per visual_spec_id has active=true"},
    64: {"name": "amendment_lock_state", "description": "No stale lock during gate run"},
    65: {"name": "specificity_contract_present", "description": "All 7 specificity fields populated with min counts"},
    66: {"name": "ocr_extractable_specificity", "description": "Mockup text content extractable, ≥1 readable line per anchor"},
    67: {"name": "reviewer_redline_field_linked", "description": "Adjudication redlines reference specificity-contract fields"},
    68: {"name": "brief_grounding_overlap", "description": "Declared specificity items overlap ≥70% with brief-extracted candidates"},
    69: {"name": "banned_vague_taxonomy_absence", "description": "No declared specificity item uses banned standalone term without qualifier"},
    70: {"name": "semantic_specificity_scoring", "description": "Per-item ≥0.4, average ≥0.6, fewer than 20% below 0.5"},
    71: {"name": "mode_none_waiver_presence", "description": "When ambition signals + mode=none, waiver artifact must exist"},
    72: {"name": "atomic_vs_lock_state", "description": "Lock file is valid (holder declared, lease not expired, base_revision consistent)"},
    73: {"name": "resolver_generation_match", "description": "Ticket's recorded resolver_generation matches current"},
    74: {"name": "cohort_organization_diversity", "description": "Proposal must have ≥3 distinct client_organization_id"},
    75: {"name": "effect_size_thresholds", "description": "Improvement exceeds thresholds (≥0.5 grade points, ≥30% revision reduction)"},
    76: {"name": "holdout_validation", "description": "Training-set proposal validated on holdout set"},
    77: {"name": "audience_context_field", "description": "Specificity contract has 7th field (audience_context) populated"},
    78: {"name": "regression_replay_contract_present", "description": "Each medium plugin declares regression_replay_contract"},
    79: {"name": "schema_validation_all_artifacts", "description": "Every JSON/YAML artifact validates against its schema"},
    80: {"name": "field_linked_revision_proof", "description": "Reviewer redlines drive field-linked revision with diff proof"},
    81: {"name": "brief_specificity_adequacy", "description": "Brief scores above thresholds on all 5 axes OR has clarifications appended"},
    82: {"name": "brief_contract_collusion_absence", "description": "Brief and VS specificity scores not jointly thin (>2σ below median)"},
    83: {"name": "operator_waiver_rate_within_bounds", "description": "Operator's waiver rate in 30d/90d windows within bounds"},
    84: {"name": "unsupported_medium_approval_rate", "description": "Operator's unsupported-medium approval rate within bounds"},
    85: {"name": "lock_backend_declared", "description": "vault/config/lock-backend.json exists; probe_passed: true"},
    86: {"name": "clock_skew_bounds", "description": "Multi-host: NTP synced and skew <5s"},
    87: {"name": "profile_dispatch_valid", "description": "Gate run includes valid --profile argument"},
    88: {"name": "runtime_budget_within_bounds", "description": "Gate run completed within max_runtime_s for its profile"},
    89: {"name": "producer_state_valid_for_invocation", "description": "Artifact producers are active or repaired_active at gate-run time"},
    90: {"name": "slot_integration_check_passed", "description": "Every manifest item with a slot contract passed slot integration"},
    91: {"name": "coherence_quantitative_set_checks_passed", "description": "All 8 cross-artifact coherence quantitative checks pass"},
    92: {"name": "coherence_reviewer_signoff_cites_every_check", "description": "Coherence signoff contains every quantitative check and reviewer assessment"},
    93: {"name": "centroid_version_current", "description": "Artifact centroid versions are not older than VS lock-time versions"},
    94: {"name": "custom_cohort_tracked_in_telemetry", "description": "Custom-mode VS has a cohort ID and appears in custom cohort membership"},
    95: {"name": "slot_integration_remediation_completed", "description": "Slot integration failures completed remediation or operator-decision flow"},
    96: {"name": "coherence_thresholds_applied_per_medium_preset", "description": "Coherence signoff records the active threshold version and resolved overrides"},
    97: {"name": "custom_cohort_cluster_id_assigned", "description": "Custom cohort cluster ID is a UUID and matches membership JSON"},
    98: {"name": "subject_present_at_required_locations",
         "description": "When subject_presence_contract is required, locked mockups for required_locations must contain the subject in at least one allowed_modalities form"},
}


def get_profile(name: str) -> dict[str, Any]:
    """Return profile config by name, or raise ``KeyError``."""
    if name not in PROFILES:
        raise KeyError(f"Unknown profile: {name}. Available: {sorted(PROFILES)}")
    return PROFILES[name]


def get_check(check_id: int) -> dict[str, str]:
    """Return check definition by id."""
    return CHECK_DEFINITIONS.get(check_id, {"name": f"check_{check_id}", "description": "(undefined)"})


def get_cache_categories(profile_name: str) -> tuple[str, ...]:
    """Return enabled cache categories for a profile."""
    profile = get_profile(profile_name)
    strategy = str(profile.get("cache_strategy") or "none")
    return PROFILE_CACHE_CATEGORIES.get(strategy, ())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", help="Optional profile name to inspect.")
    parser.add_argument("--pretty", action="store_true", help="Emit indented JSON.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.profile:
        profile = get_profile(args.profile)
        payload: dict[str, Any] = {
            "profile": args.profile,
            "config": profile,
            "cache_categories": list(get_cache_categories(args.profile)),
            "checks": [get_check(check_id) | {"id": check_id} for check_id in profile["checks"]],
        }
    else:
        payload = {
            "profiles": list(PROFILES.keys()),
            "n_checks": len(CHECK_DEFINITIONS),
            "cache_strategies": {name: list(values) for name, values in PROFILE_CACHE_CATEGORIES.items()},
        }
    text = json.dumps(payload, indent=2 if args.pretty or not args.profile else 2, sort_keys=True)
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
