from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import jsonschema
import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
CHECKER_PATH = REPO_ROOT / "scripts" / "check_tool_survey.py"
ACQUIRE_PATH = REPO_ROOT / "scripts" / "acquire_tool.py"
MCP_PATH = REPO_ROOT / "vault" / "clients" / "_platform" / "mcps" / "tool-discovery" / "server.py"
FIXTURE_ROOT = REPO_ROOT / "tests" / "fixtures" / "tool-survey"
RENDER_FIXTURE_REQUEST = (
    "Build a cinematic volumetric rendering workflow. The requested baseline names "
    "Mantaflow, and the fallback under consideration is an MP4-on-card hybrid."
)


STAGE1_FIXTURES = [
    "01-operator-wrong-tool-zero-spend",
    "02-paid-tool-out-of-band",
    "03-api-key-forbidden",
    "04-installed-overlay",
    "05-unsupported-os",
    "06-malicious-catalog",
    "07-stale-refresh",
    "08-operator-curated-precedence",
    "09-unresolved-oai-plan",
    "10-disposition-reject",
    "11-forward-watch-touching",
    "12-forward-watch-judging",
    "13-canary-blocks-ticket",
]

STAGE2_FIXTURES = [
    "14-same-stack-rejects-oai-tool",
    "15-tool-ceiling-first-reject",
    "16-three-same-stack-revises",
    "17-missing-root-cause-rejected",
    "18-ad-missing-tool-stack-refs",
    "19-tc-ratchet-plus-tool-fit-retro",
    "20-tool-replan-revised-ad",
    "21-different-stack-rejects-no-retro",
    "22-high-rigor-thresholds",
]

STAGE3_FIXTURES = [
    "23-malicious-acquisition-manifest",
    "24-checksum-mismatch-rollback",
    "25-mid-acquisition-failure-release",
    "26-direct-mcp-registry-mutation-refused",
    "27-reservation-capture-idempotency",
    "28-already-installed-idempotent",
    "29-os-unsupported-fails-fast",
    "30-secrets-in-oai-rejected",
    "31-dry-run-no-mutation",
    "32-spending-mcp-approved-flow",
    "33-operator-declines-manifest",
]

EXPECTED_FIXTURES = STAGE1_FIXTURES + STAGE2_FIXTURES + STAGE3_FIXTURES


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def load_markdown_yaml(path: Path, key: str) -> dict:
    text = path.read_text(encoding="utf-8")
    block = text.split("```yaml", 1)[1].split("```", 1)[0]
    data = yaml.safe_load(block)
    return data[key]


