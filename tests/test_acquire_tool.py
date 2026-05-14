from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import jsonschema
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
ACQUIRE_PATH = REPO_ROOT / "scripts" / "acquire_tool.py"
CANARY_PATH = REPO_ROOT / "scripts" / "check_tool_acquisition.py"
MANIFEST_SCHEMA_PATH = REPO_ROOT / "schemas" / "acquisition-manifest.schema.json"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def entry(
    *,
    slug="fixture-tool",
    install_method="package_manager",
    cost=0,
    canary_steps=None,
    mcp_registration=None,
    os_values=None,
):
    return {
        "tool_slug": slug,
        "tool_stack_id": f"fixture:{slug}@1",
        "display_name": slug.replace("-", " ").title(),
        "versions": [{"version": "1.2.3", "released": "2026-01-01"}],
        "capabilities": [
            {
                "id": "fixture_capability",
                "bar_fit_default": "HIGH",
                "bar_fit_evidence": [{"type": "test", "source": "fixture", "summary": "fixture"}],
                "known_ceilings": [],
            }
        ],
        "constraints": {
            "os": os_values or ["macos", "linux"],
            "arch": ["arm64", "x86_64"],
            "acquisition_cost_usd": cost,
            "recurrence": "annual" if cost else "none",
            "license": "commercial_indie" if cost else "mit",
            "local_runnable": True,
            "network_required": False,
            "credentials_required": bool(cost),
        },
        "acquisition": {
            "install_method": install_method,
            "install_risk": "low",
            "package_manager": "pip",
            "package": "fixture-package",
            "install_steps_summary": "Install safely.",
            "canary_type": "functional",
            "canary_steps": canary_steps
            or [
                {
                    "type": "command",
                    "name": "exercise capability",
                    "command": [sys.executable, "-c", "open('canary.out','w').write('ok')"],
                },
                {"type": "assert_path_exists", "path": "canary.out"},
            ],
            "credentials_needed": [],
            "credential_handoff": "none",
        },
        "catalog_metadata": {
            "source": "canonical",
            "terms_last_checked": "2026-05-12",
            "ttl_days_by_domain": {"pricing": 90, "licensing": 180, "capability_evidence": 365},
            "citation_urls": ["https://example.test/tool"],
            "catalog_revision": 1,
            "last_validated": "2026-05-12",
        },
        "mcp_registration": mcp_registration,
    }


def auth(amount=269, paid_via="spending_mcp"):
    return {
        "authorization_id": "auth-fixture-001",
        "spend_approved": True,
        "currency": "USD",
        "max_authorized_amount_usd": amount,
        "vendor": "Fixture Vendor",
        "recurrence": "annual",
        "paid_via": paid_via,
        "approval_source": "operator fixture",
    }


class MockAdapter:
    def __init__(self, *, installed=False, fail_step=None):
        self.installed = installed
        self.fail_step = fail_step
        self.calls = []
        self.rollback_calls = []

    def is_installed(self, manifest):
        self.calls.append(("is_installed", manifest["manifest_id"]))
        return self.installed

    def execute_step(self, step, manifest):
        self.calls.append(("execute_step", step["kind"]))
        if self.fail_step == step["kind"]:
            return {"ok": False, "error": "fixture failure"}
        return {"ok": True, "step": step["kind"]}

    def rollback_step(self, action, manifest):
        self.rollback_calls.append(action["action"])
        return {"ok": True, "action": action["action"]}


class MockSpending:
    def __init__(self):
        self.calls = []

    def quote_spend(self, **kwargs):
        self.calls.append(("quote", kwargs))
        return {"status": "OK", "quote_id": "quote-fixture", "projected_balance": {}}

    def reserve_spend(self, **kwargs):
        self.calls.append(("reserve", kwargs))
        return {"status": "OK", "reservation": {"reservation_id": "res-fixture", "authorization_id": kwargs["authorization_id"]}}

    def capture_spend(self, **kwargs):
        self.calls.append(("capture", kwargs))
        return {"status": "OK", "capture": {"reservation_id": kwargs["reservation_id"], "receipt_ref": kwargs["receipt_ref"]}}

    def release_reservation(self, **kwargs):
        self.calls.append(("release", kwargs))
        return {"status": "OK", "release": {"reservation_id": kwargs["reservation_id"], "reason": kwargs["reason"]}}


def ok_canary(entry, *, install_root, evidence_dir):
    evidence_dir.mkdir(parents=True, exist_ok=True)
    evidence = evidence_dir / "canary.json"
    evidence.write_text(json.dumps({"ok": True}), encoding="utf-8")
    return {"ok": True, "evidence_pointer": str(evidence)}


def failing_canary(entry, *, install_root, evidence_dir):
    evidence_dir.mkdir(parents=True, exist_ok=True)
    return {"ok": False, "error": "tool not present", "evidence_pointer": str(evidence_dir / "missing.json")}


