"""
Tool Discovery MCP Server

Tool survey and lifecycle evidence for OneShot. The server loads a canonical
YAML tool catalog plus optional per-client overlays, validates both against
schemas, and returns deterministic bar-fitness / constraint-fit rankings. Stage
2 adds overlay-scoped execution evidence writes; canonical catalog promotion
remains operator-gated.
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import jsonschema
import yaml

try:
    from mcp.server.fastmcp import FastMCP
except ModuleNotFoundError:  # Keep --check and tests usable before MCP deps are installed.
    FastMCP = None  # type: ignore[assignment]

if FastMCP is not None:
    mcp = FastMCP("tool-discovery")
else:
    class _MissingMCP:
        def tool(self):
            def decorator(func):
                return func
            return decorator

        def run(self):
            raise RuntimeError("mcp package is not installed; run pip install -r requirements.txt")

    mcp = _MissingMCP()

SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
REPO_ROOT = Path(__file__).resolve().parents[5]
DEFAULT_CATALOG_DIR = REPO_ROOT / "vault" / "archive" / "tools-catalog"
DEFAULT_VAULT_ROOT = REPO_ROOT / "vault"
SCHEMA_DIR = REPO_ROOT / "schemas"

FIT_RANK = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}
CONFIDENCE_RANK = {"high": 3, "medium": 2, "low": 1, "stale_accepted": 0}
RISK_RANK = {"low": 3, "medium": 2, "high": 1}
OPEN_SOURCE_LICENSE_TOKENS = ("gpl", "mit", "apache", "bsd", "mpl", "isc", "lgpl", "open")


def _safe_slug(value: str, *, label: str = "slug") -> str:
    if not SLUG_RE.match(value or ""):
        raise ValueError(f"invalid {label}: {value!r}")
    return value


def _schema(name: str) -> Dict[str, Any]:
    path = SCHEMA_DIR / name
    return json.loads(path.read_text(encoding="utf-8"))


CATALOG_SCHEMA = _schema("tools-catalog-entry.schema.json")
OVERLAY_SCHEMA = _schema("tools-catalog-overlay.schema.json")
EXECUTION_EVIDENCE_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "additionalProperties": True,
    "required": ["ticket_id", "tier", "decision", "date", "evidence_pointer"],
    "properties": {
        "ticket_id": {"type": "string", "pattern": r"^T-[0-9]{3,}$"},
        "tier": {"type": "integer", "enum": [1, 2, 3]},
        "decision": {"type": "string", "enum": ["ACCEPT", "REJECT", "ESCALATE"]},
        "root_cause": {
            "type": "string",
            "enum": ["craft_miss", "spec_miss", "tool_ceiling", "unknown"],
        },
        "root_cause_confidence": {"type": "string", "enum": ["low", "medium", "high"]},
        "observed_ceiling": {"type": "string", "minLength": 1},
        "date": {"type": "string", "pattern": r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$"},
        "evidence_pointer": {"type": "string", "minLength": 1},
    },
    "allOf": [
        {
            "if": {
                "properties": {"decision": {"const": "REJECT"}},
                "required": ["decision"],
            },
            "then": {"required": ["root_cause", "root_cause_confidence"]},
            "else": {
                "not": {
                    "anyOf": [
                        {"required": ["root_cause"]},
                        {"required": ["root_cause_confidence"]},
                        {"required": ["observed_ceiling"]},
                    ]
                }
            },
        },
        {
            "if": {
                "properties": {"root_cause": {"const": "tool_ceiling"}},
                "required": ["root_cause"],
            },
            "then": {"required": ["observed_ceiling"]},
        },
    ],
}


def _today() -> date:
    override = os.environ.get("TOOL_DISCOVERY_TODAY")
    if override:
        return date.fromisoformat(override)
    return datetime.now().astimezone().date()


def _read_yaml(path: Path) -> Dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a YAML object")
    return _normalize_dates(data)


def _normalize_dates(value: Any) -> Any:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _normalize_dates(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_normalize_dates(item) for item in value]
    return value


def _validate(data: Dict[str, Any], schema: Dict[str, Any], path: Path) -> None:
    try:
        jsonschema.Draft7Validator(schema).validate(data)
    except jsonschema.ValidationError as exc:
        pointer = "/".join(str(p) for p in exc.absolute_path)
        where = f" at {pointer}" if pointer else ""
        raise ValueError(f"{path} failed schema validation{where}: {exc.message}") from exc


def _catalog_dir(path: Optional[str] = None) -> Path:
    raw = path or os.environ.get("TOOL_DISCOVERY_CATALOG_DIR")
    return Path(raw).resolve() if raw else DEFAULT_CATALOG_DIR


def _vault_root(path: Optional[str] = None) -> Path:
    raw = path or os.environ.get("TOOL_DISCOVERY_VAULT_ROOT")
    return Path(raw).resolve() if raw else DEFAULT_VAULT_ROOT


def _deep_merge(base: Dict[str, Any], overlay: Dict[str, Any]) -> Dict[str, Any]:
    out = copy.deepcopy(base)
    for key, value in overlay.items():
        if key in {"tool_slug", "overlay_metadata", "capability_overrides"}:
            continue
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = copy.deepcopy(value)
    return out


def _apply_capability_overrides(entry: Dict[str, Any], overlay: Dict[str, Any]) -> None:
    overrides = overlay.get("capability_overrides") or []
    if not overrides:
        return
    by_id = {cap["id"]: copy.deepcopy(cap) for cap in entry.get("capabilities", [])}
    for override in overrides:
        cap = copy.deepcopy(override)
        cap.pop("override_reason", None)
        by_id[cap["id"]] = cap
    entry["capabilities"] = list(by_id.values())


def _overlay_dir(vault_root: Path, client_slug: str) -> Path:
    return vault_root / "clients" / _safe_slug(client_slug, label="client_slug") / "tools-catalog-overlay"


def _execution_evidence_dir(vault_root: Path, client_slug: str, project_slug: str) -> Path:
    return (
        vault_root
        / "clients"
        / _safe_slug(client_slug, label="client_slug")
        / "tools-catalog-overlay"
        / "evidence"
        / _safe_slug(project_slug, label="project_slug")
        / "execution"
    )


def _merge_overlay(entry: Dict[str, Any], overlay: Dict[str, Any]) -> Dict[str, Any]:
    merged = _deep_merge(entry, overlay)
    _apply_capability_overrides(merged, overlay)
    merged["overlay_metadata"] = copy.deepcopy(overlay.get("overlay_metadata", {}))
    if "installed_state_by_host" in overlay:
        merged["installed_state_by_host"] = copy.deepcopy(overlay["installed_state_by_host"])
    return merged


def load_catalog(
    catalog_dir: Optional[str] = None,
    client_slug: Optional[str] = None,
    vault_root: Optional[str] = None,
) -> Dict[str, Dict[str, Any]]:
    """Load and validate the canonical catalog plus optional client overlay."""
    catalog_path = _catalog_dir(catalog_dir)
    if not catalog_path.is_dir():
        raise FileNotFoundError(f"catalog directory not found: {catalog_path}")

    entries: Dict[str, Dict[str, Any]] = {}
    for path in sorted(catalog_path.glob("*.yaml")):
        data = _read_yaml(path)
        _validate(data, CATALOG_SCHEMA, path)
        slug = data["tool_slug"]
        if slug in entries:
            raise ValueError(f"duplicate catalog tool_slug: {slug}")
        entries[slug] = data

    if client_slug:
        overlay_path = _overlay_dir(_vault_root(vault_root), client_slug)
        if overlay_path.is_dir():
            for path in sorted(overlay_path.glob("*.yaml")):
                overlay = _read_yaml(path)
                _validate(overlay, OVERLAY_SCHEMA, path)
                slug = overlay["tool_slug"]
                if slug not in entries:
                    raise ValueError(f"overlay references unknown tool_slug {slug}: {path}")
                entries[slug] = _merge_overlay(entries[slug], overlay)
    return entries


def _capability_for(entry: Dict[str, Any], capability: str) -> Optional[Dict[str, Any]]:
    for cap in entry.get("capabilities", []):
        if cap.get("id") == capability:
            return cap
    return None


def _license_pass(license_name: str, license_constraint: str) -> bool:
    lower = (license_name or "").lower()
    if license_constraint == "commercial_ok":
        return True
    if license_constraint == "cc0_only":
        return "cc0" in lower or "public-domain" in lower or "public domain" in lower
    return any(token in lower for token in OPEN_SOURCE_LICENSE_TOKENS)


def _constraint_fit(entry: Dict[str, Any], constraints: Dict[str, Any]) -> Tuple[Dict[str, str], List[str]]:
    tool_constraints = entry.get("constraints", {})
    fit: Dict[str, str] = {}
    excluded: List[str] = []

    requested_os = constraints.get("os") or []
    if requested_os:
        ok = bool(set(requested_os).intersection(tool_constraints.get("os", [])))
        fit["os"] = "pass" if ok else "fail"
        if not ok:
            excluded.append("os")
    else:
        fit["os"] = "n_a"

    requested_arch = constraints.get("arch") or []
    if requested_arch:
        ok = bool(set(requested_arch).intersection(tool_constraints.get("arch", [])))
        fit["arch"] = "pass" if ok else "fail"
        if not ok:
            excluded.append("arch")
    else:
        fit["arch"] = "n_a"

    budget = constraints.get("budget") or {}
    max_total = float(budget.get("max_total_usd", 0))
    will_pay = bool(budget.get("operator_will_pay_out_of_band", False))
    cost = float(tool_constraints.get("acquisition_cost_usd", 0))
    ok = cost <= max_total or will_pay
    fit["budget"] = "pass" if ok else "fail"
    if not ok:
        excluded.append("budget")

    local_requirement = constraints.get("local_runnable", "unconstrained")
    local_ok = bool(tool_constraints.get("local_runnable", False))
    if local_requirement == "required" and not local_ok:
        fit["local_runnable"] = "fail"
        excluded.append("local_runnable")
    else:
        fit["local_runnable"] = "pass" if local_ok else "n_a"

    network = constraints.get("network") or {}
    network_required = bool(tool_constraints.get("network_required", False))
    api_method = entry.get("acquisition", {}).get("install_method") == "api_only"
    if network.get("outbound") == "forbidden" and network_required:
        fit["network"] = "fail"
        excluded.append("network")
    elif api_method and not network.get("api_dependencies_allowed", True):
        fit["network"] = "fail"
        excluded.append("network")
    else:
        fit["network"] = "pass" if network_required or api_method else "n_a"

    license_constraint = constraints.get("license_constraint", "commercial_ok")
    if _license_pass(str(tool_constraints.get("license", "")), license_constraint):
        fit["license_constraint"] = "pass"
    else:
        fit["license_constraint"] = "fail"
        excluded.append("license_constraint")

    creds = constraints.get("credentials") or {}
    credentials_required = bool(tool_constraints.get("credentials_required", False))
    if credentials_required and not creds.get("api_keys_allowed", True):
        fit["credentials"] = "fail"
        excluded.append("credentials")
    else:
        fit["credentials"] = "pass" if credentials_required else "n_a"

    deliverable = constraints.get("deliverable") or {}
    deliverable_type = deliverable.get("type")
    if deliverable_type == "live_runtime" and api_method:
        fit["deliverable"] = "fail"
        if "deliverable" not in excluded:
            excluded.append("deliverable")
    else:
        fit["deliverable"] = "pass"

    browser_runtime = constraints.get("browser_runtime") or {}
    if browser_runtime:
        fit["browser_runtime"] = "pass"
    else:
        fit["browser_runtime"] = "n_a"

    if constraints.get("host_availability"):
        fit["host_availability"] = "pass"
    else:
        fit["host_availability"] = "n_a"

    return fit, sorted(set(excluded))


def _freshness(entry: Dict[str, Any]) -> Dict[str, Any]:
    metadata = entry.get("catalog_metadata", {})
    last_checked = date.fromisoformat(metadata["terms_last_checked"])
    ttl_values = list((metadata.get("ttl_days_by_domain") or {}).values())
    ttl_days = min(int(v) for v in ttl_values) if ttl_values else 90
    expiry = last_checked + timedelta(days=ttl_days)
    grace_expiry = expiry + timedelta(days=30)
    today = _today()
    if today <= expiry:
        status = "fresh"
    elif today <= grace_expiry:
        status = "stale_within_grace"
    else:
        status = "stale"
    return {
        "terms_last_checked": metadata["terms_last_checked"],
        "ttl_status": status,
        "citation_urls": metadata.get("citation_urls", []),
    }


def _installed_state(entry: Dict[str, Any], constraints: Dict[str, Any]) -> Dict[str, Any]:
    states = entry.get("installed_state_by_host") or {}
    hosts = ((constraints.get("host_availability") or {}).get("hosts") or [])
    for host in hosts:
        if host in states:
            return states[host]
    if states:
        first_host = sorted(states)[0]
        return states[first_host]
    return {
        "state": "unknown",
        "detected_version": None,
        "canary_status": "not_run",
        "last_seen_on_host": None,
    }


def _evidence_confidence(entry: Dict[str, Any], cap: Dict[str, Any], freshness: Dict[str, Any], policy: str) -> str:
    if freshness["ttl_status"] != "fresh" and policy == "best_effort":
        return "stale_accepted"
    evidence_count = len(cap.get("bar_fit_evidence") or [])
    citation_count = len(entry.get("catalog_metadata", {}).get("citation_urls") or [])
    if evidence_count >= 2 and citation_count >= 2 and freshness["ttl_status"] == "fresh":
        return "high"
    if evidence_count >= 1:
        return "medium"
    return "low"


def _candidate(entry: Dict[str, Any], cap: Dict[str, Any], constraints: Dict[str, Any], policy: str) -> Dict[str, Any]:
    fit, excluded = _constraint_fit(entry, constraints)
    freshness = _freshness(entry)
    acquisition = entry.get("acquisition", {})
    tool_constraints = entry.get("constraints", {})
    return {
        "tool_slug": entry["tool_slug"],
        "tool_stack_id": entry.get("tool_stack_id"),
        "display_name": entry["display_name"],
        "bar_fitness": cap["bar_fit_default"],
        "bar_fitness_evidence": cap.get("bar_fit_evidence", []),
        "constraint_fit": fit,
        "excluded_by_constraint": excluded,
        "known_ceilings": cap.get("known_ceilings", []),
        "installed_state": _installed_state(entry, constraints),
        "acquisition_summary": {
            "install_method": acquisition.get("install_method"),
            "install_risk": acquisition.get("install_risk"),
            "acquisition_cost_usd": tool_constraints.get("acquisition_cost_usd", 0),
            "recurrence": tool_constraints.get("recurrence", "none"),
            "credentials_needed": acquisition.get("credentials_needed", []),
            "credential_handoff": acquisition.get("credential_handoff", "none"),
            "license": tool_constraints.get("license"),
        },
        "canary_type": acquisition.get("canary_type", "not_required"),
        "evidence_confidence": _evidence_confidence(entry, cap, freshness, policy),
        "catalog_freshness": freshness,
    }


def _sort_key(candidate: Dict[str, Any]) -> Tuple[int, int, int, int, int, str]:
    excluded = candidate.get("excluded_by_constraint") or []
    installed = candidate.get("installed_state", {}).get("state") == "installed"
    canary_passed = candidate.get("installed_state", {}).get("canary_status") == "passed"
    return (
        0 if excluded else 1,
        FIT_RANK.get(candidate.get("bar_fitness"), 0),
        1 if installed and canary_passed else 0,
        CONFIDENCE_RANK.get(candidate.get("evidence_confidence"), 0),
        RISK_RANK.get(candidate.get("acquisition_summary", {}).get("install_risk"), 0),
        candidate.get("tool_slug", ""),
    )


def survey_tools_result(
    capability: str,
    bar: str,
    constraints: Dict[str, Any],
    client_slug: Optional[str] = None,
    freshness_policy: str = "strict",
    catalog_dir: Optional[str] = None,
    vault_root: Optional[str] = None,
) -> Dict[str, Any]:
    """Return ranked tool candidates for a load-bearing capability."""
    _safe_slug(capability, label="capability")
    if freshness_policy not in {"strict", "best_effort"}:
        raise ValueError("freshness_policy must be strict or best_effort")
    entries = load_catalog(catalog_dir=catalog_dir, client_slug=client_slug, vault_root=vault_root)
    candidates: List[Dict[str, Any]] = []
    for entry in entries.values():
        cap = _capability_for(entry, capability)
        if cap:
            candidates.append(_candidate(entry, cap, constraints or {}, freshness_policy))
    candidates.sort(key=_sort_key, reverse=True)
    refresh_required = any(c["catalog_freshness"]["ttl_status"] != "fresh" for c in candidates)
    return {
        "capability": capability,
        "bar": bar,
        "constraints": constraints or {},
        "refresh_required": bool(refresh_required and freshness_policy == "strict"),
        "candidates": candidates,
    }


def get_tool_result(
    tool_slug: str,
    client_slug: Optional[str] = None,
    catalog_dir: Optional[str] = None,
    vault_root: Optional[str] = None,
) -> Dict[str, Any]:
    slug = _safe_slug(tool_slug, label="tool_slug")
    entries = load_catalog(catalog_dir=catalog_dir, client_slug=client_slug, vault_root=vault_root)
    if slug not in entries:
        raise KeyError(f"tool not found: {slug}")
    return entries[slug]


def list_capabilities_result(
    client_slug: Optional[str] = None,
    catalog_dir: Optional[str] = None,
    vault_root: Optional[str] = None,
) -> List[str]:
    entries = load_catalog(catalog_dir=catalog_dir, client_slug=client_slug, vault_root=vault_root)
    capabilities = set()
    for entry in entries.values():
        for cap in entry.get("capabilities", []):
            capabilities.add(cap["id"])
    return sorted(capabilities)


def propose_refresh_result(
    tool_slug: str,
    citation_urls: List[str],
    evidence: str,
    catalog_dir: Optional[str] = None,
) -> Dict[str, Any]:
    current = get_tool_result(tool_slug, catalog_dir=catalog_dir)
    proposed = copy.deepcopy(current)
    proposed["catalog_metadata"]["citation_urls"] = citation_urls
    proposed["catalog_metadata"]["terms_last_checked"] = _today().isoformat()
    proposed["catalog_metadata"]["last_validated"] = _today().isoformat()
    proposed["catalog_metadata"]["catalog_revision"] = int(
        proposed["catalog_metadata"]["catalog_revision"]
    ) + 1
    return {
        "tool_slug": tool_slug,
        "writes_performed": False,
        "evidence": evidence,
        "diff": {
            "catalog_metadata.citation_urls": {
                "from": current["catalog_metadata"].get("citation_urls", []),
                "to": citation_urls,
            },
            "catalog_metadata.terms_last_checked": {
                "from": current["catalog_metadata"]["terms_last_checked"],
                "to": proposed["catalog_metadata"]["terms_last_checked"],
            },
            "catalog_metadata.catalog_revision": {
                "from": current["catalog_metadata"]["catalog_revision"],
                "to": proposed["catalog_metadata"]["catalog_revision"],
            },
        },
        "proposed_entry": proposed,
    }


def record_operator_curation_result(
    tool_slug: str,
    client_slug: str,
    fields: Dict[str, Any],
    vault_root: Optional[str] = None,
    catalog_dir: Optional[str] = None,
) -> Dict[str, Any]:
    slug = _safe_slug(tool_slug, label="tool_slug")
    client = _safe_slug(client_slug, label="client_slug")
    canonical = get_tool_result(slug, catalog_dir=catalog_dir)
    out_dir = _overlay_dir(_vault_root(vault_root), client)
    out_dir.mkdir(parents=True, exist_ok=True)
    overlay = copy.deepcopy(fields or {})
    overlay["tool_slug"] = slug
    metadata = overlay.get("overlay_metadata") or {}
    metadata.setdefault("source", "operator-curated")
    metadata.setdefault("curator", overlay.pop("curator", "operator"))
    metadata.setdefault("canonical_revision_base", canonical["catalog_metadata"]["catalog_revision"])
    metadata.setdefault("conflict_reason", overlay.pop("conflict_reason", "operator curation"))
    metadata.setdefault("review_after", (_today() + timedelta(days=90)).isoformat())
    metadata.setdefault("override_durability", "durable")
    metadata.setdefault("created_at", datetime.now().astimezone().isoformat(timespec="minutes"))
    overlay["overlay_metadata"] = metadata
    _validate(overlay, OVERLAY_SCHEMA, out_dir / f"{slug}.yaml")
    path = out_dir / f"{slug}.yaml"
    path.write_text(yaml.safe_dump(overlay, sort_keys=False), encoding="utf-8")
    return {
        "tool_slug": slug,
        "client_slug": client,
        "overlay_path": str(path),
        "source": overlay["overlay_metadata"]["source"],
        "promotion_proposal": {
            "tool_slug": slug,
            "canonical_revision_base": metadata["canonical_revision_base"],
            "status": "operator-review-required",
        },
    }


def record_planning_evidence_result(
    tool_slug: str,
    client_slug: str,
    project_slug: str,
    capability: str,
    evidence: Dict[str, Any],
    vault_root: Optional[str] = None,
) -> Dict[str, Any]:
    slug = _safe_slug(tool_slug, label="tool_slug")
    client = _safe_slug(client_slug, label="client_slug")
    project = _safe_slug(project_slug, label="project_slug")
    cap = _safe_slug(capability, label="capability")
    out_dir = _vault_root(vault_root) / "clients" / client / "tools-catalog-overlay" / "evidence" / project
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "tool_slug": slug,
        "client_slug": client,
        "project_slug": project,
        "capability": cap,
        "recorded_at": datetime.now().astimezone().isoformat(timespec="minutes"),
        "evidence": evidence or {},
    }
    path = out_dir / f"{slug}-{cap}.yaml"
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    return {"tool_slug": slug, "evidence_path": str(path), "writes_performed": True}


def _execution_client_slug(evidence: Dict[str, Any]) -> str:
    client = evidence.get("client_slug") or os.environ.get("TOOL_DISCOVERY_CLIENT_SLUG") or "personal"
    return _safe_slug(str(client), label="client_slug")


def record_execution_evidence_result(
    tool_slug: str,
    tool_stack_id: str,
    project_slug: str,
    capability: str,
    evidence: Dict[str, Any],
    vault_root: Optional[str] = None,
) -> Dict[str, Any]:
    slug = _safe_slug(tool_slug, label="tool_slug")
    if not tool_stack_id or not isinstance(tool_stack_id, str):
        raise ValueError("tool_stack_id must be a non-empty string")
    project = _safe_slug(project_slug, label="project_slug")
    cap = _safe_slug(capability, label="capability")
    payload_evidence = copy.deepcopy(evidence or {})
    _validate(payload_evidence, EXECUTION_EVIDENCE_SCHEMA, Path("<execution_evidence>"))
    client = _execution_client_slug(payload_evidence)
    tier = int(payload_evidence["tier"])
    decision = str(payload_evidence["decision"]).upper()
    evidence_date = payload_evidence["date"]
    out_dir = _execution_evidence_dir(_vault_root(vault_root), client, project)
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "tool_slug": slug,
        "tool_stack_id": tool_stack_id,
        "client_slug": client,
        "project_slug": project,
        "capability": cap,
        "recorded_at": datetime.now().astimezone().isoformat(timespec="minutes"),
        "evidence": payload_evidence,
    }
    path = out_dir / f"{slug}-{tier}-{decision}-{evidence_date}.yaml"
    _validate(payload["evidence"], EXECUTION_EVIDENCE_SCHEMA, path)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    return {
        "tool_slug": slug,
        "tool_stack_id": tool_stack_id,
        "project_slug": project,
        "client_slug": client,
        "evidence_path": str(path),
        "writes_performed": True,
        "promotion_required": True,
        "promotion_scope": "operator-gated-overlay-to-canonical",
    }


@mcp.tool()
def survey_tools(
    capability: str,
    bar: str,
    constraints: Dict[str, Any],
    client_slug: Optional[str] = None,
    freshness_policy: str = "strict",
) -> str:
    """Survey known tools for a capability, bar, and structured constraint envelope."""
    try:
        return json.dumps(
            survey_tools_result(capability, bar, constraints, client_slug, freshness_policy),
            indent=2,
        )
    except Exception as exc:
        return json.dumps({"ok": False, "error": str(exc)}, indent=2)


@mcp.tool()
def get_tool(tool_slug: str, client_slug: Optional[str] = None) -> str:
    """Return a schema-validated catalog entry, merged with client overlay if provided."""
    try:
        return json.dumps(get_tool_result(tool_slug, client_slug), indent=2)
    except Exception as exc:
        return json.dumps({"ok": False, "error": str(exc)}, indent=2)


@mcp.tool()
def list_capabilities(client_slug: Optional[str] = None) -> str:
    """List capability IDs present in the Tool Discovery catalog."""
    try:
        return json.dumps({"capabilities": list_capabilities_result(client_slug)}, indent=2)
    except Exception as exc:
        return json.dumps({"ok": False, "error": str(exc)}, indent=2)


@mcp.tool()
def propose_refresh(tool_slug: str, citation_urls: List[str], evidence: str) -> str:
    """Return a refresh proposal diff without writing the canonical catalog."""
    try:
        return json.dumps(propose_refresh_result(tool_slug, citation_urls, evidence), indent=2)
    except Exception as exc:
        return json.dumps({"ok": False, "error": str(exc)}, indent=2)


@mcp.tool()
def record_operator_curation(tool_slug: str, client_slug: str, fields: Dict[str, Any]) -> str:
    """Write a per-client operator-curated overlay entry."""
    try:
        return json.dumps(record_operator_curation_result(tool_slug, client_slug, fields), indent=2)
    except Exception as exc:
        return json.dumps({"ok": False, "error": str(exc)}, indent=2)


@mcp.tool()
def record_planning_evidence(
    tool_slug: str,
    client_slug: str,
    project_slug: str,
    capability: str,
    evidence: Dict[str, Any],
) -> str:
    """Write planning-time fitness evidence into the client overlay evidence area."""
    try:
        return json.dumps(
            record_planning_evidence_result(tool_slug, client_slug, project_slug, capability, evidence),
            indent=2,
        )
    except Exception as exc:
        return json.dumps({"ok": False, "error": str(exc)}, indent=2)


@mcp.tool()
def record_execution_evidence(
    tool_slug: str,
    tool_stack_id: str,
    project_slug: str,
    capability: str,
    evidence: Dict[str, Any],
) -> str:
    """Write execution-time tool-fit evidence into overlay scope only."""
    try:
        return json.dumps(
            record_execution_evidence_result(
                tool_slug,
                tool_stack_id,
                project_slug,
                capability,
                evidence,
            ),
            indent=2,
        )
    except Exception as exc:
        return json.dumps({"ok": False, "error": str(exc)}, indent=2)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Tool Discovery MCP server")
    parser.add_argument("--check", action="store_true", help="Validate catalog and exit.")
    args = parser.parse_args(argv)
    if args.check:
        entries = load_catalog()
        print(json.dumps({"ok": True, "catalog_entries": len(entries)}, indent=2))
        return 0
    mcp.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
