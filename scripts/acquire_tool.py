#!/usr/bin/env python3
"""
Acquire a catalog tool through a dry-run-first transaction manifest.

Real mutation is only available through `execute --execute` and only when the
manifest has an approved operator signature. MCP registry writes are never
performed here; this script writes registration proposals for register-mcp.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib.util
import json
import os
import platform
import shutil
import subprocess
import sys
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import jsonschema
import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
from check_tool_acquisition import run_canary

SCHEMA_DIR = REPO_ROOT / "schemas"
DEFAULT_CATALOG_DIR = REPO_ROOT / "vault" / "archive" / "tools-catalog"
DEFAULT_VAULT_ROOT = REPO_ROOT / "vault"
TOOLS_CACHE = DEFAULT_VAULT_ROOT / "clients" / "_platform" / "tools-cache"

UNSAFE_ARG_TOKENS = ("&&", "|", ";", "`", "$(", "\n")
SECRET_KEY_TOKENS = ("secret", "token", "api_key", "apikey", "password", "license_key", "credential")
SECRET_VALUE_PREFIXES = (
    "literal-secret-",
    "sk" "-",
    "sk" "_live_",
    "sk" "_test_",
    "ghp_",
    "github_pat_",
    "xoxb-",
    "AKIA",
)
SAFE_SECRET_KEYS = {
    "sha256",
    "checksum",
    "signature",
    "signature_url",
    "source_url",
    "url",
    "manifest_id",
    "authorization_id",
    "reservation_id",
    "quote_id",
    "capture_id",
}


class AcquisitionError(RuntimeError):
    pass


def now_text() -> str:
    return datetime.now().astimezone().isoformat()


def load_schema(name: str) -> dict[str, Any]:
    return json.loads((SCHEMA_DIR / name).read_text(encoding="utf-8"))


ACQUISITION_SCHEMA = load_schema("acquisition-manifest.schema.json")


def load_yaml_or_json(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".json":
        data = json.loads(text)
    else:
        data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain an object")
    return data


def load_catalog_entry(tool_slug: str | None = None, *, catalog_entry: Path | None = None, catalog_dir: Path | None = None) -> dict[str, Any]:
    if catalog_entry is None:
        if not tool_slug:
            raise ValueError("tool_slug is required when catalog_entry is not provided")
        catalog_entry = (catalog_dir or DEFAULT_CATALOG_DIR) / f"{tool_slug}.yaml"
    return load_yaml_or_json(catalog_entry)


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_yaml(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def _current_os_slug() -> str:
    name = platform.system().lower()
    return {"darwin": "macos", "linux": "linux", "windows": "windows"}.get(name, name)


def _safe_arg(arg: str) -> bool:
    return not any(token in arg for token in UNSAFE_ARG_TOKENS)


def _path_touches_mcp_config(raw: str) -> bool:
    return Path(raw).name == ".mcp.json" or raw.endswith("/.mcp.json")


def _looks_like_env_var(value: str) -> bool:
    return value.isupper() and value.replace("_", "").replace("0", "").isalnum() and len(value) <= 80


def _looks_like_secret(value: str, key: str = "") -> bool:
    lower_key = key.lower()
    if key in SAFE_SECRET_KEYS or any(safe in lower_key for safe in ("sha256", "checksum", "signature", "source_url")):
        return False
    if _looks_like_env_var(value):
        return False
    if any(value.startswith(prefix) for prefix in SECRET_VALUE_PREFIXES):
        return True
    if _looks_like_env_var(key):
        return False
    if any(token in lower_key for token in SECRET_KEY_TOKENS):
        return len(value) > 12 and not value.startswith("$") and not value.startswith("env:")
    return False


def find_secret_values(value: Any, *, key: str = "", path: str = "$") -> list[str]:
    findings: list[str] = []
    if isinstance(value, dict):
        for child_key, child_value in value.items():
            findings.extend(find_secret_values(child_value, key=str(child_key), path=f"{path}.{child_key}"))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            findings.extend(find_secret_values(item, key=key, path=f"{path}[{index}]"))
    elif isinstance(value, str) and _looks_like_secret(value, key):
        findings.append(path)
    return findings


def spending_mcp_registered(repo_root: Path = REPO_ROOT) -> bool:
    config_path = repo_root / ".mcp.json"
    if not config_path.is_file():
        return False
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    servers = data.get("mcpServers") or {}
    if not isinstance(servers, dict):
        return False
    for name, config in servers.items():
        blob = json.dumps(config)
        if name in {"spending", "Agent Spending Budget"} or "mcps/spending/server.py" in blob or "spending/server.py" in blob:
            return True
    return False


def transaction_dir(manifest: dict[str, Any], *, vault_root: Path = DEFAULT_VAULT_ROOT) -> Path:
    target = manifest["acquisition_target"]
    return (
        vault_root
        / "clients"
        / target["client_slug"]
        / "snapshots"
        / target["project_slug"]
        / "tool-acquisition"
        / manifest["manifest_id"]
    )


def install_root_for(target: dict[str, Any], *, vault_root: Path = DEFAULT_VAULT_ROOT) -> Path:
    return vault_root / "clients" / target["client_slug"] / "tools" / target["project_slug"] / target["tool_slug"]


def _catalog_version(entry: dict[str, Any]) -> str | None:
    versions = entry.get("versions") or []
    if versions and isinstance(versions[0], dict):
        return versions[0].get("version")
    return None


def _binary_provenance(acquisition: dict[str, Any], version: str | None) -> dict[str, Any] | None:
    binary = acquisition.get("binary") or {}
    source_url = binary.get("source_url") or acquisition.get("source_url")
    sha256 = binary.get("sha256") or acquisition.get("sha256")
    if not source_url and not sha256:
        return None
    return {
        "version": str(binary.get("version") or version or ""),
        "source_url": source_url,
        "sha256": sha256,
        "signature_url": binary.get("signature_url") or acquisition.get("signature_url"),
        "tls_provenance_check": "required",
        "expected_hostname": urllib.parse.urlparse(source_url or "").hostname,
    }


def build_manifest(
    entry: dict[str, Any],
    *,
    project_slug: str,
    client_slug: str = "personal",
    authorization: dict[str, Any] | None = None,
    created_by: str = "codex",
    repo_root: Path = REPO_ROOT,
    vault_root: Path = DEFAULT_VAULT_ROOT,
    manifest_id: str | None = None,
) -> dict[str, Any]:
    acquisition = entry.get("acquisition") or {}
    constraints = entry.get("constraints") or {}
    tool_slug = entry["tool_slug"]
    version = _catalog_version(entry)
    install_method = acquisition.get("install_method", "built_in")
    target = {
        "tool_slug": tool_slug,
        "tool_stack_id": entry.get("tool_stack_id"),
        "project_slug": project_slug,
        "client_slug": client_slug,
        "version": version,
    }
    install_root = install_root_for(target, vault_root=vault_root)
    cost = float(constraints.get("acquisition_cost_usd") or acquisition.get("cost_usd") or 0)
    recurrence = constraints.get("recurrence") or acquisition.get("recurrence") or ("one_time" if cost else "none")
    auth = authorization or {}
    paid_via = auth.get("paid_via") if auth.get("spend_approved") else "n_a"
    if paid_via == "spending_mcp" and spending_mcp_registered(repo_root):
        spend_mode = "spending_mcp"
    elif cost > 0:
        spend_mode = "operator_out_of_band"
    else:
        spend_mode = "none"

    files_to_touch = [
        str(install_root.relative_to(repo_root)) if install_root.is_relative_to(repo_root) else str(install_root),
        f"vault/clients/{client_slug}/snapshots/{project_slug}/tool-acquisition/{manifest_id or '<manifest_id>'}/manifest.json",
    ]
    planned_steps: list[dict[str, Any]] = [
        {
            "step_id": "preflight",
            "kind": "preflight",
            "description": "Validate OS support, install scope, secrets policy, binary provenance, and MCP registry isolation.",
            "mutation": "none",
            "command": None,
            "package": None,
            "version": None,
            "binary": None,
            "files_to_touch": [],
            "global_install": False,
            "global_install_approval": None,
            "requires_secret_env_vars": [],
            "operator_action_prompt": None,
            "mcp_registration_proposal_path": None,
        }
    ]

    credentials = acquisition.get("credentials_needed") or []
    if credentials:
        env_vars = [str(item).upper() for item in credentials if str(item).upper() == str(item)]
        planned_steps.append(
            {
                "step_id": "secret-check",
                "kind": "api_secret_check",
                "description": "Read required credentials from environment or keychain at execute time; never from vault content.",
                "mutation": "none",
                "command": None,
                "package": None,
                "version": None,
                "binary": None,
                "files_to_touch": [],
                "global_install": False,
                "global_install_approval": None,
                "requires_secret_env_vars": env_vars,
                "operator_action_prompt": acquisition.get("operator_action_prompt")
                or "Operator must provide credentials out-of-band.",
                "mcp_registration_proposal_path": None,
            }
        )

    install_step = {
        "step_id": "install",
        "kind": "operator_action",
        "description": "No automated install required.",
        "mutation": "none",
        "command": None,
        "package": None,
        "version": version,
        "binary": None,
        "files_to_touch": [],
        "global_install": False,
        "global_install_approval": None,
        "requires_secret_env_vars": [],
        "operator_action_prompt": None,
        "mcp_registration_proposal_path": None,
    }
    install_scope = "project_local"
    if install_method == "package_manager":
        manager = acquisition.get("package_manager", "pip")
        package = acquisition.get("package") or tool_slug
        if manager == "npm":
            install_step.update(
                {
                    "kind": "npm_install",
                    "description": f"Install npm package {package} into the project-local tools directory.",
                    "mutation": "filesystem",
                    "package": package,
                    "files_to_touch": [str(install_root)],
                }
            )
        else:
            install_step.update(
                {
                    "kind": "pip_install",
                    "description": f"Install Python package {package} into a project-local virtualenv.",
                    "mutation": "filesystem",
                    "package": package,
                    "files_to_touch": [str(install_root)],
                }
            )
    elif install_method == "binary_download":
        binary = _binary_provenance(acquisition, version)
        install_scope = "oneshot_tools_cache"
        cache_path = TOOLS_CACHE / tool_slug / str((binary or {}).get("version") or version or "unknown")
        files_to_touch.append(str(cache_path))
        install_step.update(
            {
                "kind": "binary_download",
                "description": "Download a pinned binary into the OneShot tools cache after TLS and checksum validation.",
                "mutation": "filesystem",
                "binary": binary,
                "files_to_touch": [str(cache_path)],
            }
        )
    elif install_method == "vendor_installer":
        install_step.update(
            {
                "kind": "vendor_installer",
                "description": acquisition.get("install_steps_summary") or "Run the vendor installer under operator-approved terms.",
                "mutation": "external",
                "operator_action_prompt": acquisition.get("operator_action_prompt") or acquisition.get("install_steps_summary"),
                "files_to_touch": [str(install_root)],
            }
        )
    elif install_method == "api_only":
        install_step.update(
            {
                "kind": "api_secret_check",
                "description": "Validate API credentials are present as environment variables or keychain entries.",
                "mutation": "none",
                "requires_secret_env_vars": [str(item).upper() for item in credentials if str(item).upper() == str(item)],
            }
        )
    elif install_method == "built_in":
        install_step.update({"kind": "operator_action", "description": "Tool is built in; only canary validation is required."})
    planned_steps.append(install_step)

    if acquisition.get("canary_type") != "not_required":
        planned_steps.append(
            {
                "step_id": "canary",
                "kind": "canary",
                "description": "Run the catalog functional canary and write evidence.",
                "mutation": "filesystem",
                "command": None,
                "package": None,
                "version": None,
                "binary": None,
                "files_to_touch": [
                    f"vault/clients/{client_slug}/snapshots/{project_slug}/tool-acquisition/{manifest_id or '<manifest_id>'}"
                ],
                "global_install": False,
                "global_install_approval": None,
                "requires_secret_env_vars": [],
                "operator_action_prompt": None,
                "mcp_registration_proposal_path": None,
            }
        )

    mcp_registration = acquisition.get("mcp_registration") or entry.get("mcp_registration")
    registration_proposal = None
    if mcp_registration:
        proposal_path = f"vault/clients/_platform/mcps/{tool_slug}/registration-proposal.yaml"
        planned_steps.append(
            {
                "step_id": "registration-proposal",
                "kind": "mcp_registration_proposal",
                "description": "Write a register-mcp proposal artifact; do not edit .mcp.json.",
                "mutation": "filesystem",
                "command": None,
                "package": None,
                "version": None,
                "binary": None,
                "files_to_touch": [proposal_path],
                "global_install": False,
                "global_install_approval": None,
                "requires_secret_env_vars": [],
                "operator_action_prompt": None,
                "mcp_registration_proposal_path": proposal_path,
            }
        )
        registration_proposal = {
            "required": True,
            "proposal_path": proposal_path,
            "server_name": mcp_registration.get("server_name") or tool_slug,
            "server_path": mcp_registration.get("server_path"),
            "env_vars": mcp_registration.get("env_vars") or {},
        }
    else:
        registration_proposal = {
            "required": False,
            "proposal_path": None,
            "server_name": None,
            "server_path": None,
            "env_vars": {},
        }

    rollback_plan = [
        {"action": "release_reservation", "target": "spend_reservation", "condition": "reservation exists and capture has not happened"},
        {"action": "remove_path", "target": str(install_root), "condition": "path was created by this transaction"},
    ]
    if install_method == "package_manager":
        rollback_plan.insert(1, {"action": "pip_uninstall", "target": acquisition.get("package") or tool_slug, "condition": "pip install was performed"})
    if install_method == "binary_download":
        rollback_plan.insert(1, {"action": "remove_path", "target": f"vault/clients/_platform/tools-cache/{tool_slug}", "condition": "binary cache path was created"})

    manifest = {
        "manifest_id": manifest_id or str(uuid.uuid4()),
        "created_at": now_text(),
        "created_by": created_by,
        "acquisition_target": target,
        "catalog_entry_ref": entry.get("tool_slug"),
        "install_scope": install_scope,
        "planned_steps": planned_steps,
        "files_to_touch": files_to_touch,
        "spend_reservation": {
            "mode": spend_mode,
            "project_slug": project_slug,
            "vendor": auth.get("vendor") or entry.get("display_name"),
            "amount_usd": cost,
            "max_authorized_amount_usd": auth.get("max_authorized_amount_usd"),
            "recurrence": recurrence,
            "category": "tool_acquisition",
            "authorization_id": auth.get("authorization_id"),
            "quote_id": None,
            "reservation_id": None,
            "receipt_ref": None,
        },
        "operator_approval_status": "pending",
        "operator_approval_signature": None,
        "rollback_plan": rollback_plan,
        "registration_proposal": registration_proposal,
        "preflight_checks": [
            "schema",
            "secrets",
            "install_scope",
            "mcp_registry_isolation",
            "os_support",
            "binary_provenance",
        ],
        "dry_run_default": True,
        "execution": {"state": "planned"},
    }
    validate_manifest(manifest, catalog_entry=entry)
    return manifest


def approve_manifest(manifest: dict[str, Any], *, operator_id: str, approval_source: str) -> dict[str, Any]:
    updated = json.loads(json.dumps(manifest))
    updated["operator_approval_status"] = "approved"
    updated["operator_approval_signature"] = {
        "operator_id": operator_id,
        "signed_at": now_text(),
        "approval_source": approval_source,
    }
    validate_manifest(updated)
    return updated


def decline_manifest(manifest: dict[str, Any], *, operator_id: str, approval_source: str) -> dict[str, Any]:
    updated = json.loads(json.dumps(manifest))
    updated["operator_approval_status"] = "declined"
    updated["operator_approval_signature"] = {
        "operator_id": operator_id,
        "signed_at": now_text(),
        "approval_source": approval_source,
    }
    validate_manifest(updated)
    return updated


def validate_manifest(manifest: dict[str, Any], *, catalog_entry: dict[str, Any] | None = None) -> None:
    jsonschema.Draft7Validator(ACQUISITION_SCHEMA).validate(manifest)
    secret_paths = find_secret_values(manifest)
    if secret_paths:
        raise AcquisitionError(f"manifest contains literal secret values at: {', '.join(secret_paths)}")
    if manifest["install_scope"] == "global":
        for step in manifest["planned_steps"]:
            if not step.get("global_install") or not (step.get("global_install_approval") or {}).get("approved"):
                raise AcquisitionError("global installs require explicit approval recorded in the manifest")
    for raw_path in manifest.get("files_to_touch") or []:
        if _path_touches_mcp_config(str(raw_path)):
            raise AcquisitionError("Acquire-Tool must not touch .mcp.json; use register-mcp proposals only")
    for step in manifest["planned_steps"]:
        for raw_path in step.get("files_to_touch") or []:
            if _path_touches_mcp_config(str(raw_path)):
                raise AcquisitionError("Acquire-Tool must not touch .mcp.json; use register-mcp proposals only")
        command = step.get("command")
        if isinstance(command, str):
            raise AcquisitionError("planned step command must be an argv array, not a shell string")
        if isinstance(command, list) and not all(isinstance(arg, str) and _safe_arg(arg) for arg in command):
            raise AcquisitionError("planned step command contains unsafe shell tokens")
        if step["kind"] == "binary_download":
            binary = step.get("binary") or {}
            if not binary.get("version") or binary.get("version") == "latest":
                raise AcquisitionError("binary downloads require a pinned non-latest version")
            if not str(binary.get("source_url", "")).startswith("https://"):
                raise AcquisitionError("binary downloads require an https source_url")
            if not binary.get("sha256"):
                raise AcquisitionError("binary downloads require a sha256 checksum")
        if step.get("global_install") and not (step.get("global_install_approval") or {}).get("approved"):
            raise AcquisitionError("global install step lacks explicit operator approval")
    proposal = manifest.get("registration_proposal") or {}
    if proposal.get("required"):
        proposal_path = proposal.get("proposal_path") or ""
        expected = f"vault/clients/_platform/mcps/{manifest['acquisition_target']['tool_slug']}/registration-proposal.yaml"
        if proposal_path != expected:
            raise AcquisitionError(f"MCP registration proposal must be written to {expected}")
    if catalog_entry:
        supported = set((catalog_entry.get("constraints") or {}).get("os") or [])
        if supported and _current_os_slug() not in supported:
            raise AcquisitionError(f"tool does not support this OS: {_current_os_slug()}")


class RealInstallAdapter:
    def is_installed(self, manifest: dict[str, Any]) -> bool:
        root = install_root_for(manifest["acquisition_target"])
        return root.exists() and any(root.iterdir())

    def execute_step(self, step: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any]:
        target = manifest["acquisition_target"]
        root = install_root_for(target)
        root.mkdir(parents=True, exist_ok=True)
        if step["kind"] == "pip_install":
            venv = root / ".venv"
            if not venv.exists():
                subprocess.run([sys.executable, "-m", "venv", str(venv)], check=True)
            pip = venv / "bin" / "pip"
            package = step["package"]
            subprocess.run([str(pip), "install", package], check=True)
            return {"ok": True, "installed": package, "path": str(venv)}
        if step["kind"] == "npm_install":
            package = step["package"]
            subprocess.run(["npm", "install", "--prefix", str(root), package], check=True)
            return {"ok": True, "installed": package, "path": str(root)}
        if step["kind"] == "binary_download":
            binary = step["binary"]
            cache_dir = TOOLS_CACHE / target["tool_slug"] / binary["version"]
            cache_dir.mkdir(parents=True, exist_ok=True)
            destination = cache_dir / Path(urllib.parse.urlparse(binary["source_url"]).path).name
            parsed = urllib.parse.urlparse(binary["source_url"])
            if parsed.scheme != "https" or not parsed.hostname:
                raise AcquisitionError("binary download failed TLS provenance check")
            with urllib.request.urlopen(binary["source_url"], timeout=120) as response:
                payload = response.read()
            digest = hashlib.sha256(payload).hexdigest()
            if digest.lower() != binary["sha256"].lower():
                raise AcquisitionError("binary checksum mismatch")
            destination.write_bytes(payload)
            destination.chmod(0o755)
            return {"ok": True, "downloaded": str(destination), "sha256": digest}
        if step["kind"] == "vendor_installer":
            return {
                "ok": False,
                "operator_action_required": True,
                "prompt": step.get("operator_action_prompt") or step["description"],
            }
        return {"ok": True, "skipped": step["kind"]}

    def rollback_step(self, action: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any]:
        target = action["target"]
        if action["action"] == "remove_path":
            path = Path(target)
            if not path.is_absolute():
                path = REPO_ROOT / path
            if path.exists():
                if path.is_dir():
                    shutil.rmtree(path)
                else:
                    path.unlink()
            return {"ok": True, "removed": str(path)}
        if action["action"] == "pip_uninstall":
            root = install_root_for(manifest["acquisition_target"])
            pip = root / ".venv" / "bin" / "pip"
            if pip.exists():
                subprocess.run([str(pip), "uninstall", "-y", target], check=False)
            return {"ok": True, "uninstalled": target}
        return {"ok": True, "skipped": action["action"]}


class DirectSpendingAdapter:
    def __init__(self, server_path: Path | None = None):
        path = server_path or (REPO_ROOT / "vault" / "clients" / "_platform" / "mcps" / "spending" / "server.py")
        spec = importlib.util.spec_from_file_location("oneshot_spending_mcp_direct", path)
        module = importlib.util.module_from_spec(spec)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"could not load spending MCP: {path}")
        spec.loader.exec_module(module)
        self.module = module

    def quote_spend(self, **kwargs: Any) -> dict[str, Any]:
        return json.loads(asyncio.run(self.module.quote_spend(**kwargs)))

    def reserve_spend(self, **kwargs: Any) -> dict[str, Any]:
        return json.loads(asyncio.run(self.module.reserve_spend(**kwargs)))

    def capture_spend(self, **kwargs: Any) -> dict[str, Any]:
        return json.loads(asyncio.run(self.module.capture_spend(**kwargs)))

    def release_reservation(self, **kwargs: Any) -> dict[str, Any]:
        return json.loads(asyncio.run(self.module.release_reservation(**kwargs)))


class NullSpendingAdapter:
    def quote_spend(self, **kwargs: Any) -> dict[str, Any]:
        return {"status": "OK", "quote_id": f"quote-{uuid.uuid4()}", "projected_balance": {}}

    def reserve_spend(self, **kwargs: Any) -> dict[str, Any]:
        return {
            "status": "OK",
            "reservation": {
                "reservation_id": f"res-{uuid.uuid4()}",
                "authorization_id": kwargs.get("authorization_id"),
            },
        }

    def capture_spend(self, **kwargs: Any) -> dict[str, Any]:
        return {"status": "OK", "capture": {"reservation_id": kwargs.get("reservation_id"), "receipt_ref": kwargs.get("receipt_ref")}}

    def release_reservation(self, **kwargs: Any) -> dict[str, Any]:
        return {"status": "OK", "release": {"reservation_id": kwargs.get("reservation_id"), "reason": kwargs.get("reason")}}


def _run_preflight(manifest: dict[str, Any], catalog_entry: dict[str, Any] | None = None) -> dict[str, Any]:
    validate_manifest(manifest, catalog_entry=catalog_entry)
    return {"ok": True, "checked": manifest.get("preflight_checks", [])}


def _write_registration_proposal(manifest: dict[str, Any], *, repo_root: Path = REPO_ROOT) -> Path | None:
    proposal = manifest.get("registration_proposal") or {}
    if not proposal.get("required"):
        return None
    proposal_path = repo_root / proposal["proposal_path"]
    data = {
        "proposal_type": "mcp_registration",
        "created_at": now_text(),
        "source_manifest_id": manifest["manifest_id"],
        "server_name": proposal["server_name"],
        "server_path": proposal["server_path"],
        "env_vars": proposal.get("env_vars") or {},
        "register_mcp_required": True,
        "agent_must_not_edit_mcp_json": True,
        "next_step": "Review and execute through skills/register-mcp.md.",
    }
    write_yaml(proposal_path, data)
    return proposal_path


def _release_if_needed(manifest: dict[str, Any], spending: Any, reason: str) -> dict[str, Any] | None:
    spend = manifest.get("spend_reservation") or {}
    reservation_id = spend.get("reservation_id")
    if spend.get("mode") == "spending_mcp" and reservation_id:
        return spending.release_reservation(
            reservation_id=reservation_id,
            reason=reason,
            project_slug=spend.get("project_slug") or "",
            category=spend.get("category") or "",
        )
    return None


def rollback_transaction(
    manifest: dict[str, Any],
    *,
    adapter: Any | None = None,
    spending: Any | None = None,
    reason: str = "rollback requested",
    repo_root: Path = REPO_ROOT,
    vault_root: Path = DEFAULT_VAULT_ROOT,
) -> dict[str, Any]:
    adapter = adapter or RealInstallAdapter()
    spending = spending or NullSpendingAdapter()
    results = []
    release = _release_if_needed(manifest, spending, reason)
    if release is not None:
        results.append({"action": "release_reservation", "result": release})
    for action in manifest.get("rollback_plan") or []:
        if action["action"] == "release_reservation":
            continue
        try:
            results.append({"action": action["action"], "result": adapter.rollback_step(action, manifest)})
        except Exception as exc:
            results.append({"action": action["action"], "error": str(exc), "manual_cleanup_required": True})
    log = {
        "ok": True,
        "manifest_id": manifest["manifest_id"],
        "reason": reason,
        "actual_spend_usd": 0,
        "rolled_back_at": now_text(),
        "results": results,
    }
    write_json(transaction_dir(manifest, vault_root=vault_root) / "rollback-log.json", log)
    return log


def execute_manifest(
    manifest: dict[str, Any],
    *,
    catalog_entry: dict[str, Any] | None = None,
    adapter: Any | None = None,
    spending: Any | None = None,
    execute: bool = False,
    repo_root: Path = REPO_ROOT,
    vault_root: Path = DEFAULT_VAULT_ROOT,
    canary_runner: Any = run_canary,
) -> dict[str, Any]:
    adapter = adapter or RealInstallAdapter()
    spending = spending or (DirectSpendingAdapter() if spending_mcp_registered(repo_root) else NullSpendingAdapter())
    preflight = _run_preflight(manifest, catalog_entry=catalog_entry)
    if not execute:
        return {
            "ok": True,
            "status": "dry_run",
            "manifest": manifest,
            "preflight": preflight,
            "external_mutation": False,
        }

    tx_dir = transaction_dir(manifest, vault_root=vault_root)
    tx_dir.mkdir(parents=True, exist_ok=True)
    result_path = tx_dir / "result.json"
    lock_path = tx_dir / "in-progress.lock"
    if result_path.exists():
        cached = json.loads(result_path.read_text(encoding="utf-8"))
        return {"ok": cached.get("ok", False), "status": "cached", "result": cached}
    if lock_path.exists():
        return {"ok": False, "status": "in_progress", "reason": "manifest execution already in progress"}

    if manifest["operator_approval_status"] == "declined":
        release = _release_if_needed(manifest, spending, "operator declined manifest")
        result = {"ok": False, "status": "declined", "release": release, "external_mutation": False}
        write_json(tx_dir / "result.json", result)
        return result
    if manifest["operator_approval_status"] != "approved":
        raise AcquisitionError("execute requires operator_approval_status: approved")

    lock_path.write_text(now_text(), encoding="utf-8")
    write_json(tx_dir / "manifest.json", manifest)
    installed_steps: list[dict[str, Any]] = []
    captured = False
    try:
        spend = manifest["spend_reservation"]
        if spend["mode"] == "spending_mcp" and not spend.get("reservation_id"):
            quote = spending.quote_spend(
                project_slug=spend["project_slug"],
                vendor=spend["vendor"],
                amount_usd=spend["amount_usd"],
                recurrence=spend["recurrence"],
                category=spend["category"],
                requested_by_tool_stack=manifest["acquisition_target"].get("tool_stack_id") or "",
            )
            if quote.get("status") != "OK":
                result = {"ok": False, "status": "spend_quote_rejected", "quote": quote}
                write_json(result_path, result)
                return result
            reserve = spending.reserve_spend(
                quote_id=quote["quote_id"],
                authorization_id=spend["authorization_id"],
                expires_at=(datetime.now().astimezone() + timedelta(hours=2)).isoformat(),
                project_slug=spend["project_slug"],
                category=spend["category"],
                max_authorized_amount_usd=spend.get("max_authorized_amount_usd"),
            )
            if reserve.get("status") != "OK":
                result = {"ok": False, "status": "spend_reserve_rejected", "reserve": reserve}
                write_json(result_path, result)
                return result
            spend["quote_id"] = quote["quote_id"]
            spend["reservation_id"] = reserve["reservation"]["reservation_id"]
            write_json(tx_dir / "manifest.json", manifest)

        if spend["mode"] == "operator_out_of_band" and any(step["kind"] == "vendor_installer" for step in manifest["planned_steps"]):
            canary_report = None
            if catalog_entry:
                canary_report = canary_runner(
                    catalog_entry,
                    install_root=install_root_for(manifest["acquisition_target"], vault_root=vault_root),
                    evidence_dir=tx_dir,
                )
            if not canary_report or not canary_report.get("ok"):
                result = {
                    "ok": False,
                    "status": "tool_presence_canary_waiting",
                    "canary": canary_report,
                    "external_mutation": False,
                }
                write_json(result_path, result)
                return result

        if getattr(adapter, "is_installed", lambda _manifest: False)(manifest):
            install_status = "already_installed"
        else:
            install_status = "installed"
            for step in manifest["planned_steps"]:
                if step["kind"] in {"preflight", "api_secret_check", "operator_action", "canary", "mcp_registration_proposal", "record_execution_evidence"}:
                    continue
                step_result = adapter.execute_step(step, manifest)
                if not step_result.get("ok"):
                    raise AcquisitionError(f"install step failed: {step['step_id']}: {step_result}")
                installed_steps.append({"step": step["step_id"], "result": step_result})

        canary_report = None
        if catalog_entry and any(step["kind"] == "canary" for step in manifest["planned_steps"]):
            canary_report = canary_runner(
                catalog_entry,
                install_root=install_root_for(manifest["acquisition_target"], vault_root=vault_root),
                evidence_dir=tx_dir,
            )
            if not canary_report.get("ok"):
                raise AcquisitionError(f"canary failed: {canary_report.get('error')}")

        capture = None
        if spend["mode"] == "spending_mcp" and spend.get("reservation_id"):
            receipt_ref = spend.get("receipt_ref") or str(tx_dir / "receipt.json")
            write_json(Path(receipt_ref), {"manifest_id": manifest["manifest_id"], "amount_usd": spend["amount_usd"]})
            capture = spending.capture_spend(
                reservation_id=spend["reservation_id"],
                actual_amount_usd=spend["amount_usd"],
                receipt_ref=receipt_ref,
                project_slug=spend["project_slug"],
                category=spend["category"],
            )
            if capture.get("status") != "OK":
                raise AcquisitionError(f"spend capture failed: {capture}")
            captured = True
            spend["receipt_ref"] = receipt_ref

        proposal_path = _write_registration_proposal(manifest, repo_root=repo_root)
        result = {
            "ok": True,
            "status": "acquired",
            "install_status": install_status,
            "installed_steps": installed_steps,
            "canary": canary_report,
            "capture": capture,
            "registration_proposal": str(proposal_path) if proposal_path else None,
            "manifest_path": str(tx_dir / "manifest.json"),
        }
        write_json(result_path, result)
        return result
    except BaseException as exc:
        if not captured:
            rollback_transaction(
                manifest,
                adapter=adapter,
                spending=spending,
                reason=str(exc),
                repo_root=repo_root,
                vault_root=vault_root,
            )
        result = {"ok": False, "status": "rolled_back", "error": str(exc), "installed_steps": installed_steps}
        write_json(result_path, result)
        return result
    finally:
        if lock_path.exists():
            lock_path.unlink()


def _load_authorization(path_or_json: str | None) -> dict[str, Any] | None:
    if not path_or_json:
        return None
    candidate = Path(path_or_json)
    if candidate.exists():
        data = load_yaml_or_json(candidate)
        secret_paths = find_secret_values(data)
        if secret_paths:
            raise AcquisitionError(f"OAI authorization contains literal secret values at: {', '.join(secret_paths)}")
        return data
    data = json.loads(path_or_json)
    if not isinstance(data, dict):
        raise ValueError("authorization must be a JSON object")
    secret_paths = find_secret_values(data)
    if secret_paths:
        raise AcquisitionError(f"OAI authorization contains literal secret values at: {', '.join(secret_paths)}")
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    manifest_parser = subparsers.add_parser("manifest", help="Produce and validate a dry-run transaction manifest.")
    manifest_parser.add_argument("--tool-slug")
    manifest_parser.add_argument("--catalog-entry")
    manifest_parser.add_argument("--catalog-dir", default=str(DEFAULT_CATALOG_DIR))
    manifest_parser.add_argument("--project-slug", required=True)
    manifest_parser.add_argument("--client-slug", default="personal")
    manifest_parser.add_argument("--authorization", help="Path to authorization YAML/JSON, or an inline JSON object.")
    manifest_parser.add_argument("--created-by", default="codex")
    manifest_parser.add_argument("--out", help="Optional output path for manifest JSON.")

    validate_parser = subparsers.add_parser("validate", help="Validate a transaction manifest.")
    validate_parser.add_argument("manifest")

    execute_parser = subparsers.add_parser("execute", help="Dry-run by default; real acquisition requires --execute.")
    execute_parser.add_argument("manifest")
    execute_parser.add_argument("--catalog-entry")
    execute_parser.add_argument("--execute", action="store_true")
    execute_parser.add_argument("--json", action="store_true")

    rollback_parser = subparsers.add_parser("rollback", help="Rollback a transaction by manifest.")
    rollback_parser.add_argument("manifest")
    rollback_parser.add_argument("--reason", default="operator requested rollback")
    rollback_parser.add_argument("--json", action="store_true")

    args = parser.parse_args()
    try:
        if args.command == "manifest":
            entry = load_catalog_entry(
                args.tool_slug,
                catalog_entry=Path(args.catalog_entry).resolve() if args.catalog_entry else None,
                catalog_dir=Path(args.catalog_dir).resolve(),
            )
            manifest = build_manifest(
                entry,
                project_slug=args.project_slug,
                client_slug=args.client_slug,
                authorization=_load_authorization(args.authorization),
                created_by=args.created_by,
            )
            if args.out:
                write_json(Path(args.out).resolve(), manifest)
            print(json.dumps(manifest, indent=2, sort_keys=True))
            return 0
        if args.command == "validate":
            manifest = load_yaml_or_json(Path(args.manifest).resolve())
            validate_manifest(manifest)
            print("manifest valid")
            return 0
        if args.command == "execute":
            manifest = load_yaml_or_json(Path(args.manifest).resolve())
            entry = load_catalog_entry(catalog_entry=Path(args.catalog_entry).resolve()) if args.catalog_entry else None
            result = execute_manifest(manifest, catalog_entry=entry, execute=args.execute)
            print(json.dumps(result, indent=2, sort_keys=True) if args.json else result["status"])
            return 0 if result.get("ok") else 1
        if args.command == "rollback":
            manifest = load_yaml_or_json(Path(args.manifest).resolve())
            result = rollback_transaction(manifest, reason=args.reason)
            print(json.dumps(result, indent=2, sort_keys=True) if args.json else "rollback complete")
            return 0 if result.get("ok") else 1
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    sys.exit(main())