def test_manifest_schema_and_dry_run_has_no_external_mutation(tmp_path):
    acquire = load_module(ACQUIRE_PATH, "acquire_tool_manifest_test")
    tool = entry()
    manifest = acquire.build_manifest(
        tool,
        project_slug="demo-project",
        client_slug="personal",
        repo_root=tmp_path,
        vault_root=tmp_path / "vault",
    )
    schema = json.loads(MANIFEST_SCHEMA_PATH.read_text(encoding="utf-8"))
    jsonschema.Draft7Validator(schema).validate(manifest)

    adapter = MockAdapter()
    spending = MockSpending()
    result = acquire.execute_manifest(
        manifest,
        catalog_entry=tool,
        adapter=adapter,
        spending=spending,
        execute=False,
        repo_root=tmp_path,
        vault_root=tmp_path / "vault",
    )
    assert result["status"] == "dry_run"
    assert adapter.calls == []
    assert spending.calls == []
    assert not (tmp_path / ".mcp.json").exists()


def test_functional_canary_runs_capability_steps(tmp_path):
    canary = load_module(CANARY_PATH, "check_tool_acquisition_test")
    install_root = tmp_path / "install"
    install_root.mkdir()
    report = canary.run_canary(entry(), install_root=install_root, evidence_dir=tmp_path / "evidence")
    assert report["ok"] is True
    assert (install_root / "canary.out").read_text(encoding="utf-8") == "ok"


def test_functional_canary_rejects_version_only_check(tmp_path):
    canary = load_module(CANARY_PATH, "check_tool_acquisition_version_test")
    install_root = tmp_path / "install"
    install_root.mkdir()
    tool = entry(canary_steps=[{"type": "command", "command": [sys.executable, "--version"]}])
    report = canary.run_canary(tool, install_root=install_root, evidence_dir=tmp_path / "evidence")
    assert report["ok"] is False
    assert "not only --version" in report["error"]


def test_malicious_manifest_and_direct_mcp_config_mutation_are_rejected(tmp_path):
    acquire = load_module(ACQUIRE_PATH, "acquire_tool_policy_test")
    manifest = acquire.build_manifest(entry(), project_slug="demo-project", repo_root=tmp_path, vault_root=tmp_path / "vault")
    manifest["planned_steps"][0]["command"] = ["python", "-c", "print(1); rm -rf vault"]
    with pytest.raises((jsonschema.ValidationError, acquire.AcquisitionError)):
        acquire.validate_manifest(manifest)

    clean = acquire.build_manifest(entry(), project_slug="demo-project", repo_root=tmp_path, vault_root=tmp_path / "vault")
    clean["files_to_touch"].append(".mcp.json")
    with pytest.raises((jsonschema.ValidationError, acquire.AcquisitionError), match="mcp|MCP|\\.mcp"):
        acquire.validate_manifest(clean)


def test_secret_values_in_oai_authorization_are_rejected():
    acquire = load_module(ACQUIRE_PATH, "acquire_tool_secret_test")
    with pytest.raises(acquire.AcquisitionError, match="literal secret"):
        acquire._load_authorization(json.dumps({"authorization_id": "auth", "api_key": "literal-secret-value"}))


def test_checksum_or_install_failure_rolls_back_and_releases_reservation(tmp_path):
    acquire = load_module(ACQUIRE_PATH, "acquire_tool_rollback_test")
    (tmp_path / ".mcp.json").write_text(json.dumps({"mcpServers": {"spending": {"args": ["mcps/spending/server.py"]}}}), encoding="utf-8")
    tool = entry(install_method="binary_download", cost=269)
    tool["acquisition"]["binary"] = {
        "version": "1.2.3",
        "source_url": "https://example.test/tool.tar.gz",
        "sha256": "a" * 64,
    }
    manifest = acquire.approve_manifest(
        acquire.build_manifest(
            tool,
            project_slug="demo-project",
            authorization=auth(),
            repo_root=tmp_path,
            vault_root=tmp_path / "vault",
        ),
        operator_id="operator",
        approval_source="fixture",
    )
    adapter = MockAdapter(fail_step="binary_download")
    spending = MockSpending()
    result = acquire.execute_manifest(
        manifest,
        catalog_entry=tool,
        adapter=adapter,
        spending=spending,
        canary_runner=ok_canary,
        execute=True,
        repo_root=tmp_path,
        vault_root=tmp_path / "vault",
    )
    assert result["status"] == "rolled_back"
    assert [call[0] for call in spending.calls] == ["quote", "reserve", "release"]
    assert "remove_path" in adapter.rollback_calls


