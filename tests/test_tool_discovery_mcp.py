from __future__ import annotations

import importlib.util
import os
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
SERVER_PATH = REPO_ROOT / "vault" / "clients" / "_platform" / "mcps" / "tool-discovery" / "server.py"


def load_module():
    spec = importlib.util.spec_from_file_location("tool_discovery_under_test", SERVER_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def base_entry(slug: str, *, fit: str = "MEDIUM", cost: int = 0, checked: str = "2026-05-12") -> dict:
    return {
        "tool_slug": slug,
        "tool_stack_id": f"test:{slug}@1",
        "display_name": slug.replace("-", " ").title(),
        "versions": [{"version": "1.0", "released": "2026-01-01"}],
        "capabilities": [
            {
                "id": "cinematic_volumetric_render",
                "bar_fit_default": fit,
                "bar_fit_evidence": [
                    {"type": "test", "source": "fixture", "summary": f"{slug} evidence"}
                ],
                "known_ceilings": ["fixture ceiling"],
            }
        ],
        "constraints": {
            "os": ["macos", "linux"],
            "arch": ["arm64", "x86_64"],
            "acquisition_cost_usd": cost,
            "recurrence": "none" if cost == 0 else "annual",
            "license": "mit" if cost == 0 else "commercial_indie",
            "local_runnable": True,
            "network_required": False,
            "credentials_required": cost > 0,
        },
        "acquisition": {
            "install_method": "package_manager" if cost == 0 else "vendor_installer",
            "install_risk": "low" if cost == 0 else "medium",
            "install_steps_summary": "Install from the documented package source and run a canary.",
            "canary_type": "functional",
            "credentials_needed": [] if cost == 0 else ["LICENSE_KEY"],
            "credential_handoff": "none" if cost == 0 else "operator_out_of_band",
        },
        "catalog_metadata": {
            "source": "canonical",
            "terms_last_checked": checked,
            "ttl_days_by_domain": {"pricing": 90, "licensing": 180, "capability_evidence": 365},
            "citation_urls": ["https://example.test/tool"],
            "catalog_revision": 1,
            "last_validated": "2026-05-12",
        },
    }


def write_catalog(path: Path, *entries: dict) -> None:
    path.mkdir(parents=True, exist_ok=True)
    for entry in entries:
        (path / f"{entry['tool_slug']}.yaml").write_text(
            yaml.safe_dump(entry, sort_keys=False),
            encoding="utf-8",
        )


def constraints() -> dict:
    return {
        "os": ["macos"],
        "arch": ["arm64"],
        "budget": {
            "max_total_usd": 0,
            "max_recurring_usd_per_month": 0,
            "operator_will_pay_out_of_band": False,
        },
        "local_runnable": "required",
        "network": {"outbound": "forbidden", "api_dependencies_allowed": False},
        "license_constraint": "open_source_only",
        "deliverable": {"type": "live_runtime", "performance_target": "60fps"},
        "credentials": {"out_of_band_secrets_allowed": False, "api_keys_allowed": False},
        "host_availability": {"hosts": ["primary-laptop"]},
    }


def test_survey_ordering_is_deterministic(tmp_path, monkeypatch):
    mod = load_module()
    monkeypatch.setenv("TOOL_DISCOVERY_TODAY", "2026-05-12")
    catalog = tmp_path / "catalog"
    write_catalog(
        catalog,
        base_entry("tool-medium", fit="MEDIUM"),
        base_entry("tool-high", fit="HIGH"),
        base_entry("tool-paid-high", fit="HIGH", cost=269),
    )

    first = mod.survey_tools_result(
        "cinematic_volumetric_render",
        "feature quality volume",
        constraints(),
        catalog_dir=str(catalog),
    )
    second = mod.survey_tools_result(
        "cinematic_volumetric_render",
        "feature quality volume",
        constraints(),
        catalog_dir=str(catalog),
    )

    assert [c["tool_slug"] for c in first["candidates"]] == [c["tool_slug"] for c in second["candidates"]]
    assert first["candidates"][0]["tool_slug"] == "tool-high"
    assert first["candidates"][-1]["tool_slug"] == "tool-paid-high"
    assert "budget" in first["candidates"][-1]["excluded_by_constraint"]


def test_schema_validation_rejects_malicious_install_summary(tmp_path):
    mod = load_module()
    catalog = tmp_path / "catalog"
    entry = base_entry("bad-tool")
    entry["acquisition"]["install_steps_summary"] = "Install tool; rm -rf vault"
    write_catalog(catalog, entry)

    with pytest.raises(ValueError, match="schema validation"):
        mod.load_catalog(catalog_dir=str(catalog))


def test_overlay_merge_precedence_and_installed_state(tmp_path, monkeypatch):
    mod = load_module()
    monkeypatch.setenv("TOOL_DISCOVERY_TODAY", "2026-05-12")
    catalog = tmp_path / "catalog"
    vault = tmp_path / "vault"
    write_catalog(catalog, base_entry("tool-medium", fit="MEDIUM"))
    overlay_dir = vault / "clients" / "acme" / "tools-catalog-overlay"
    overlay_dir.mkdir(parents=True)
    overlay = {
        "tool_slug": "tool-medium",
        "overlay_metadata": {
            "source": "operator-curated",
            "curator": "operator",
            "canonical_revision_base": 1,
            "conflict_reason": "operator confirms high-fitness local result",
            "review_after": "2026-08-12",
            "override_durability": "durable",
        },
        "installed_state_by_host": {
            "primary-laptop": {
                "state": "installed",
                "detected_version": "1.0",
                "canary_status": "passed",
                "canary_last_run": "2026-05-12T01:23",
                "last_seen_on_host": "primary-laptop",
            }
        },
        "capability_overrides": [
            {
                "id": "cinematic_volumetric_render",
                "bar_fit_default": "HIGH",
                "bar_fit_evidence": [
                    {"type": "operator", "source": "operator note", "summary": "local result cleared the bar"}
                ],
                "known_ceilings": ["none observed in local canary"],
                "override_reason": "operator has direct project evidence",
            }
        ],
    }
    (overlay_dir / "tool-medium.yaml").write_text(yaml.safe_dump(overlay, sort_keys=False), encoding="utf-8")

    result = mod.survey_tools_result(
        "cinematic_volumetric_render",
        "feature quality volume",
        constraints(),
        client_slug="acme",
        catalog_dir=str(catalog),
        vault_root=str(vault),
    )

    candidate = result["candidates"][0]
    assert candidate["bar_fitness"] == "HIGH"
    assert candidate["installed_state"]["state"] == "installed"
    assert candidate["installed_state"]["canary_status"] == "passed"


def test_overlay_missing_conflict_hygiene_is_rejected(tmp_path):
    mod = load_module()
    catalog = tmp_path / "catalog"
    vault = tmp_path / "vault"
    write_catalog(catalog, base_entry("tool-medium"))
    overlay_dir = vault / "clients" / "acme" / "tools-catalog-overlay"
    overlay_dir.mkdir(parents=True)
    (overlay_dir / "tool-medium.yaml").write_text(
        yaml.safe_dump({"tool_slug": "tool-medium", "capability_overrides": []}, sort_keys=False),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="schema validation"):
        mod.load_catalog(catalog_dir=str(catalog), client_slug="acme", vault_root=str(vault))


def test_freshness_flag_strict_and_best_effort(tmp_path, monkeypatch):
    mod = load_module()
    monkeypatch.setenv("TOOL_DISCOVERY_TODAY", "2026-05-12")
    catalog = tmp_path / "catalog"
    write_catalog(catalog, base_entry("stale-tool", fit="HIGH", checked="2025-01-01"))

    strict = mod.survey_tools_result(
        "cinematic_volumetric_render",
        "feature quality volume",
        constraints(),
        freshness_policy="strict",
        catalog_dir=str(catalog),
    )
    best_effort = mod.survey_tools_result(
        "cinematic_volumetric_render",
        "feature quality volume",
        constraints(),
        freshness_policy="best_effort",
        catalog_dir=str(catalog),
    )

    assert strict["refresh_required"] is True
    assert strict["candidates"][0]["catalog_freshness"]["ttl_status"] == "stale"
    assert best_effort["candidates"][0]["evidence_confidence"] == "stale_accepted"


def test_propose_refresh_does_not_write_catalog(tmp_path, monkeypatch):
    mod = load_module()
    monkeypatch.setenv("TOOL_DISCOVERY_TODAY", "2026-05-12")
    catalog = tmp_path / "catalog"
    entry = base_entry("tool-high", fit="HIGH", checked="2025-01-01")
    write_catalog(catalog, entry)
    path = catalog / "tool-high.yaml"
    before = path.read_text(encoding="utf-8")

    proposal = mod.propose_refresh_result(
        "tool-high",
        ["https://example.test/fresh"],
        "operator supplied fresh citation",
        catalog_dir=str(catalog),
    )

    assert proposal["writes_performed"] is False
    assert path.read_text(encoding="utf-8") == before
    assert proposal["diff"]["catalog_metadata.citation_urls"]["to"] == ["https://example.test/fresh"]


def test_record_operator_curation_writes_overlay(tmp_path, monkeypatch):
    mod = load_module()
    monkeypatch.setenv("TOOL_DISCOVERY_TODAY", "2026-05-12")
    catalog = tmp_path / "catalog"
    vault = tmp_path / "vault"
    write_catalog(catalog, base_entry("tool-high", fit="HIGH"))

    receipt = mod.record_operator_curation_result(
        "tool-high",
        "acme",
        {
            "installed_state_by_host": {
                "primary-laptop": {
                    "state": "installed",
                    "detected_version": "1.0",
                    "canary_status": "passed",
                    "last_seen_on_host": "primary-laptop",
                }
            },
            "conflict_reason": "operator verified installation",
        },
        vault_root=str(vault),
        catalog_dir=str(catalog),
    )

    overlay_path = Path(receipt["overlay_path"])
    assert overlay_path.is_file()
    data = yaml.safe_load(overlay_path.read_text(encoding="utf-8"))
    assert data["overlay_metadata"]["source"] == "operator-curated"
    assert data["overlay_metadata"]["canonical_revision_base"] == 1
    assert data["installed_state_by_host"]["primary-laptop"]["canary_status"] == "passed"


def test_record_execution_evidence_writes_overlay_execution_scope(tmp_path, monkeypatch):
    mod = load_module()
    monkeypatch.setenv("TOOL_DISCOVERY_CLIENT_SLUG", "acme")
    vault = tmp_path / "vault"

    receipt = mod.record_execution_evidence_result(
        "tool-high",
        "test:tool-high@1",
        "render-fixture-007",
        "cinematic_volumetric_render",
        {
            "ticket_id": "T-052",
            "tier": 3,
            "decision": "REJECT",
            "root_cause": "tool_ceiling",
            "root_cause_confidence": "high",
            "observed_ceiling": "Fixture ceiling reached.",
            "date": "2026-05-12",
            "evidence_pointer": "vault/clients/acme/snapshots/render-fixture-007/checkpoint.md",
        },
        vault_root=str(vault),
    )

    evidence_path = Path(receipt["evidence_path"])
    assert receipt["writes_performed"] is True
    assert receipt["promotion_required"] is True
    assert evidence_path == (
        vault
        / "clients"
        / "acme"
        / "tools-catalog-overlay"
        / "evidence"
        / "render-fixture-007"
        / "execution"
        / "tool-high-3-REJECT-2026-05-12.yaml"
    )
    assert evidence_path.is_file()
    data = yaml.safe_load(evidence_path.read_text(encoding="utf-8"))
    assert data["tool_stack_id"] == "test:tool-high@1"
    assert data["evidence"]["root_cause"] == "tool_ceiling"
    assert not (vault / "archive" / "tools-catalog").exists()