def load_optional_markdown_yaml(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    if "```yaml" not in text:
        return {}
    block = text.split("```yaml", 1)[1].split("```", 1)[0]
    data = yaml.safe_load(block) or {}
    return data if isinstance(data, dict) else {}


def constraints() -> dict:
    return {
        "os": ["macos"],
        "arch": ["arm64"],
        "hardware": {"gpu_class": ["apple-silicon-m-series"], "ram_floor_gb": 16, "disk_floor_gb": 20},
        "browser_runtime": {
            "webgl": "required",
            "webgpu": "preferred",
            "target_browsers": ["safari-17+", "chrome-120+"],
        },
        "host_availability": {"hosts": ["primary-laptop"]},
        "budget": {
            "max_total_usd": 0,
            "max_recurring_usd_per_month": 0,
            "operator_will_pay_out_of_band": False,
        },
        "local_runnable": "required",
        "network": {"outbound": "forbidden", "api_dependencies_allowed": False},
        "license_constraint": "open_source_only",
        "deliverable": {"type": "live_runtime", "performance_target": "60fps on M-series MacBook Pro"},
        "credentials": {"out_of_band_secrets_allowed": True, "api_keys_allowed": False},
        "canary_type": "functional",
        "evidence_threshold": "medium",
        "install_risk_threshold": "medium",
    }


def build_oai(meta: dict) -> dict:
    alternatives = []
    for idx, slug in enumerate(meta.get("alternatives") or ["fixture-tool"]):
        label = chr(ord("a") + idx)
        alternatives.append(
            {
                "label": label,
                "tool_slug": slug,
                "tool_stack_id": f"fixture:{slug}@1",
                "display_name": slug.replace("-", " ").title(),
                "bar_fitness": "HIGH" if "high" in slug or label == "a" else "MEDIUM",
                "constraint_fit": {"budget": "pass", "local_runnable": "pass", "credentials": "pass"},
                "excluded_by_constraint": [],
                "acquisition": {
                    "install_method": "vendor_installer" if meta.get("spend_approved") else "package_manager",
                    "cost_usd": meta.get("max_authorized_amount_usd", 0),
                    "recurrence": "annual" if meta.get("spend_approved") else "none",
                    "credentials_needed": ["LICENSE_KEY"] if meta.get("spend_approved") else [],
                    "license": "commercial_indie" if meta.get("spend_approved") else "mit",
                },
                "install_risk": "medium" if meta.get("spend_approved") else "low",
                "evidence_confidence": "high",
                "why_this_fits": "Fixture alternative for the synthetic tool survey.",
            }
        )
    spend = bool(meta.get("spend_approved"))
    canary_required = bool(meta.get("canary_required"))
    resolved = meta.get("decision_state") == "resolved"
    return {
        "oai_id": meta.get("oai_id", "OAI-PLAN-001"),
        "added": "2026-05-12T10:00",
        "planning_time": True,
        "capability": "fixture_capability",
        "bar": "Fixture bar.",
        "binding_constraints": constraints(),
        "tension": "Fixture tool-bar tension.",
        "alternatives": alternatives[:3],
        "recommended_default": {
            "label": meta.get("recommended_default", "a"),
            "reason": "Fixture recommended default.",
        },
        "operator_decision": {
            "decision": meta.get("decision"),
            "decision_state": meta.get("decision_state", "resolved"),
            "decision_reasoning": meta.get("decision_reasoning", "Fixture operator reasoning.") if resolved else None,
            "decision_authorization": {
                "authorization_id": "auth-fixture-001" if spend else None,
                "spend_approved": spend,
                "currency": "USD",
                "max_authorized_amount_usd": meta.get("max_authorized_amount_usd") if spend else None,
                "vendor": alternatives[0]["display_name"] if spend else None,
                "recurrence": "annual" if spend else None,
                "paid_via": meta.get("paid_via", "operator_out_of_band") if spend else "n_a",
                "approval_source": "fixture operator response" if spend else None,
                "expires_at": None,
                "valid_until_stage": "indefinite" if spend else "stage_1",
                "receipt_or_canary_required": True if spend else False,
                "receipt_or_canary_status": "pending" if spend else "n_a",
            },
            "ad_binding": "AD-001" if resolved else None,
            "tool_presence_canary": {
                "required": canary_required,
                "canary_target": alternatives[0]["tool_slug"] if canary_required else None,
                "blocked_tickets": meta.get("blocked_tickets", []) if canary_required else [],
                "canary_type": "functional" if canary_required else "not_required",
                "canary_status": meta.get("canary_status", "not_run") if canary_required else "not_required",
                "canary_evidence_pointer": None,
            },
            "decided_at": "2026-05-12T10:20" if resolved else None,
            "decided_by": "operator" if resolved else None,
        },
    }


def build_oai_tool(meta: dict) -> dict:
    alternatives = []
    for idx, slug in enumerate(meta.get("alternatives") or ["fixture-tool"]):
        label = chr(ord("a") + idx)
        alternatives.append(
            {
                "label": label,
                "tool_slug": slug,
                "tool_stack_id": meta.get("alternative_stack_ids", {}).get(slug, f"fixture:{slug}@1"),
                "display_name": slug.replace("-", " ").title(),
                "bar_fitness": "HIGH" if label == meta.get("recommended_default", "a") else "MEDIUM",
                "constraint_fit": {"budget": "pass", "local_runnable": "pass", "credentials": "pass"},
                "excluded_by_constraint": [],
                "acquisition": {
                    "install_method": "package_manager",
                    "cost_usd": 0,
                    "recurrence": "none",
                    "credentials_needed": [],
                    "license": "mit",
                },
                "install_risk": "low",
                "evidence_confidence": "high",
                "why_this_fits": "Catalog-backed fixture alternative for execution-time tool replan.",
            }
        )
    canary_required = bool(meta.get("canary_required"))
    resolved = meta.get("decision_state", "resolved") == "resolved"
    return {
        "oai_id": meta.get("oai_id", "OAI-TOOL-001"),
        "added": "2026-05-12T11:00",
        "execution_time": True,
        "capability": meta.get("capability", "fixture_capability"),
        "trigger": meta.get("trigger", "same_stack_rejects"),
        "current_tool_stack_id": meta.get("current_tool_stack_id", "fixture:current@1"),
        "current_tool_slug": meta.get("current_tool_slug", "fixture-tool"),
        "prior_ad_binding": meta.get("prior_ad_binding", "AD-001"),
        "affected_tickets": meta.get("affected_tickets", ["T-052"]),
        "updated_constraints": constraints(),
        "retrospective_summary": meta.get(
            "retrospective_summary",
            "Fixture Tool-Fit Retrospective found current stack insufficient.",
        ),
        "alternatives": alternatives[:3],
        "recommended_default": {
            "label": meta.get("recommended_default", "a"),
            "reason": meta.get("recommended_reason", "Fixture recommended default."),
        },
        "operator_decision": {
            "decision": meta.get("decision", "chose_a") if resolved else None,
            "decision_state": meta.get("decision_state", "resolved"),
            "decision_reasoning": meta.get("decision_reasoning", "Fixture operator chose a tool replan.")
            if resolved
            else None,
            "decision_authorization": {
                "authorization_id": None,
                "spend_approved": False,
                "currency": "USD",
                "max_authorized_amount_usd": None,
                "vendor": None,
                "recurrence": None,
                "paid_via": "n_a",
                "approval_source": None,
                "expires_at": None,
                "valid_until_stage": "stage_2",
                "receipt_or_canary_required": False,
                "receipt_or_canary_status": "n_a",
            },
            "ad_binding": meta.get("ad_binding", "AD-002") if resolved else None,
            "tool_presence_canary": {
                "required": canary_required,
                "canary_target": alternatives[0]["tool_slug"] if canary_required else None,
                "blocked_tickets": meta.get("blocked_tickets", []) if canary_required else [],
                "canary_type": "functional" if canary_required else "not_required",
                "canary_status": meta.get("canary_status", "not_run") if canary_required else "not_required",
                "canary_evidence_pointer": None,
            },
            "decided_at": "2026-05-12T11:20" if resolved else None,
            "decided_by": "operator" if resolved else None,
        },
    }


def build_survey(snapshot_meta: dict, oai: dict) -> dict:
    evidence_confidence = snapshot_meta.get("evidence_confidence", "high")
    ttl_status = "stale" if evidence_confidence == "stale_accepted" else "fresh"
    installed_state = snapshot_meta.get("installed_state", "unknown")
    canary_status = snapshot_meta.get("canary_status", "not_run")
    return {
        "project_slug": snapshot_meta["project_slug"],
        "client_slug": "example",
        "generated_at": "2026-05-12T10:00",
        "load_bearing_capabilities": [
            {
                "id": snapshot_meta["capability"],
                "bar": "Fixture bar.",
                "operator_named_tool": snapshot_meta.get("candidate_tool"),
            }
        ],
        "constraints": constraints(),
        "surveys": [
            {
                "capability": snapshot_meta["capability"],
                "bar": "Fixture bar.",
                "constraints": constraints(),
                "refresh_required": bool(snapshot_meta.get("refresh_required", False)),
                "candidates": [
                    {
                        "tool_slug": snapshot_meta.get("candidate_tool", "fixture-tool"),
                        "tool_stack_id": snapshot_meta.get("tool_stack_id", "fixture:tool@1"),
                        "display_name": "Fixture Tool",
                        "bar_fitness": "HIGH",
                        "bar_fitness_evidence": [
                            {"type": "fixture", "source": "fixture", "summary": "Fixture evidence."}
                        ],
                        "constraint_fit": {"budget": "pass", "local_runnable": "pass"},
                        "excluded_by_constraint": snapshot_meta.get("excluded_by_constraint", []),
                        "installed_state": {
                            "state": installed_state,
                            "detected_version": "1.0" if installed_state == "installed" else None,
                            "canary_status": canary_status,
                            "last_seen_on_host": "primary-laptop" if installed_state == "installed" else None,
                        },
                        "acquisition_summary": {
                            "install_method": "package_manager",
                            "install_risk": "low",
                            "acquisition_cost_usd": 0,
                            "recurrence": "none",
                        },
                        "canary_type": "functional",
                        "evidence_confidence": evidence_confidence,
                        "catalog_freshness": {
                            "terms_last_checked": "2025-01-01" if ttl_status == "stale" else "2026-05-12",
                            "ttl_status": ttl_status,
                            "citation_urls": ["https://example.test/fixture"],
                        },
                    }
                ],
                "tension": "Fixture tension.",
                "recommended_default": str(snapshot_meta.get("recommendation", "a")),
            }
        ],
        "oai_plan_responses": [oai],
        "warnings": [],
    }


def write_markdown_yaml(path: Path, key: str, data: dict) -> None:
    path.write_text(f"```yaml\n{yaml.safe_dump({key: data}, sort_keys=False)}```\n", encoding="utf-8")


def write_ticket(path: Path, frontmatter: dict) -> None:
    path.write_text(f"---\n{yaml.safe_dump(frontmatter, sort_keys=False)}---\n# Fixture ticket\n", encoding="utf-8")


def build_stage3_manifest(meta: dict) -> dict:
    manifest_id = meta.get("manifest_id", "00000000-0000-4000-8000-000000000032")
    status = meta.get("operator_approval_status", "approved")
    signature = None
    if status in {"approved", "declined"}:
        signature = {
            "operator_id": "operator",
            "signed_at": "2026-05-12T10:30",
            "approval_source": "fixture",
        }
    install_kind = meta.get("install_kind", "pip_install")
    binary = None
    if install_kind == "binary_download":
        binary = {
            "version": meta.get("binary_version", "1.2.3"),
            "source_url": "https://example.test/fixture.tar.gz",
            "sha256": "a" * 64,
            "signature_url": None,
            "tls_provenance_check": "required",
            "expected_hostname": "example.test",
        }
    manifest = {
        "manifest_id": manifest_id,
        "created_at": "2026-05-12T10:00",
        "created_by": "codex",
        "acquisition_target": {
            "tool_slug": "fixture-tool",
            "tool_stack_id": "fixture:tool@1",
            "project_slug": "stage3-fixture",
            "client_slug": "example",
            "version": "1.2.3",
        },
        "catalog_entry_ref": "fixture-tool",
        "install_scope": meta.get("install_scope", "project_local"),
        "planned_steps": [
            {
                "step_id": "preflight",
                "kind": "preflight",
                "description": "Validate acquisition policy.",
                "mutation": "none",
                "command": meta.get("preflight_command"),
                "package": None,
                "version": None,
                "binary": None,
                "files_to_touch": [],
                "global_install": False,
                "global_install_approval": None,
                "requires_secret_env_vars": [],
                "operator_action_prompt": None,
                "mcp_registration_proposal_path": None,
            },
            {
                "step_id": "install",
                "kind": install_kind,
                "description": "Install fixture tool locally.",
                "mutation": "filesystem",
                "command": None,
                "package": "fixture-package",
                "version": "1.2.3",
                "binary": binary,
                "files_to_touch": meta.get("step_files_to_touch", ["vault/clients/example/tools/stage3-fixture/fixture-tool"]),
                "global_install": bool(meta.get("global_install", False)),
                "global_install_approval": meta.get("global_install_approval"),
                "requires_secret_env_vars": [],
                "operator_action_prompt": meta.get("operator_action_prompt"),
                "mcp_registration_proposal_path": None,
            },
            {
                "step_id": "canary",
                "kind": "canary",
                "description": "Run functional canary.",
                "mutation": "filesystem",
                "command": None,
                "package": None,
                "version": None,
                "binary": None,
                "files_to_touch": ["vault/clients/example/snapshots/stage3-fixture/tool-acquisition/evidence.json"],
                "global_install": False,
                "global_install_approval": None,
                "requires_secret_env_vars": [],
                "operator_action_prompt": None,
                "mcp_registration_proposal_path": None,
            },
        ],
        "files_to_touch": meta.get("files_to_touch", ["vault/clients/example/tools/stage3-fixture/fixture-tool"]),
        "spend_reservation": {
            "mode": meta.get("spend_mode", "spending_mcp"),
            "project_slug": "stage3-fixture",
            "vendor": "Fixture Vendor",
            "amount_usd": 269,
            "max_authorized_amount_usd": 269,
            "recurrence": "annual",
            "category": "tool_acquisition",
            "authorization_id": "auth-fixture-001",
            "quote_id": meta.get("quote_id"),
            "reservation_id": meta.get("reservation_id"),
            "receipt_ref": meta.get("receipt_ref"),
        },
        "operator_approval_status": status,
        "operator_approval_signature": signature,
        "rollback_plan": [
            {"action": "release_reservation", "target": "spend_reservation", "condition": "no capture happened"},
            {"action": "remove_path", "target": "vault/clients/example/tools/stage3-fixture/fixture-tool", "condition": "installed by transaction"},
        ],
        "registration_proposal": {
            "required": bool(meta.get("registration_required", False)),
            "proposal_path": "vault/clients/_platform/mcps/fixture-tool/registration-proposal.yaml"
            if meta.get("registration_required", False)
            else None,
            "server_name": "fixture-tool" if meta.get("registration_required", False) else None,
            "server_path": "/tmp/fixture/server.py" if meta.get("registration_required", False) else None,
            "env_vars": {},
        },
        "preflight_checks": ["schema", "secrets", "install_scope", "mcp_registry_isolation", "os_support"],
        "dry_run_default": True,
        "execution": meta.get("execution", {"state": "planned"}),
    }
    return manifest


def test_fixture_file_shape():
    for fixture_name in EXPECTED_FIXTURES:
        fixture = FIXTURE_ROOT / fixture_name
        assert (fixture / "plan.md").is_file()
        assert (fixture / "catalog").is_dir()
        assert any((fixture / "catalog").iterdir())
        assert (fixture / "expected_snapshot_output.md").is_file()
        if fixture_name in STAGE1_FIXTURES:
            assert (fixture / "expected_oai_plan_output.md").is_file()
        if fixture_name in STAGE2_FIXTURES and not fixture_name.startswith(("17-", "18-", "21-")):
            assert (fixture / "expected_oai_tool_output.md").is_file()
        if fixture_name[:2] in {"10", "11", "12", "13"} or fixture_name in STAGE2_FIXTURES:
            assert (fixture / "checkpoint_output.md").is_file()
        if fixture_name in STAGE3_FIXTURES:
            assert (fixture / "expected_manifest_output.md").is_file()
            assert (fixture / "expected_oai_spend_output.md").is_file()
            assert (fixture / "expected_rollback_log.md").is_file()
            assert (fixture / "expected_spending_log_delta.md").is_file()


@pytest.mark.parametrize("fixture_name", EXPECTED_FIXTURES)
def test_synthetic_fixture_runner(fixture_name, tmp_path):
    checker = load_module(CHECKER_PATH, "check_tool_survey_under_test")
    fixture = FIXTURE_ROOT / fixture_name
    snapshot_meta = load_markdown_yaml(fixture / "expected_snapshot_output.md", "snapshot")
    if (fixture / "expected_oai_plan_output.md").is_file():
        oai_meta = load_markdown_yaml(fixture / "expected_oai_plan_output.md", "oai_fixture")
    else:
        oai_meta = {
            "oai_id": "OAI-PLAN-001",
            "decision_state": "resolved",
            "decision": "brief_amendment",
            "recommended_default": "a",
            "spend_approved": False,
            "canary_required": False,
            "alternatives": ["fixture-tool"],
        }
    oai = build_oai(oai_meta)
    survey = build_survey(snapshot_meta, oai)
    survey_path = tmp_path / f"{fixture_name}-survey.md"
    write_markdown_yaml(survey_path, "tool_survey", survey)
    plan_text = (fixture / "plan.md").read_text(encoding="utf-8").replace(
        "expected_snapshot_output.md", str(survey_path)
    )
    plan_path = tmp_path / f"{fixture_name}-plan.md"
    plan_path.write_text(plan_text, encoding="utf-8")

    checkpoint_paths = sorted(fixture.glob("checkpoint_output*.md"))
    runtime_check_paths = sorted(fixture.glob("runtime_check*.md"))
    ticket_paths = []
    if (fixture / "ticket_frontmatter.md").is_file():
        ticket_paths.append(fixture / "ticket_frontmatter.md")
    if snapshot_meta.get("ticket_frontmatter"):
        ticket_path = tmp_path / f"{fixture_name}-ticket.md"
        write_ticket(ticket_path, snapshot_meta["ticket_frontmatter"])
        ticket_paths.append(ticket_path)
    oai_tool_paths = []
    if (fixture / "expected_oai_tool_output.md").is_file():
        oai_tool_meta = load_markdown_yaml(fixture / "expected_oai_tool_output.md", "oai_tool_fixture")
        oai_tool = build_oai_tool(oai_tool_meta)
        oai_tool_path = tmp_path / f"{fixture_name}-oai-tool.md"
        write_markdown_yaml(oai_tool_path, "oai_tool", oai_tool)
        oai_tool_paths.append(oai_tool_path)
    oai_spend_paths = []
    acquisition_manifest_paths = []
    spending_record_paths = []
    if fixture_name in STAGE3_FIXTURES:
        manifest_data = load_optional_markdown_yaml(fixture / "expected_manifest_output.md")
        if manifest_data.get("manifest_fixture") is not None:
            manifest = build_stage3_manifest(manifest_data["manifest_fixture"])
            manifest_path = tmp_path / f"{fixture_name}-manifest.md"
            write_markdown_yaml(manifest_path, "acquisition_manifest", manifest)
            acquisition_manifest_paths.append(manifest_path)
        elif manifest_data.get("acquisition_manifest") is not None:
            manifest_path = tmp_path / f"{fixture_name}-manifest.md"
            write_markdown_yaml(manifest_path, "acquisition_manifest", manifest_data["acquisition_manifest"])
            acquisition_manifest_paths.append(manifest_path)
        oai_spend_data = load_optional_markdown_yaml(fixture / "expected_oai_spend_output.md")
        if oai_spend_data.get("oai_spend") is not None:
            oai_spend_path = tmp_path / f"{fixture_name}-oai-spend.md"
            write_markdown_yaml(oai_spend_path, "oai_spend", oai_spend_data["oai_spend"])
            oai_spend_paths.append(oai_spend_path)
        spending_data = load_optional_markdown_yaml(fixture / "expected_spending_log_delta.md")
        if spending_data.get("spending_record") is not None:
            spending_path = tmp_path / f"{fixture_name}-spending-record.md"
            write_markdown_yaml(spending_path, "spending_record", spending_data["spending_record"])
            spending_record_paths.append(spending_path)
    attempted_ticket = "T-010" if fixture_name.startswith("13-") else None
    report = checker.validate_tool_survey(
        plan_path=plan_path,
        survey_path=survey_path,
        checkpoint_paths=checkpoint_paths,
        oai_tool_paths=oai_tool_paths,
        oai_spend_paths=oai_spend_paths,
        acquisition_manifest_paths=acquisition_manifest_paths,
        spending_record_paths=spending_record_paths,
        ticket_paths=ticket_paths,
        runtime_check_paths=runtime_check_paths,
        attempted_ticket=attempted_ticket,
    )

    expected_ok = snapshot_meta.get("expected_ok")
    if expected_ok is None:
        expected_ok = not fixture_name.startswith(("09-", "12-", "13-"))
    assert report["ok"] is expected_ok, report
    if fixture_name.startswith("07-"):
        assert any("stale_accepted" in warning for warning in report["warnings"])
    if fixture_name.startswith("10-"):
        checkpoint = checker.load_checkpoint(fixture / "checkpoint_output.md")
        assert checkpoint["Decision"] == "REJECT"
        assert checkpoint["root_cause"] == "tool_ceiling"
        assert set(checkpoint["next_iteration_options"]) == {
            "same-stack-harder-with-explicit-composition-direction",
            "pivot-to-brief-secondary-path",
            "tool-replan-to-named-alternative",
        }
    if fixture_name.startswith("14-"):
        assert any(check["name"] == "tool_fit_retrospective_trigger" and check["ok"] for check in report["checks"])
    if fixture_name.startswith("21-"):
        assert any(
            check["name"] == "tool_fit_retrospective_trigger"
            and check["ok"]
            and "No same-stack" in check["details"]
            for check in report["checks"]
        )


def test_render_fixture_replay_surfaces_expected_oai_plan(monkeypatch, tmp_path):
    mcp = load_module(MCP_PATH, "tool_discovery_replay")
    checker = load_module(CHECKER_PATH, "check_tool_survey_replay")
    monkeypatch.setenv("TOOL_DISCOVERY_TODAY", "2026-05-12")
    request_text = RENDER_FIXTURE_REQUEST
    assert "Mantaflow" in request_text
    assert "MP4-on-card hybrid" in request_text

    survey = mcp.survey_tools_result(
        "cinematic_volumetric_render",
        "feature-quality volumetric material under local runtime constraints",
        constraints(),
        catalog_dir=str(REPO_ROOT / "vault" / "archive" / "tools-catalog"),
    )
    by_slug = {candidate["tool_slug"]: candidate for candidate in survey["candidates"]}
    assert "houdini-indie" in by_slug
    assert "mp4-video-texture-on-card" in by_slug
    assert "blender-mantaflow-gas" in by_slug

    oai = build_oai(
        {
            "oai_id": "OAI-PLAN-001",
            "decision_state": "open",
            "decision": None,
            "recommended_default": "c",
            "spend_approved": False,
            "canary_required": False,
            "alternatives": [
                "blender-mantaflow-gas",
                "houdini-indie",
                "mp4-video-texture-on-card",
            ],
        }
    )
    oai["capability"] = "cinematic_volumetric_render"
    oai["bar"] = "feature-quality volumetric material under local runtime constraints"
    oai["alternatives"][0]["bar_fitness"] = by_slug["blender-mantaflow-gas"]["bar_fitness"]
    oai["alternatives"][1]["bar_fitness"] = by_slug["houdini-indie"]["bar_fitness"]
    oai["alternatives"][1]["excluded_by_constraint"] = by_slug["houdini-indie"]["excluded_by_constraint"]
    oai["alternatives"][2]["display_name"] = by_slug["mp4-video-texture-on-card"]["display_name"]
    oai["alternatives"][2]["bar_fitness"] = by_slug["mp4-video-texture-on-card"]["bar_fitness"]
    oai["recommended_default"]["reason"] = "Cycles-bake hybrid clears the bar inside zero-spend local constraints."

    jsonschema.Draft7Validator(checker.OAI_PLAN_SCHEMA).validate(oai)
    assert oai["oai_id"] == "OAI-PLAN-001"
    assert "budget" in oai["alternatives"][1]["excluded_by_constraint"]
    assert "Cycles-bake" in oai["alternatives"][2]["display_name"]
    assert oai["recommended_default"]["label"] == "c"

    reject_checkpoint = checker.load_checkpoint(
        FIXTURE_ROOT / "10-disposition-reject" / "checkpoint_output.md"
    )
    assert reject_checkpoint["Decision"] == "REJECT"
    assert reject_checkpoint["tool_stack_bottleneck"]["tool"] == "blender-mantaflow-gas"

    oai_tool = build_oai_tool(
        {
            "oai_id": "OAI-TOOL-001",
            "trigger": "tool_ceiling_high_confidence",
            "capability": "cinematic_volumetric_render",
            "current_tool_stack_id": "blender:mantaflow-gas@4.5",
            "current_tool_slug": "blender-mantaflow-gas",
            "prior_ad_binding": "AD-001",
            "ad_binding": "AD-002",
            "affected_tickets": ["T-052"],
            "alternatives": ["houdini-indie", "mp4-video-texture-on-card"],
            "alternative_stack_ids": {
                "houdini-indie": by_slug["houdini-indie"]["tool_stack_id"],
                "mp4-video-texture-on-card": by_slug["mp4-video-texture-on-card"]["tool_stack_id"],
            },
            "recommended_default": "b",
            "recommended_reason": "Cycles-bake hybrid clears the bar inside zero-spend local constraints.",
            "decision": "chose_b",
        }
    )
    oai_tool["alternatives"][0]["display_name"] = by_slug["houdini-indie"]["display_name"]
    oai_tool["alternatives"][0]["excluded_by_constraint"] = by_slug["houdini-indie"]["excluded_by_constraint"]
    oai_tool["alternatives"][1]["display_name"] = by_slug["mp4-video-texture-on-card"]["display_name"]
    oai_tool["alternatives"][1]["bar_fitness"] = by_slug["mp4-video-texture-on-card"]["bar_fitness"]

    jsonschema.Draft7Validator(checker.OAI_TOOL_SCHEMA).validate(oai_tool)
    assert oai_tool["oai_id"] == "OAI-TOOL-001"
    assert oai_tool["operator_decision"]["ad_binding"] == "AD-002"
    assert "budget" in oai_tool["alternatives"][0]["excluded_by_constraint"]
    assert "Cycles-bake" in oai_tool["alternatives"][1]["display_name"]

    plan_path = tmp_path / "render-fixture-plan.md"
    plan_path.write_text(
        """tool_fit_rigor_tier: default
tool_survey_snapshot: render-fixture-survey.md

## Load-Bearing Capabilities
| Capability | Bar |
|---|---|
| `cinematic_volumetric_render` | feature-quality volumetric material under local runtime constraints |

## Architecture Decisions
| ID | Decision | Binding |
|---|---|---|
| AD-001 | Original Mantaflow + Cycles stack | tool_slug: blender-mantaflow-gas; tool_stack_refs: [blender:mantaflow-gas@4.5, blender:cycles@4.5] |
| AD-002 | Revised Cycles-bake hybrid after OAI-TOOL-001 approval | tool_slug: mp4-video-texture-on-card; tool_stack_refs: [hybrid:cycles-bake-vdb-mp4-card@stage1] |
""",
        encoding="utf-8",
    )
    render_fixture_survey = build_survey(
        {
            "project_slug": "render-fixture-007",
            "capability": "cinematic_volumetric_render",
            "candidate_tool": "blender-mantaflow-gas",
            "tool_stack_id": "blender:mantaflow-gas@4.5",
        },
        build_oai(
            {
                "oai_id": "OAI-PLAN-001",
                "decision_state": "resolved",
                "decision": "brief_amendment",
                "recommended_default": "a",
                "spend_approved": False,
                "canary_required": False,
                "alternatives": ["blender-mantaflow-gas"],
            }
        ),
    )
    survey_path = tmp_path / "render-fixture-survey.md"
    write_markdown_yaml(survey_path, "tool_survey", render_fixture_survey)
    checkpoint_path = tmp_path / "render-fixture-checkpoint.md"
    write_markdown_yaml(
        checkpoint_path,
        "checkpoint",
        {
            "ticket_id": "T-052",
            "Tier selected": "T3",
            "Decision": "REJECT",
            "root_cause": "tool_ceiling",
            "root_cause_confidence": "high",
            "tool_stack_refs": ["blender:mantaflow-gas@4.5", "blender:cycles@4.5"],
            "Reasoning": "Mantaflow plus Cycles hit the visual ceiling on Wave D round 1.",
        },
    )
    oai_tool_path = tmp_path / "render-fixture-oai-tool.md"
    write_markdown_yaml(oai_tool_path, "oai_tool", oai_tool)

    report = checker.validate_tool_survey(
        plan_path=plan_path,
        survey_path=survey_path,
        checkpoint_paths=[checkpoint_path],
        oai_tool_paths=[oai_tool_path],
    )
    assert report["ok"] is True, report
    assert any(check["name"] == "OAI-TOOL-001_ad_binding_exists" and check["ok"] for check in report["checks"])


class Stage3MockAdapter:
    def __init__(self):
        self.calls = []

    def is_installed(self, manifest):
        self.calls.append(("is_installed", manifest["acquisition_target"]["tool_slug"]))
        return False

    def execute_step(self, step, manifest):
        self.calls.append(("execute_step", step["kind"]))
        return {"ok": True, "step": step["kind"]}

    def rollback_step(self, action, manifest):
        self.calls.append(("rollback", action["action"]))
        return {"ok": True}


class Stage3MockSpending:
    def __init__(self):
        self.calls = []

    def quote_spend(self, **kwargs):
        self.calls.append(("quote", kwargs))
        return {"status": "OK", "quote_id": "quote-houdini", "projected_balance": {}}

    def reserve_spend(self, **kwargs):
        self.calls.append(("reserve", kwargs))
        return {"status": "OK", "reservation": {"reservation_id": "res-houdini", "authorization_id": kwargs["authorization_id"]}}

    def capture_spend(self, **kwargs):
        self.calls.append(("capture", kwargs))
        return {"status": "OK", "capture": {"reservation_id": kwargs["reservation_id"], "receipt_ref": kwargs["receipt_ref"]}}

    def release_reservation(self, **kwargs):
        self.calls.append(("release", kwargs))
        return {"status": "OK", "release": {"reservation_id": kwargs["reservation_id"]}}


def stage3_ok_canary(entry, *, install_root, evidence_dir):
    evidence_dir.mkdir(parents=True, exist_ok=True)
    evidence = evidence_dir / "houdini-canary.json"
    evidence.write_text(json.dumps({"ok": True, "exported": "minimal.vdb"}), encoding="utf-8")
    return {"ok": True, "evidence_pointer": str(evidence)}


def stage3_waiting_canary(entry, *, install_root, evidence_dir):
    evidence_dir.mkdir(parents=True, exist_ok=True)
    return {"ok": False, "error": "hython not present", "evidence_pointer": str(evidence_dir / "missing.json")}


def test_render_fixture_stage3_replay_spending_mcp_and_out_of_band(monkeypatch, tmp_path):
    mcp = load_module(MCP_PATH, "tool_discovery_stage3_replay")
    acquire = load_module(ACQUIRE_PATH, "acquire_tool_stage3_replay")
    monkeypatch.setenv("TOOL_DISCOVERY_TODAY", "2026-05-12")
    catalog = mcp.load_catalog(catalog_dir=str(REPO_ROOT / "vault" / "archive" / "tools-catalog"))
    houdini = json.loads(json.dumps(catalog["houdini-indie"]))
    houdini["versions"] = [{"version": "20.5.410", "released": "2026-01-01"}]
    houdini["acquisition"]["canary_steps"] = [
        {
            "type": "command",
            "name": "export minimal vdb",
            "command": [sys.executable, "-c", "open('minimal.vdb','w').write('vdb')"],
        },
        {"type": "assert_path_exists", "path": "minimal.vdb"},
    ]
    houdini["mcp_registration"] = {
        "server_name": "houdini-indie",
        "server_path": "/opt/sidefx/houdini/server.py",
        "env_vars": {"HOUDINI_LICENSE": "operator-provided keychain entry"},
    }
    spending_auth = {
        "authorization_id": "auth-houdini-269",
        "spend_approved": True,
        "currency": "USD",
        "max_authorized_amount_usd": 269,
        "vendor": "Houdini Indie",
        "recurrence": "annual",
        "paid_via": "spending_mcp",
        "approval_source": "operator approved Houdini Indie path",
    }
    (tmp_path / ".mcp.json").write_text(
        json.dumps({"mcpServers": {"spending": {"args": ["vault/clients/_platform/mcps/spending/server.py"]}}}),
        encoding="utf-8",
    )
    manifest = acquire.build_manifest(
        houdini,
        project_slug="render-fixture-007",
        authorization=spending_auth,
        repo_root=tmp_path,
        vault_root=tmp_path / "vault",
    )
    assert manifest["spend_reservation"]["mode"] == "spending_mcp"
    approved = acquire.approve_manifest(manifest, operator_id="operator", approval_source="fixture")

    dry_run = acquire.execute_manifest(
        approved,
        catalog_entry=houdini,
        adapter=Stage3MockAdapter(),
        spending=Stage3MockSpending(),
        execute=False,
        repo_root=tmp_path,
        vault_root=tmp_path / "vault",
    )
    assert dry_run["status"] == "dry_run"

    spending = Stage3MockSpending()
    result = acquire.execute_manifest(
        approved,
        catalog_entry=houdini,
        adapter=Stage3MockAdapter(),
        spending=spending,
        canary_runner=stage3_ok_canary,
        execute=True,
        repo_root=tmp_path,
        vault_root=tmp_path / "vault",
    )
    assert result["ok"] is True, result
    assert [name for name, _ in spending.calls] == ["quote", "reserve", "capture"]
    assert spending.calls[1][1]["max_authorized_amount_usd"] == 269
    assert spending.calls[2][1]["actual_amount_usd"] == 269
    proposal = tmp_path / "vault" / "clients" / "_platform" / "mcps" / "houdini-indie" / "registration-proposal.yaml"
    assert proposal.is_file()

    out_of_band_auth = dict(spending_auth, paid_via="operator_out_of_band", authorization_id="auth-houdini-oob")
    oob_manifest = acquire.approve_manifest(
        acquire.build_manifest(
            houdini,
            project_slug="render-fixture-007",
            authorization=out_of_band_auth,
            repo_root=tmp_path / "no-spending-config",
            vault_root=tmp_path / "oob-vault",
        ),
        operator_id="operator",
        approval_source="fixture",
    )
    oob_spending = Stage3MockSpending()
    oob_result = acquire.execute_manifest(
        oob_manifest,
        catalog_entry=houdini,
        adapter=Stage3MockAdapter(),
        spending=oob_spending,
        canary_runner=stage3_waiting_canary,
        execute=True,
        repo_root=tmp_path / "no-spending-config",
        vault_root=tmp_path / "oob-vault",
    )
    assert oob_result["status"] == "tool_presence_canary_waiting"
    assert oob_spending.calls == []