def test_already_installed_tool_skips_install_but_runs_canary(tmp_path):
    acquire = load_module(ACQUIRE_PATH, "acquire_tool_idempotent_test")
    tool = entry()
    manifest = acquire.approve_manifest(
        acquire.build_manifest(tool, project_slug="demo-project", repo_root=tmp_path, vault_root=tmp_path / "vault"),
        operator_id="operator",
        approval_source="fixture",
    )
    adapter = MockAdapter(installed=True)
    result = acquire.execute_manifest(
        manifest,
        catalog_entry=tool,
        adapter=adapter,
        spending=MockSpending(),
        canary_runner=ok_canary,
        execute=True,
        repo_root=tmp_path,
        vault_root=tmp_path / "vault",
    )
    assert result["ok"] is True
    assert result["install_status"] == "already_installed"
    assert ("execute_step", "pip_install") not in adapter.calls
    second = acquire.execute_manifest(
        manifest,
        catalog_entry=tool,
        adapter=adapter,
        spending=MockSpending(),
        canary_runner=ok_canary,
        execute=True,
        repo_root=tmp_path,
        vault_root=tmp_path / "vault",
    )
    assert second["status"] == "cached"


def test_unsupported_os_fails_preflight_before_install(tmp_path):
    acquire = load_module(ACQUIRE_PATH, "acquire_tool_os_test")
    tool = entry(os_values=["plan9"])
    with pytest.raises(acquire.AcquisitionError, match="does not support"):
        acquire.build_manifest(tool, project_slug="demo-project", repo_root=tmp_path, vault_root=tmp_path / "vault")


def test_spending_mcp_flow_captures_and_writes_register_mcp_proposal(tmp_path):
    acquire = load_module(ACQUIRE_PATH, "acquire_tool_spending_test")
    (tmp_path / ".mcp.json").write_text(json.dumps({"mcpServers": {"spending": {"args": ["mcps/spending/server.py"]}}}), encoding="utf-8")
    tool = entry(
        cost=269,
        mcp_registration={
            "server_name": "fixture-mcp",
            "server_path": "/tmp/fixture/server.py",
            "env_vars": {"FIXTURE_API_KEY": "operator-provided env var"},
        },
    )
    manifest = acquire.approve_manifest(
        acquire.build_manifest(
            tool,
            project_slug="demo-project",
            authorization=auth(),
            repo_root=tmp_path,
            vault_root=tmp_path / "vault",
        ),
        operator_id="operator",
        approval_source="fixture",
    )
    spending = MockSpending()
    result = acquire.execute_manifest(
        manifest,
        catalog_entry=tool,
        adapter=MockAdapter(),
        spending=spending,
        canary_runner=ok_canary,
        execute=True,
        repo_root=tmp_path,
        vault_root=tmp_path / "vault",
    )
    assert result["ok"] is True
    assert [call[0] for call in spending.calls] == ["quote", "reserve", "capture"]
    proposal = tmp_path / "vault" / "clients" / "_platform" / "mcps" / "fixture-tool" / "registration-proposal.yaml"
    assert proposal.is_file()
    assert not (tmp_path / ".mcp.json").read_text(encoding="utf-8").count("fixture-mcp")


def test_operator_declines_manifest_releases_reservation_without_install_or_proposal(tmp_path):
    acquire = load_module(ACQUIRE_PATH, "acquire_tool_decline_test")
    tool = entry(cost=269, mcp_registration={"server_name": "fixture-mcp", "server_path": "/tmp/server.py", "env_vars": {}})
    manifest = acquire.decline_manifest(
        acquire.build_manifest(tool, project_slug="demo-project", authorization=auth(), repo_root=tmp_path, vault_root=tmp_path / "vault"),
        operator_id="operator",
        approval_source="fixture",
    )
    manifest["spend_reservation"]["mode"] = "spending_mcp"
    manifest["spend_reservation"]["reservation_id"] = "res-fixture"
    adapter = MockAdapter()
    spending = MockSpending()
    result = acquire.execute_manifest(
        manifest,
        catalog_entry=tool,
        adapter=adapter,
        spending=spending,
        execute=True,
        repo_root=tmp_path,
        vault_root=tmp_path / "vault",
    )
    assert result["status"] == "declined"
    assert [call[0] for call in spending.calls] == ["release"]
    assert adapter.calls == []
    assert not (tmp_path / "vault" / "clients" / "_platform" / "mcps" / "fixture-tool" / "registration-proposal.yaml").exists()


def test_operator_out_of_band_flow_skips_spending_and_waits_for_canary(tmp_path):
    acquire = load_module(ACQUIRE_PATH, "acquire_tool_oob_test")
    tool = entry(install_method="vendor_installer", cost=269)
    manifest = acquire.approve_manifest(
        acquire.build_manifest(
            tool,
            project_slug="demo-project",
            authorization=auth(paid_via="operator_out_of_band"),
            repo_root=tmp_path,
            vault_root=tmp_path / "vault",
        ),
        operator_id="operator",
        approval_source="fixture",
    )
    spending = MockSpending()
    adapter = MockAdapter()
    result = acquire.execute_manifest(
        manifest,
        catalog_entry=tool,
        adapter=adapter,
        spending=spending,
        canary_runner=failing_canary,
        execute=True,
        repo_root=tmp_path,
        vault_root=tmp_path / "vault",
    )
    assert result["status"] == "tool_presence_canary_waiting"
    assert spending.calls == []
    assert adapter.calls == []
