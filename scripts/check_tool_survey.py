#!/usr/bin/env python3
"""
Tool survey Plan QA sub-check.

Validates Stage 1 Step 0.7 tool-survey snapshots, OAI-PLAN responses, and
disposition checkpoint hygiene. Stage 2 also validates OAI-TOOL responses,
tool-stack mechanical identity, and Tool-Fit Retrospective trigger behavior.
Exits nonzero on mechanical blockers and emits soft warnings for stale accepted
evidence and unreasoned overrides.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import jsonschema
import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
SCHEMA_DIR = REPO_ROOT / "schemas"

CAPABILITY_SECTION_RE = re.compile(
    r"^##\s+Load-Bearing Capabilities\s*$([\s\S]*?)(?=^##\s+|\Z)",
    re.IGNORECASE | re.MULTILINE,
)
TOOL_SURVEY_PATH_RE = re.compile(
    r"(?:tool_survey_snapshot|Tool survey snapshot)\s*[:|-]\s*`?([^`\n]+)`?",
    re.IGNORECASE,
)
AD_RE = re.compile(r"\bAD-[0-9]{3,}\b")
ARCH_SECTION_RE = re.compile(
    r"^##\s+Architecture Decisions\s*$([\s\S]*?)(?=^##\s+|\Z)",
    re.IGNORECASE | re.MULTILINE,
)
TOOL_FIT_RIGOR_RE = re.compile(
    r"\b(?:tool_fit_rigor_tier|tool_fit_rigor|tool_lifecycle_rigor)\s*:\s*(default|high|max)\b",
    re.IGNORECASE,
)


def now() -> str:
    return datetime.now().astimezone().strftime("%Y-%m-%dT%H:%M:%S")


def load_schema(name: str) -> dict[str, Any]:
    return json.loads((SCHEMA_DIR / name).read_text(encoding="utf-8"))


TOOL_SURVEY_SCHEMA = load_schema("tool-survey.schema.json")
OAI_PLAN_SCHEMA = load_schema("oai-plan-response.schema.json")
OAI_TOOL_SCHEMA = load_schema("oai-tool-response.schema.json")
OAI_SPEND_SCHEMA = load_schema("oai-spend-response.schema.json")
ACQUISITION_MANIFEST_SCHEMA = load_schema("acquisition-manifest.schema.json")
SPENDING_RESERVATION_SCHEMA = load_schema("spending-reservation.schema.json")
CHECKPOINT_SCHEMA = load_schema("disposition-checkpoint.schema.json")
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


def check_item(name: str, ok: bool, details: str) -> dict[str, Any]:
    return {"name": name, "ok": ok, "details": details}


def _load_yaml_or_json(path: Path) -> Any:
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".json":
        return json.loads(text)
    if path.suffix in {".yaml", ".yml"}:
        return _normalize_dates(yaml.safe_load(text))
    blocks = re.findall(r"```(?:yaml|yml|json)\s*\n([\s\S]*?)\n```", text, re.IGNORECASE)
    for block in blocks:
        data = json.loads(block) if block.lstrip().startswith("{") else yaml.safe_load(block)
        if isinstance(data, dict):
            return _normalize_dates(data)
    loaded = yaml.safe_load(text)
    return _normalize_dates(loaded)


def _normalize_dates(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _normalize_dates(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_normalize_dates(item) for item in value]
    return value


def load_tool_survey(path: Path) -> dict[str, Any]:
    data = _load_yaml_or_json(path)
    if isinstance(data, dict) and "tool_survey" in data:
        data = data["tool_survey"]
    if not isinstance(data, dict):
        raise ValueError(f"tool survey at {path} must be a structured object")
    jsonschema.Draft7Validator(TOOL_SURVEY_SCHEMA).validate(data)
    return data


def load_checkpoint(path: Path) -> dict[str, Any]:
    data = _load_yaml_or_json(path)
    if isinstance(data, dict) and "checkpoint" in data:
        data = data["checkpoint"]
    if not isinstance(data, dict):
        raise ValueError(f"checkpoint at {path} must be a structured object")
    jsonschema.Draft7Validator(CHECKPOINT_SCHEMA).validate(data)
    return data


def load_oai_tool(path: Path) -> dict[str, Any]:
    data = _load_yaml_or_json(path)
    if isinstance(data, dict) and "oai_tool" in data:
        data = data["oai_tool"]
    if not isinstance(data, dict):
        raise ValueError(f"OAI-TOOL response at {path} must be a structured object")
    jsonschema.Draft7Validator(OAI_TOOL_SCHEMA).validate(data)
    return data


def load_oai_spend(path: Path) -> dict[str, Any]:
    data = _load_yaml_or_json(path)
    if isinstance(data, dict) and "oai_spend" in data:
        data = data["oai_spend"]
    if not isinstance(data, dict):
        raise ValueError(f"OAI-SPEND response at {path} must be a structured object")
    jsonschema.Draft7Validator(OAI_SPEND_SCHEMA).validate(data)
    return data


def load_acquisition_manifest(path: Path) -> dict[str, Any]:
    data = _load_yaml_or_json(path)
    if isinstance(data, dict) and "acquisition_manifest" in data:
        data = data["acquisition_manifest"]
    if not isinstance(data, dict):
        raise ValueError(f"acquisition manifest at {path} must be a structured object")
    jsonschema.Draft7Validator(ACQUISITION_MANIFEST_SCHEMA).validate(data)
    return data


def load_spending_record(path: Path) -> dict[str, Any]:
    data = _load_yaml_or_json(path)
    if isinstance(data, dict) and "spending_record" in data:
        data = data["spending_record"]
    if not isinstance(data, dict):
        raise ValueError(f"spending record at {path} must be a structured object")
    jsonschema.Draft7Validator(SPENDING_RESERVATION_SCHEMA).validate(data)
    return data


def load_runtime_check(path: Path) -> dict[str, Any]:
    data = _load_yaml_or_json(path)
    if isinstance(data, dict) and "runtime_check" in data:
        data = data["runtime_check"]
    if not isinstance(data, dict):
        raise ValueError(f"runtime check at {path} must be a structured object")
    return data


def load_ticket_frontmatter(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    loaded = yaml.safe_load(parts[1]) or {}
    if not isinstance(loaded, dict):
        raise ValueError(f"ticket frontmatter at {path} must be a mapping")
    return loaded


def extract_load_bearing_capabilities(plan_text: str) -> set[str]:
    match = CAPABILITY_SECTION_RE.search(plan_text)
    if not match:
        return set()
    section = match.group(1)
    capabilities: set[str] = set()
    for line in section.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("|---") or "Capability" in stripped:
            continue
        if stripped.startswith("|"):
            cells = [cell.strip(" `") for cell in stripped.strip("|").split("|")]
            if cells and re.match(r"^[a-z0-9][a-z0-9_-]*$", cells[0]):
                capabilities.add(cells[0])
        else:
            for found in re.findall(r"`([a-z0-9][a-z0-9_-]*)`", stripped):
                capabilities.add(found)
    return capabilities


def find_survey_path(plan_text: str, plan_path: Path) -> Path | None:
    match = TOOL_SURVEY_PATH_RE.search(plan_text)
    if not match:
        return None
    raw = match.group(1).strip()
    candidate = Path(raw)
    if not candidate.is_absolute():
        candidate = (plan_path.parent / candidate).resolve()
    return candidate


def _tool_stack_refs(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _data_tool_stack_refs(data: dict[str, Any]) -> list[str]:
    refs = _tool_stack_refs(data.get("tool_stack_refs"))
    if refs:
        return refs
    refs = _tool_stack_refs(data.get("tool_stack_id"))
    if refs:
        return refs
    bottleneck = data.get("tool_stack_bottleneck")
    if isinstance(bottleneck, dict):
        refs = _tool_stack_refs(bottleneck.get("tool_stack_refs")) or _tool_stack_refs(
            bottleneck.get("tool_stack_id")
        )
    return refs


def _has_tool_stack_refs_text(text: str) -> bool:
    if re.search(r"tool_stack_refs\s*:\s*\[[^\]]*\S[^\]]*\]", text):
        return True
    return bool(re.search(r"tool_stack_refs\s*:\s*\n(?:\s*-\s*\S+)", text))


def _architecture_decision_blocks(plan_text: str) -> list[tuple[str, str]]:
    match = ARCH_SECTION_RE.search(plan_text)
    if not match:
        return []
    blocks: list[tuple[str, str]] = []
    current_id: str | None = None
    current_lines: list[str] = []
    for line in match.group(1).splitlines():
        ids = AD_RE.findall(line)
        if ids:
            if current_id:
                blocks.append((current_id, "\n".join(current_lines)))
            current_id = ids[0]
            current_lines = [line]
        elif current_id:
            current_lines.append(line)
    if current_id:
        blocks.append((current_id, "\n".join(current_lines)))
    return blocks


def _ad_binds_tool(block: str) -> bool:
    cleaned = re.sub(r"tool_stack_refs\s*:\s*(?:\[[^\]]*\]|\n(?:\s*-\s*\S+)+)", "", block)
    return bool(
        re.search(
            r"\b(tool_binding|selected_tool|tool_slug|tool_stack_id)\s*[:=]",
            cleaned,
            re.IGNORECASE,
        )
        or re.search(r"\b(tool|stack)\s*[:=]\s*[a-z0-9][a-z0-9_-]+", cleaned, re.IGNORECASE)
    )


def _validate_ad_tool_stack_refs(plan_text: str) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    for ad_id, block in _architecture_decision_blocks(plan_text):
        if not _ad_binds_tool(block):
            continue
        checks.append(
            check_item(
                f"{ad_id}_tool_stack_refs",
                _has_tool_stack_refs_text(block),
                f"{ad_id} tool-binding decision carries tool_stack_refs."
                if _has_tool_stack_refs_text(block)
                else f"{ad_id} binds a tool but is missing non-empty tool_stack_refs.",
            )
        )
    return checks


def _ticket_depends_on_tool_stack(frontmatter: dict[str, Any]) -> bool:
    if frontmatter.get("depends_on_tool_stack") is True or frontmatter.get("tool_dependency") is True:
        return True
    if frontmatter.get("tool_slug") or frontmatter.get("tool_stack_id"):
        return True
    tags = frontmatter.get("tags") or []
    if isinstance(tags, str):
        tags = [tags]
    return any(str(tag) in {"tool-stack", "tool-dependent"} for tag in tags)


def _runtime_check_exercises_tool(data: dict[str, Any]) -> bool:
    if data.get("tool_slug") or data.get("tool_stack_id") or data.get("tools_exercised"):
        return True
    return bool(data.get("capability") and data.get("tier"))


def _validate_ticket_tool_stack_refs(paths: list[Path]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    for path in paths:
        try:
            frontmatter = load_ticket_frontmatter(path)
            if not _ticket_depends_on_tool_stack(frontmatter):
                continue
            refs = _tool_stack_refs(frontmatter.get("tool_stack_refs"))
            checks.append(
                check_item(
                    f"{path.name}_tool_stack_refs",
                    bool(refs),
                    f"{path.name} carries tool_stack_refs."
                    if refs
                    else f"{path.name} depends on a tool stack but is missing non-empty tool_stack_refs.",
                )
            )
        except (ValueError, yaml.YAMLError) as exc:
            checks.append(check_item(f"{path.name}_ticket_frontmatter", False, f"Ticket invalid: {exc}"))
    return checks


def _validate_runtime_check_tool_stack_refs(paths: list[Path]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    checks: list[dict[str, Any]] = []
    records: list[dict[str, Any]] = []
    for path in paths:
        try:
            data = load_runtime_check(path)
            records.append({"path": path, "data": data})
            if not _runtime_check_exercises_tool(data):
                continue
            refs = _data_tool_stack_refs(data)
            checks.append(
                check_item(
                    f"{path.name}_tool_stack_refs",
                    bool(refs),
                    f"{path.name} carries tool_stack_refs."
                    if refs
                    else f"{path.name} exercises a tool stack but is missing non-empty tool_stack_refs.",
                )
            )
        except (ValueError, yaml.YAMLError, json.JSONDecodeError) as exc:
            checks.append(check_item(f"{path.name}_runtime_check", False, f"Runtime check invalid: {exc}"))
    return checks, records


def _validate_oai_plan(item: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    checks: list[dict[str, Any]] = []
    warnings: list[str] = []
    try:
        jsonschema.Draft7Validator(OAI_PLAN_SCHEMA).validate(item)
        checks.append(check_item(f"{item.get('oai_id', 'OAI-PLAN')}_schema", True, "OAI-PLAN response schema-valid."))
    except jsonschema.ValidationError as exc:
        checks.append(check_item("oai_plan_schema", False, f"OAI-PLAN schema violation: {exc.message}"))
        return checks, warnings

    operator_decision = item["operator_decision"]
    oai_id = item["oai_id"]
    resolved = operator_decision.get("decision_state") == "resolved"
    ad_binding = operator_decision.get("ad_binding")
    checks.append(
        check_item(
            f"{oai_id}_resolved",
            resolved and bool(ad_binding),
            f"{oai_id} decision_state resolved with {ad_binding}."
            if resolved and ad_binding
            else f"{oai_id} must have decision_state: resolved and ad_binding: AD-NNN.",
        )
    )

    recommended = (item.get("recommended_default") or {}).get("label")
    decision = operator_decision.get("decision")
    decision_label = {"chose_a": "a", "chose_b": "b", "chose_c": "c"}.get(decision)
    reasoning = (operator_decision.get("decision_reasoning") or "").strip()
    if recommended in {"a", "b", "c"} and decision_label and decision_label != recommended and not reasoning:
        warnings.append(f"{oai_id} overrides recommended default {recommended} without decision_reasoning.")
    return checks, warnings


def _validate_oai_tool(item: dict[str, Any], plan_text: str = "") -> tuple[list[dict[str, Any]], list[str]]:
    checks: list[dict[str, Any]] = []
    warnings: list[str] = []
    try:
        jsonschema.Draft7Validator(OAI_TOOL_SCHEMA).validate(item)
        checks.append(check_item(f"{item.get('oai_id', 'OAI-TOOL')}_schema", True, "OAI-TOOL response schema-valid."))
    except jsonschema.ValidationError as exc:
        checks.append(check_item("oai_tool_schema", False, f"OAI-TOOL schema violation: {exc.message}"))
        return checks, warnings

    operator_decision = item["operator_decision"]
    oai_id = item["oai_id"]
    resolved = operator_decision.get("decision_state") == "resolved"
    ad_binding = operator_decision.get("ad_binding")
    checks.append(
        check_item(
            f"{oai_id}_resolved",
            resolved and bool(ad_binding),
            f"{oai_id} decision_state resolved with {ad_binding}."
            if resolved and ad_binding
            else f"{oai_id} must have decision_state: resolved and ad_binding: AD-NNN.",
        )
    )
    if plan_text and ad_binding:
        checks.append(
            check_item(
                f"{oai_id}_ad_binding_exists",
                ad_binding in set(AD_RE.findall(plan_text)),
                f"{ad_binding} exists in the plan."
                if ad_binding in set(AD_RE.findall(plan_text))
                else f"{ad_binding} referenced by OAI-TOOL is missing from the plan.",
            )
        )
    recommended = (item.get("recommended_default") or {}).get("label")
    decision = operator_decision.get("decision")
    decision_label = {"chose_a": "a", "chose_b": "b", "chose_c": "c"}.get(decision)
    reasoning = (operator_decision.get("decision_reasoning") or "").strip()
    if recommended in {"a", "b", "c"} and decision_label and decision_label != recommended and not reasoning:
        warnings.append(f"{oai_id} overrides recommended default {recommended} without decision_reasoning.")
    return checks, warnings


def _validate_oai_spend(item: dict[str, Any], plan_text: str = "") -> tuple[list[dict[str, Any]], list[str]]:
    checks: list[dict[str, Any]] = []
    warnings: list[str] = []
    try:
        jsonschema.Draft7Validator(OAI_SPEND_SCHEMA).validate(item)
        checks.append(check_item(f"{item.get('oai_id', 'OAI-SPEND')}_schema", True, "OAI-SPEND response schema-valid."))
    except jsonschema.ValidationError as exc:
        checks.append(check_item("oai_spend_schema", False, f"OAI-SPEND schema violation: {exc.message}"))
        return checks, warnings

    operator_decision = item["operator_decision"]
    oai_id = item["oai_id"]
    resolved = operator_decision.get("decision_state") == "resolved"
    ad_binding = operator_decision.get("ad_binding")
    checks.append(
        check_item(
            f"{oai_id}_resolved",
            resolved and bool(ad_binding),
            f"{oai_id} decision_state resolved with {ad_binding}."
            if resolved and ad_binding
            else f"{oai_id} must have decision_state: resolved and ad_binding: AD-NNN.",
        )
    )
    if plan_text and ad_binding:
        checks.append(
            check_item(
                f"{oai_id}_ad_binding_exists",
                ad_binding in set(AD_RE.findall(plan_text)),
                f"{ad_binding} exists in the plan."
                if ad_binding in set(AD_RE.findall(plan_text))
                else f"{ad_binding} referenced by OAI-SPEND is missing from the plan.",
            )
        )
    return checks, warnings


def _looks_like_env_var(value: str) -> bool:
    return value.isupper() and value.replace("_", "").replace("0", "").isalnum() and len(value) <= 80


def _manifest_secret_paths(value: Any, *, key: str = "", path: str = "$") -> list[str]:
    safe_keys = {"sha256", "checksum", "signature", "signature_url", "source_url", "authorization_id", "reservation_id"}
    if isinstance(value, dict):
        findings: list[str] = []
        for child_key, child_value in value.items():
            findings.extend(_manifest_secret_paths(child_value, key=str(child_key), path=f"{path}.{child_key}"))
        return findings
    if isinstance(value, list):
        findings = []
        for index, item in enumerate(value):
            findings.extend(_manifest_secret_paths(item, key=key, path=f"{path}[{index}]"))
        return findings
    if not isinstance(value, str):
        return []
    lower_key = key.lower()
    if key in safe_keys or "sha256" in lower_key or "checksum" in lower_key or "source_url" in lower_key:
        return []
    if _looks_like_env_var(value) or _looks_like_env_var(key):
        return []
    if any(value.startswith(prefix) for prefix in SECRET_VALUE_PREFIXES):
        return [path]
    if any(token in lower_key for token in ("secret", "token", "api_key", "apikey", "password", "license_key")) and len(value) > 12:
        return [path]
    return []


def _validate_acquisition_manifest_policy(item: dict[str, Any]) -> list[dict[str, Any]]:
    manifest_id = item.get("manifest_id", "manifest")
    checks: list[dict[str, Any]] = []
    secret_paths = _manifest_secret_paths(item)
    checks.append(
        check_item(
            f"{manifest_id}_no_literal_secrets",
            not secret_paths,
            "Acquisition manifest contains no literal secrets."
            if not secret_paths
            else f"Acquisition manifest contains literal secret-looking values at: {', '.join(secret_paths)}",
        )
    )
    touched = [str(path) for path in item.get("files_to_touch") or []]
    for step in item.get("planned_steps") or []:
        touched.extend(str(path) for path in step.get("files_to_touch") or [])
    direct_mcp = any(Path(path).name == ".mcp.json" or path.endswith("/.mcp.json") for path in touched)
    checks.append(
        check_item(
            f"{manifest_id}_no_direct_mcp_registry_mutation",
            not direct_mcp,
            "Acquire-Tool writes registration proposals only."
            if not direct_mcp
            else "Acquire-Tool manifest attempts to touch .mcp.json directly.",
        )
    )
    global_without_approval = [
        step.get("step_id")
        for step in item.get("planned_steps") or []
        if step.get("global_install") and not ((step.get("global_install_approval") or {}).get("approved"))
    ]
    checks.append(
        check_item(
            f"{manifest_id}_global_install_approval",
            not global_without_approval,
            "No unapproved global install steps."
            if not global_without_approval
            else f"Global install steps lack explicit approval: {', '.join(str(step) for step in global_without_approval)}",
        )
    )
    preflight = ((item.get("execution") or {}).get("preflight") or {})
    if "os_supported" in preflight:
        checks.append(
            check_item(
                f"{manifest_id}_os_supported",
                preflight.get("os_supported") is True,
                "Manifest pre-flight confirms host OS is supported."
                if preflight.get("os_supported") is True
                else "Manifest pre-flight reports unsupported host OS; acquisition must fail before install.",
            )
        )
    return checks


def _authorization_id_from_item(item: dict[str, Any]) -> str | None:
    decision = item.get("operator_decision") or {}
    authorization = decision.get("decision_authorization") or {}
    auth_id = authorization.get("authorization_id")
    return str(auth_id) if auth_id else None


def _tier_number(value: Any) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        stripped = value.strip().upper()
        if stripped.startswith("T") and stripped[1:].isdigit():
            return int(stripped[1:])
        if stripped.isdigit():
            return int(stripped)
    return None


def _event_from_checkpoint(path: Path, data: dict[str, Any]) -> dict[str, Any] | None:
    tier = _tier_number(data.get("Tier selected") or data.get("tier"))
    if tier != 3:
        return None
    decision = str(data.get("Decision") or data.get("decision") or "").upper()
    if decision not in {"REJECT", "REVISE"}:
        return None
    return {
        "source": str(path),
        "ticket_id": data.get("ticket_id"),
        "tier": tier,
        "decision": decision,
        "root_cause": data.get("root_cause"),
        "root_cause_confidence": data.get("root_cause_confidence"),
        "tool_stack_refs": _data_tool_stack_refs(data),
        "evidence_pointer": data.get("execution_evidence_pointer") or data.get("evidence_pointer"),
        "tc_ratchet_id": data.get("tc_ratchet_id"),
    }


def _event_from_runtime_check(path: Path, data: dict[str, Any]) -> dict[str, Any] | None:
    tier = _tier_number(data.get("tier") or data.get("Tier selected"))
    if tier != 3:
        return None
    decision = str(data.get("decision") or data.get("Decision") or "").upper()
    if decision not in {"REJECT", "REVISE", "ACCEPT", "ESCALATE"}:
        return None
    return {
        "source": str(path),
        "ticket_id": data.get("ticket_id"),
        "tier": tier,
        "decision": decision,
        "root_cause": data.get("root_cause"),
        "root_cause_confidence": data.get("root_cause_confidence"),
        "tool_stack_refs": _data_tool_stack_refs(data),
        "evidence_pointer": data.get("execution_evidence_pointer") or data.get("evidence_pointer"),
        "tc_ratchet_id": data.get("tc_ratchet_id"),
    }


def _tool_fit_rigor_tier(plan_text: str) -> str:
    match = TOOL_FIT_RIGOR_RE.search(plan_text)
    return match.group(1).lower() if match else "default"


def _retrospective_triggers(events: list[dict[str, Any]], rigor_tier: str) -> list[str]:
    reject_threshold = 1 if rigor_tier == "high" else 2
    revise_threshold = 2 if rigor_tier == "high" else 3
    by_stack: dict[str, list[dict[str, Any]]] = {}
    for event in events:
        for ref in event.get("tool_stack_refs") or []:
            by_stack.setdefault(ref, []).append(event)

    triggers: list[str] = []
    for stack, stack_events in by_stack.items():
        rejects = [event for event in stack_events if event["decision"] == "REJECT"]
        revises = [event for event in stack_events if event["decision"] == "REVISE"]
        if any(
            event.get("root_cause") == "tool_ceiling"
            and event.get("root_cause_confidence") == "high"
            for event in rejects
        ):
            triggers.append(f"{stack}: tool_ceiling_high_confidence")
            continue
        counted_rejects = rejects
        if rigor_tier == "max":
            counted_rejects = [
                event for event in rejects if event.get("root_cause_confidence") == "high"
            ]
        if len(counted_rejects) >= reject_threshold:
            triggers.append(f"{stack}: same_stack_rejects")
            continue
        if len(revises) >= revise_threshold:
            triggers.append(f"{stack}: same_stack_revises")
    return triggers


def _validate_tool_fit_trigger(
    events: list[dict[str, Any]],
    oai_tools: list[dict[str, Any]],
    plan_text: str,
) -> list[dict[str, Any]]:
    if not events and not oai_tools:
        return []
    rigor_tier = _tool_fit_rigor_tier(plan_text)
    triggers = _retrospective_triggers(events, rigor_tier)
    checks = [
        check_item(
            "tool_fit_retrospective_trigger",
            bool(oai_tools) if triggers else not bool(oai_tools),
            f"Triggered OAI-TOOL for {', '.join(triggers)}."
            if triggers and oai_tools
            else (
                f"Tool-Fit Retrospective should have fired for {', '.join(triggers)} but no OAI-TOOL was recorded."
                if triggers
                else "No same-stack Tool-Fit Retrospective trigger matched."
                if not oai_tools
                else "OAI-TOOL recorded even though no Tool-Fit Retrospective trigger matched."
            ),
        )
    ]
    pointers = [event.get("evidence_pointer") for event in events if event.get("evidence_pointer")]
    if pointers:
        checks.append(
            check_item(
                "execution_evidence_no_duplicates",
                len(pointers) == len(set(pointers)),
                "Execution evidence pointers are unique."
                if len(pointers) == len(set(pointers))
                else "Duplicate execution evidence pointers found for Tool-Fit Retrospective events.",
            )
        )
    return checks


def _survey_candidates(survey: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for entry in survey.get("surveys", []):
        out.extend(entry.get("candidates", []))
    return out


def _validate_canary_blocks(survey: dict[str, Any], attempted_ticket: str | None = None) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    for item in survey.get("oai_plan_responses", []):
        decision = item.get("operator_decision", {})
        canary = decision.get("tool_presence_canary", {})
        if not canary.get("required"):
            continue
        status = canary.get("canary_status")
        blocked = canary.get("blocked_tickets") or []
        if attempted_ticket and attempted_ticket in blocked and status in {"not_run", "failed"}:
            checks.append(
                check_item(
                    f"{item.get('oai_id', 'OAI-PLAN')}_canary_blocks_ticket",
                    False,
                    f"{attempted_ticket} is blocked by tool_presence_canary while canary_status is {status}.",
                )
            )
        else:
            checks.append(
                check_item(
                    f"{item.get('oai_id', 'OAI-PLAN')}_canary_block_present",
                    True,
                    f"tool_presence_canary recorded with status {status}.",
                )
            )
    return checks


def validate_tool_survey(
    plan_path: Path | None = None,
    survey_path: Path | None = None,
    checkpoint_paths: list[Path] | None = None,
    oai_tool_paths: list[Path] | None = None,
    oai_spend_paths: list[Path] | None = None,
    acquisition_manifest_paths: list[Path] | None = None,
    spending_record_paths: list[Path] | None = None,
    ticket_paths: list[Path] | None = None,
    runtime_check_paths: list[Path] | None = None,
    attempted_ticket: str | None = None,
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    warnings: list[str] = []
    plan_text = plan_path.read_text(encoding="utf-8") if plan_path else ""
    declared_capabilities = extract_load_bearing_capabilities(plan_text) if plan_text else set()

    if survey_path is None and plan_path is not None:
        survey_path = find_survey_path(plan_text, plan_path)

    survey: dict[str, Any] | None = None
    if survey_path is None:
        ok = not declared_capabilities
        checks.append(
            check_item(
                "tool_survey_snapshot_present",
                ok,
                "No load-bearing capabilities declared; no tool survey required."
                if ok
                else "Load-bearing capabilities declared but no tool_survey_snapshot path found.",
            )
        )
    elif not survey_path.is_file():
        checks.append(
            check_item("tool_survey_snapshot_present", False, f"Tool survey snapshot not found: {survey_path}")
        )
    else:
        try:
            survey = load_tool_survey(survey_path)
            checks.append(check_item("tool_survey_schema", True, f"Tool survey schema-valid: {survey_path}"))
        except (ValueError, jsonschema.ValidationError, yaml.YAMLError, json.JSONDecodeError) as exc:
            checks.append(check_item("tool_survey_schema", False, f"Tool survey invalid at {survey_path}: {exc}"))

    if survey is not None:
        survey_capabilities = {item["id"] for item in survey.get("load_bearing_capabilities", [])}
        if not declared_capabilities:
            declared_capabilities = survey_capabilities
        missing = sorted(declared_capabilities - survey_capabilities)
        checks.append(
            check_item(
                "load_bearing_capabilities_surveyed",
                not missing,
                "Every declared load-bearing capability has a tool survey entry."
                if not missing
                else f"Missing tool survey entries for: {', '.join(missing)}",
            )
        )

        missing_survey_rows = sorted(
            declared_capabilities - {entry.get("capability") for entry in survey.get("surveys", [])}
        )
        checks.append(
            check_item(
                "tool_survey_rows_present",
                not missing_survey_rows,
                "Survey rows present for every load-bearing capability."
                if not missing_survey_rows
                else f"Missing survey rows for: {', '.join(missing_survey_rows)}",
            )
        )

        structured_constraints = isinstance(survey.get("constraints"), dict) and bool(survey.get("constraints"))
        structured_constraints = structured_constraints and all(
            isinstance(row.get("constraints"), dict) and bool(row.get("constraints"))
            for row in survey.get("surveys", [])
        )
        checks.append(
            check_item(
                "structured_constraints_present",
                structured_constraints,
                "Structured constraint objects present at snapshot and survey-row level."
                if structured_constraints
                else "Tool survey constraints must be structured objects, not free-form bar strings.",
            )
        )

        for item in survey.get("oai_plan_responses", []):
            oai_checks, oai_warnings = _validate_oai_plan(item)
            checks.extend(oai_checks)
            warnings.extend(oai_warnings)
            ad_binding = ((item.get("operator_decision") or {}).get("ad_binding") or "")
            if plan_text and ad_binding:
                checks.append(
                    check_item(
                        f"{item.get('oai_id', 'OAI-PLAN')}_ad_binding_exists",
                        ad_binding in set(AD_RE.findall(plan_text)),
                        f"{ad_binding} exists in the plan."
                        if ad_binding in set(AD_RE.findall(plan_text))
                        else f"{ad_binding} referenced by OAI-PLAN is missing from the plan.",
                    )
                )

        for candidate in _survey_candidates(survey):
            if candidate.get("evidence_confidence") == "stale_accepted":
                warnings.append(f"{candidate.get('tool_slug')} uses evidence_confidence: stale_accepted.")

        checks.extend(_validate_canary_blocks(survey, attempted_ticket=attempted_ticket))

    if plan_text:
        checks.extend(_validate_ad_tool_stack_refs(plan_text))

    checks.extend(_validate_ticket_tool_stack_refs(ticket_paths or []))
    runtime_checks, runtime_records = _validate_runtime_check_tool_stack_refs(runtime_check_paths or [])
    checks.extend(runtime_checks)

    oai_tools: list[dict[str, Any]] = []
    authorization_ids: set[str] = set()
    if survey is not None:
        for item in survey.get("oai_plan_responses", []):
            auth_id = _authorization_id_from_item(item)
            if auth_id:
                authorization_ids.add(auth_id)

    for path in oai_tool_paths or []:
        try:
            item = load_oai_tool(path)
            oai_tools.append(item)
            auth_id = _authorization_id_from_item(item)
            if auth_id:
                authorization_ids.add(auth_id)
            oai_checks, oai_warnings = _validate_oai_tool(item, plan_text=plan_text)
            checks.extend(oai_checks)
            warnings.extend(oai_warnings)
        except (ValueError, jsonschema.ValidationError, yaml.YAMLError, json.JSONDecodeError) as exc:
            checks.append(check_item(f"{path.name}_oai_tool_schema", False, f"OAI-TOOL invalid: {exc}"))

    for path in oai_spend_paths or []:
        try:
            item = load_oai_spend(path)
            auth_id = _authorization_id_from_item(item)
            if auth_id:
                authorization_ids.add(auth_id)
            oai_checks, oai_warnings = _validate_oai_spend(item, plan_text=plan_text)
            checks.extend(oai_checks)
            warnings.extend(oai_warnings)
        except (ValueError, jsonschema.ValidationError, yaml.YAMLError, json.JSONDecodeError) as exc:
            checks.append(check_item(f"{path.name}_oai_spend_schema", False, f"OAI-SPEND invalid: {exc}"))

    for path in acquisition_manifest_paths or []:
        try:
            manifest = load_acquisition_manifest(path)
            checks.append(check_item(f"{path.name}_acquisition_manifest_schema", True, "Acquisition manifest schema-valid."))
            checks.extend(_validate_acquisition_manifest_policy(manifest))
        except (ValueError, jsonschema.ValidationError, yaml.YAMLError, json.JSONDecodeError) as exc:
            checks.append(check_item(f"{path.name}_acquisition_manifest_schema", False, f"Acquisition manifest invalid: {exc}"))

    for path in spending_record_paths or []:
        try:
            record = load_spending_record(path)
            checks.append(check_item(f"{path.name}_spending_record_schema", True, "Spending reservation/capture record schema-valid."))
            if record.get("state") == "captured":
                auth_id = record.get("authorization_id")
                checks.append(
                    check_item(
                        f"{path.name}_captured_spend_authorization_trace",
                        bool(auth_id and auth_id in authorization_ids),
                        f"Captured spend traces to authorization_id {auth_id}."
                        if auth_id and auth_id in authorization_ids
                        else f"Captured spend authorization_id {auth_id} is missing from OAI responses.",
                    )
                )
        except (ValueError, jsonschema.ValidationError, yaml.YAMLError, json.JSONDecodeError) as exc:
            checks.append(check_item(f"{path.name}_spending_record_schema", False, f"Spending record invalid: {exc}"))

    events: list[dict[str, Any]] = []
    for path in checkpoint_paths or []:
        try:
            checkpoint = load_checkpoint(path)
            checks.append(check_item(f"{path.name}_checkpoint_schema", True, "Disposition checkpoint schema-valid."))
            event = _event_from_checkpoint(path, checkpoint)
            if event:
                events.append(event)
            canary = checkpoint.get("tool_presence_canary") or {}
            attempted = attempted_ticket or canary.get("attempted_ticket")
            if attempted and canary.get("canary_status") in {"not_run", "failed"} and attempted in (canary.get("blocked_tickets") or []):
                checks.append(
                    check_item(
                        f"{path.name}_canary_blocks_ticket",
                        False,
                        f"{attempted} cannot move in_progress while canary_status is {canary.get('canary_status')}.",
                    )
                )
        except (ValueError, jsonschema.ValidationError, yaml.YAMLError, json.JSONDecodeError) as exc:
            checks.append(check_item(f"{path.name}_checkpoint_schema", False, f"Checkpoint invalid: {exc}"))

    for record in runtime_records:
        event = _event_from_runtime_check(record["path"], record["data"])
        if event:
            events.append(event)

    checks.extend(_validate_tool_fit_trigger(events, oai_tools, plan_text))

    failures = [check for check in checks if not check["ok"]]
    return {
        "ok": not failures,
        "generated": now(),
        "plan": str(plan_path) if plan_path else None,
        "survey": str(survey_path) if survey_path else None,
        "checks": checks,
        "warnings": warnings,
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Tool Survey Check",
        "",
        f"_Generated: {report['generated']}_",
        "",
        "## Checks",
        "",
    ]
    for check in report["checks"]:
        marker = "PASS" if check["ok"] else "FAIL"
        lines.append(f"- **{marker}** `{check['name']}` - {check['details']}")
    if report["warnings"]:
        lines.extend(["", "## Warnings", ""])
        for warning in report["warnings"]:
            lines.append(f"- {warning}")
    lines.extend(["", f"**Verdict:** {'PASS' if report['ok'] else 'FAIL'}"])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", help="Path to project plan markdown.")
    parser.add_argument("--survey", help="Path to tool survey snapshot markdown/yaml/json.")
    parser.add_argument("--checkpoint", action="append", default=[], help="Disposition checkpoint file to validate.")
    parser.add_argument("--oai-tool", action="append", default=[], help="OAI-TOOL response file to validate.")
    parser.add_argument("--oai-spend", action="append", default=[], help="OAI-SPEND response file to validate.")
    parser.add_argument("--acquisition-manifest", action="append", default=[], help="Acquire-Tool transaction manifest to validate.")
    parser.add_argument("--spending-record", action="append", default=[], help="Spending reservation/capture/release record to validate.")
    parser.add_argument("--ticket", action="append", default=[], help="Ticket file whose frontmatter should be checked.")
    parser.add_argument("--runtime-check", action="append", default=[], help="Runtime check artifact to validate.")
    parser.add_argument("--attempted-ticket", help="Ticket attempted to move in_progress for canary blocking checks.")
    parser.add_argument("--json", action="store_true", help="Emit JSON to stdout instead of markdown.")
    parser.add_argument("--json-out", help="Optional JSON report path.")
    parser.add_argument("--markdown-out", help="Optional markdown report path.")
    args = parser.parse_args()

    plan_path = Path(args.plan).resolve() if args.plan else None
    survey_path = Path(args.survey).resolve() if args.survey else None
    checkpoint_paths = [Path(p).resolve() for p in args.checkpoint]
    oai_tool_paths = [Path(p).resolve() for p in args.oai_tool]
    oai_spend_paths = [Path(p).resolve() for p in args.oai_spend]
    acquisition_manifest_paths = [Path(p).resolve() for p in args.acquisition_manifest]
    spending_record_paths = [Path(p).resolve() for p in args.spending_record]
    ticket_paths = [Path(p).resolve() for p in args.ticket]
    runtime_check_paths = [Path(p).resolve() for p in args.runtime_check]

    report = validate_tool_survey(
        plan_path=plan_path,
        survey_path=survey_path,
        checkpoint_paths=checkpoint_paths,
        oai_tool_paths=oai_tool_paths,
        oai_spend_paths=oai_spend_paths,
        acquisition_manifest_paths=acquisition_manifest_paths,
        spending_record_paths=spending_record_paths,
        ticket_paths=ticket_paths,
        runtime_check_paths=runtime_check_paths,
        attempted_ticket=args.attempted_ticket,
    )
    if args.json_out:
        Path(args.json_out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json_out).write_text(json.dumps(report, indent=2), encoding="utf-8")
    if args.markdown_out:
        Path(args.markdown_out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.markdown_out).write_text(render_markdown(report), encoding="utf-8")
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(render_markdown(report))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
