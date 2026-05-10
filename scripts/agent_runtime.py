#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import signal
import subprocess
import sys
import tempfile
import time
import uuid
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path, PurePosixPath

import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

DATE_FMT = "%Y-%m-%d %H:%M"
ISO_FMT = "%Y-%m-%dT%H:%M"
TIGHT_THRESHOLD_PCT = 80.0
CRITICAL_THRESHOLD_PCT = 95.0
EXECUTOR_HEARTBEAT_SECS = 15
EXECUTOR_TERMINAL_GRACE_SECS = 30
EXECUTOR_STOP_WAIT_SECS = 5
EXECUTOR_SPAWN_WAIT_SECS = 5
EXECUTOR_SPAWN_POLL_SECS = 0.1
TERMINAL_TICKET_STATUSES = {"closed", "blocked", "waiting"}
GATE_TASK_TYPES = {"code_review", "credibility_gate", "visual_review"}
EXECUTOR_FRONTMATTER_KEYS = {
    "executor_agent",
    "executor_preferred_agent",
    "executor_routing_reason",
    "executor_agent_mode",
    "executor_task_type",
    "executor_runtime_pid",
    "executor_child_pid",
    "executor_started",
    "executor_last_heartbeat",
    "executor_ledger",
}

DEFAULT_ROUTING = {
    "agent_mode": "chat_native",
    "host_agent": "",
    "budget_based_routing": False,
    "agents": {
        "claude": {
            "cli": "claude -p --model claude-opus-4-7 --effort max",
            "enabled": True,
            "monthly_credit_budget": 100,
            "priority": 1,
        },
        "codex": {
            "cli": "codex exec",
            "enabled": False,
            "monthly_credit_budget": 100,
            "priority": 2,
        },
        "gemini": {
            "cli": "gemini",
            "enabled": False,
            "monthly_credit_budget": 100,
            "priority": 3,
        },
    },
    "task_routing": {
        "planner": "claude",
        "orchestrator": "claude",
        "design": "claude",
        "creative_brief": "codex",
        "verification_manifest_generate": "codex",
        "verification_manifest_execute": "codex",
        "test_manifest_generate": "codex",
        "test_manifest_execute": "codex",
        "self_review": "codex",
        "quality_check": "codex",
        "visual_review": "claude",
        "artifact_polish_review": "codex",
        "credibility_gate": "codex",
        "adversarial_probe": "codex",
        "drift_detection": "codex",
        "email_composition": "claude",
        "vault_navigation": "codex",
        "onboarding": "claude",
        "orchestration": "claude",
        "project_change_control": "codex",
        "project_amendment": "codex",
        "project_replan": "codex",
        "plan_rebase": "codex",
        "plan_rebaseline": "codex",
        "plan_reconciliation": "codex",
        "roadmap_reconciliation": "codex",
        "architecture_decision": "codex",
        "simulation_rehearsal": "codex",
        "build": "codex",
        "code_build": "codex",
        "code_review": "codex",
        "code_fix": "codex",
        "test_generation": "codex",
        "mcp_build": "codex",
        "mcp_review": "codex",
        "artifact_cleanup": "codex",
        "receipt_cleanup": "codex",
        "docs_cleanup": "codex",
        "brief_remediation": "codex",
        "evidence_cleanup": "codex",
        "gate_remediation": "codex",
        "general": "codex",
    },
    # Contract tags such as stitch-required/ui-design must enforce prompt and gate
    # requirements, not silently move expensive worker tickets off the Codex lane.
    "routing_override_tags": [],
    "fallback_policy": (
        "Route to the preferred agent for each task type. "
        "If that agent is unavailable, fall back to the other enabled agent. "
        "Budget-based throttling is disabled."
    ),
    "orchestration_context_mode": "tiered",
    "orchestration_context_packet_max_chars": 16000,
    "orchestration_context_expand_on": [
        "phase_gate",
        "ambiguous_decision",
        "conflicting_evidence",
        "admin_or_client_communication",
        "system_anomaly",
        "delivery_or_completion",
    ],
}

DEFAULT_QUALITY_CONTRACT = {
    "optimize_for": "credible_shipping",
    "no_unverified_claims": True,
    "fresh_checkout_required": True,
    "documented_commands_must_pass": True,
    "zero_failing_tests": True,
    "warning_budget_default": 0,
    "high_or_critical_vulns_allowed": 0,
    "critical_flow_pass_rate_required": 100,
    "claim_ledger_required": True,
    "limitations_required": True,
    "proof_matrix_required": True,
    "prune_unverified_features": True,
    "max_failed_gate_rounds_before_scope_cut": 2,
    "reserve_verification_effort_pct": 30,
    "artifact_polish_review_required": True,
    "review_pack_required": True,
    "clean_room_artifact_review_required": True,
    "reserve_polish_effort_pct": 15,
    "concept_required_for_frontend_design": True,
    "stitch_required_for_existing_public_surface_redesigns": False,
    "stitch_required_for_multi_screen_high_complexity_ui": False,
    "implementation_only_allowed_for_low_risk_ui_changes": True,
    "stitch_block_on_unavailable": False,
    "stitch_design_doc_required": True,
    "stitch_screen_artifacts_required": True,
    "stitch_qc_reference_required": True,
    "visual_quality_bar_required": True,
    "narrative_structure_required_for_public_surfaces": True,
    "composition_anchors_required_for_public_surfaces": True,
    "replace_vs_preserve_required_for_existing_surface_redesigns": True,
    "greenfield_concept_required_for_existing_public_surfaces": True,
    "runtime_stitch_parity_required_for_public_surface_redesigns": False,
    "stitch_artifacts_must_be_fresh": True,
    "stitch_required_codex_code_build_requires_sealed_design_package": False,
    "qc_runtime_screenshot_reference_required": True,
    "runtime_screenshot_hashes_are_copy_integrity_only": True,
    "dynamic_ui_preservation_requires_semantic_gate": True,
    "runtime_ui_screenshots_must_not_require_byte_identity_across_captures": True,
    "screenshot_laundering_for_gate_pass_prohibited": True,
    "page_contract_required_for_nav_surfaces": True,
    "route_family_required_for_operator_surfaces": True,
    "stitch_required_for_existing_route_family_redesigns": False,
    "route_family_section_required_for_operator_surfaces": True,
    "composition_anchors_required_for_route_family_surfaces": True,
    "route_family_parity_required_in_qc": True,
    "dangerous_actions_must_be_nested": True,
    "separate_design_stage_for_public_surfaces": True,
    "generic_saas_layout_is_failure_mode": True,
}

DESIGN_MODES = {"stitch_required", "concept_required", "implementation_only"}
STITCH_REQUIRED_TAGS = {"stitch-required"}
IMPLEMENTATION_ONLY_TAGS = {"implementation-only"}
STITCH_EXEMPT_TAGS = {"stitch-exempt", "non-visual", "backend-only"}
ROUTE_FAMILY_REQUIRED_TAGS = {"route-family-required"}
STITCH_DESIGN_PACKAGE_BLOCKER = "STITCH-DESIGN-PACKAGE"
STITCH_DESIGN_PACKAGE_REF_FIELDS = (
    "stitch_design_package_ref",
    "stitch_design_package",
    "sealed_stitch_package_ref",
    "sealed_stitch_package",
    "sealed_design_package_ref",
    "sealed_design_package",
    "sealed_design_artifacts_ref",
    "sealed_design_artifacts",
    "design_package_ref",
    "stitch_artifacts_ref",
)
STITCH_DESIGN_PACKAGE_READY_FIELDS = (
    "stitch_design_package_ready",
    "sealed_stitch_package_ready",
    "sealed_design_package_ready",
    "design_package_ready",
)
VALID_AGENT_MODES = {"normal", "codex_fallback", "claude_fallback", "chat_native"}
FALLBACK_MODE_TARGETS = {"codex_fallback": "codex", "claude_fallback": "claude"}
# Env-var fingerprints we trust to identify the orchestrator's host CLI.
# CLAUDECODE=1 is set by Claude Code (verified). No equivalent has been
# verified for Codex CLI yet, so absence of CLAUDECODE does NOT prove Codex —
# operators running in Codex should set host_agent: codex in platform.md.
HOST_AGENT_ENV_FINGERPRINTS = (
    ("CLAUDECODE", "claude"),
    ("CLAUDE_CODE_ENTRYPOINT", "claude"),
    ("CODEX_HOME", "codex"),
)
# Semantic role names usable in --force-agent. Resolve to a concrete agent
# based on agent_mode + task_routing, so the skill can stay mode-agnostic
# instead of hardcoding "codex" or "claude" in gate prompts.
#
# gate_reviewer: the cross-model reviewer for code/proof/credibility gates
#   (resolves to task_routing[code_review] in normal mode).
# visual_reviewer: the multimodal/taste reviewer for visual gates
#   (resolves to task_routing[visual_review] in normal mode).
FORCE_AGENT_ROLES = {
    "gate_reviewer": {"normal_routing_key": "code_review", "normal_default": "codex"},
    "visual_reviewer": {"normal_routing_key": "visual_review", "normal_default": "claude"},
}
VALID_ORCHESTRATION_CONTEXT_MODES = {"full", "tiered", "compact"}
PROJECT_RECONCILIATION_TASK_TYPES = {
    "project_change_control",
    "project_amendment",
    "project_replan",
    "plan_rebase",
    "plan_rebaseline",
    "plan_reconciliation",
    "roadmap_reconciliation",
    "architecture_decision",
}
PROJECT_RECONCILIATION_TAGS = {
    "project-change-control",
    "project-amendment",
    "project-replan",
    "plan-rebase",
    "plan-rebaseline",
    "plan-reconciliation",
    "roadmap-reconciliation",
    "architecture-decision",
    "scope-update",
    "phase-amendment",
}
CLAUDE_JUDGMENT_TAGS = {
    "strategy-review",
    "orchestration-decision",
    "stakeholder-communication",
    "ambiguous-product-reasoning",
    "final-judgment",
    "visual-judgment",
}
PROJECT_RECONCILIATION_TITLE_RE = re.compile(
    r"\b("
    r"project amendment|admin scope update|scope update|project replan|rebaseline|"
    r"plan rebase|plan rebaseline|plan reconciliation|roadmap reconciliation|"
    r"architecture decision|architecture delta"
    r")\b",
    re.IGNORECASE,
)
UI_SURFACE_HINT_RE = re.compile(
    r"\b("
    r"ui|ux|user interface|frontend|front-end|landing page|marketing site|dashboard|admin panel|"
    r"web app|mobile app|desktop app|screen|page|layout|design system|component library|visual"
    r")\b",
    re.IGNORECASE,
)
PUBLIC_SURFACE_HINT_RE = re.compile(
    r"\b("
    r"landing page|homepage|home page|pricing page|marketing site|marketing page|"
    r"public-facing|public surface|hero section|hero"
    r")\b",
    re.IGNORECASE,
)
PAGE_CONTRACT_HINT_RE = re.compile(
    r"\b("
    r"account|settings|billing|dashboard|profile|admin panel|admin page"
    r")\b",
    re.IGNORECASE,
)
ROUTE_FAMILY_HINT_RE = re.compile(
    r"\b("
    r"pending review|handoff|memory browser|memory page|trust ledger|audit timeline|audit page|"
    r"live watch|agent console|retrieval / context|retrieval and context|knowledge graph|teach mode|"
    r"comments|feedback page|approvals page|operator console|operator surface|primary route|"
    r"top-level route|top level route|left-rail destination|nav destination"
    r")\b",
    re.IGNORECASE,
)
STITCH_CODEBUILD_HINT_RE = re.compile(
    r"\b("
    r"redesign|visual polish|ui polish|visual refresh|landing page|marketing site|dashboard|"
    r"admin panel|design system|theme overhaul|hero section|screen design|page layout"
    r")\b",
    re.IGNORECASE,
)
CROSS_CUTTING_RETRIEVAL_HINT_RE = re.compile(
    r"\b("
    r"cross-cutting|cross cutting|phase goal|acceptance criteria|gate|review pack|review-pack|"
    r"proof pack|proof-pack|evidence|traceability|qc|quality check|self-review|self review|"
    r"remediation|handoff|artifact index|current context|current-context|brief|briefs|"
    r"verification|adversarial|stress test"
    r")\b",
    re.IGNORECASE,
)
MULTI_SCREEN_COMPLEXITY_HINT_RE = re.compile(
    r"\b("
    r"multi-screen|multi screen|multi-step|multi step|dashboard|admin panel|settings flow|"
    r"app shell|design system|component library|state-heavy|complex ui|screen states"
    r")\b",
    re.IGNORECASE,
)
LOW_RISK_UI_CHANGE_HINT_RE = re.compile(
    r"\b("
    r"small polish|minor polish|low-risk ui|low risk ui|approved design|approved mock|"
    r"spacing tweak|copy tweak|button fix|alignment fix|wire up|implement approved|"
    r"follow-through|follow through|settings cleanup|header fix"
    r")\b",
    re.IGNORECASE,
)
VISUAL_REJECTION_HINT_RE = re.compile(
    r"\b("
    r"not approved|rejected|revision after rejection|re-review failed|redo the landing page|"
    r"admin revision|visual revision|design revision"
    r")\b",
    re.IGNORECASE,
)
EXISTING_SURFACE_REDESIGN_HINT_RE = re.compile(
    r"\b("
    r"existing landing page|existing homepage|existing home page|existing pricing page|existing page|"
    r"existing screen|existing surface|current landing page|current homepage|current page|"
    r"redesign|re-design|visual refresh|page overhaul|surface overhaul"
    r")\b",
    re.IGNORECASE,
)
NEXUS_DISCOVERY_TASK_TYPES = {
    "vault_navigation",
    "research",
    "knowledge-management",
    "source",
    "study",
    "reflect",
    "reflection",
}
NEXUS_DISCOVERY_HINT_RE = re.compile(
    r"\b("
    r"vault|wiki link|wiki links|see also|backlink|backlinks|link graph|linked context|"
    r"related context|related docs|related files|related tickets|brief|briefs|proof|proofs|"
    r"ticket|tickets|prior work|previous work|knowledge graph"
    r")\b",
    re.IGNORECASE,
)
CODE_INTELLIGENCE_TASK_TYPES = {
    "code_build",
    "code_review",
    "code_fix",
    "test_generation",
    "mcp_build",
    "mcp_review",
    "brief_remediation",
    "evidence_cleanup",
    "gate_remediation",
}
HYBRID_RETRIEVAL_ESCALATION_TASK_TYPES = {
    "creative_brief",
    "self_review",
    "quality_check",
    "visual_review",
    "credibility_gate",
    "code_review",
    "code_fix",
    "project_change_control",
    "project_amendment",
    "project_replan",
    "plan_rebase",
    "plan_rebaseline",
    "plan_reconciliation",
    "roadmap_reconciliation",
    "architecture_decision",
    "docs_cleanup",
    "artifact_cleanup",
    "receipt_cleanup",
    "brief_remediation",
    "evidence_cleanup",
    "gate_remediation",
    "research",
    "vault_navigation",
}
HYBRID_RETRIEVAL_CLEAN_ROOM_TASK_TYPES = {"stress_test", "artifact_polish_review", "adversarial_probe"}
STITCH_AUTH_BLOCKER = "STITCH-AUTH"
STITCH_API_KEY_BLOCKER = "STITCH-API-KEY"
STITCH_AUTH_STATE_PATH = REPO_ROOT / "vault" / "config" / "stitch-auth-state.json"
CODEX_CONFIG_PATH = Path.home() / ".codex" / "config.toml"
PROJECT_CODE_INDEX_STATE_PATH = REPO_ROOT / "data" / "project_code_index_state.json"
STITCH_AUTH_FLOW_TTL_SECS = 15 * 60
STITCH_CLAUDE_CWD = REPO_ROOT / "vault"
STITCH_OAUTH_URL_RE = re.compile(r"https://accounts\.google\.com/o/oauth2/v2/auth\?\S+")
STITCH_PROXY_SERVER_RELATIVE = Path("tools/stitch-mcp-proxy/server.mjs")


def load_yaml_map(path: Path) -> dict:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def load_json_map(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def load_toml_map(path: Path) -> tuple[dict, str]:
    try:
        import tomllib  # type: ignore[import-not-found]
    except ModuleNotFoundError:
        try:
            import tomli as tomllib  # type: ignore[no-redef]
        except ModuleNotFoundError:
            return {}, "No TOML parser is available. Install Python 3.11+ or tomli."

    try:
        with path.open("rb") as handle:
            data = tomllib.load(handle)
    except FileNotFoundError:
        return {}, f"TOML file not found: {path}"
    except Exception as exc:
        return {}, f"Failed to parse TOML file {path}: {exc}"
    return (data if isinstance(data, dict) else {}), ""


def run_git_capture(command: list[str], cwd: Path) -> tuple[bool, str]:
    try:
        result = subprocess.run(command, cwd=str(cwd), capture_output=True, text=True, timeout=10, check=False)
    except Exception:
        return False, ""
    if result.returncode != 0:
        return False, ""
    return True, (result.stdout or "").strip()


def discover_live_git_root(path: Path) -> Path | None:
    probe = path if path.is_dir() else path.parent
    if not probe.exists():
        return None
    ok, output = run_git_capture(["git", "rev-parse", "--show-toplevel"], probe)
    if not ok or not output:
        return None
    return Path(output).expanduser().resolve()


def strip_inline_comment(value: str) -> str:
    in_quote = False
    quote_char = ""
    bracket_depth = 0
    out = []
    for idx, char in enumerate(value):
        if char in {"'", '"'}:
            if not in_quote:
                in_quote = True
                quote_char = char
            elif quote_char == char:
                in_quote = False
                quote_char = ""
            out.append(char)
            continue
        if not in_quote:
            if char == "[":
                bracket_depth += 1
            elif char == "]":
                bracket_depth = max(0, bracket_depth - 1)
            elif char == "#" and bracket_depth == 0:
                break
        out.append(char)
    return "".join(out).rstrip()


def parse_scalar(value: str):
    value = strip_inline_comment(value).strip()
    if not value:
        return ""
    if value.startswith('"') and value.endswith('"'):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value[1:-1]
    if value.startswith("'") and value.endswith("'"):
        return value[1:-1]
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [parse_scalar(item.strip()) for item in inner.split(",")]
    lowered = value.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    if re.fullmatch(r"-?\d+\.\d+", value):
        return float(value)
    return value


def extract_heading_code_block(text: str, heading: str) -> str:
    lines = text.splitlines()
    heading_line = f"## {heading}"
    for idx, line in enumerate(lines):
        if line.strip() != heading_line:
            continue
        block_start = None
        for inner_idx in range(idx + 1, len(lines)):
            if lines[inner_idx].strip() == "```yaml":
                block_start = inner_idx + 1
                break
            if lines[inner_idx].startswith("## "):
                break
        if block_start is None:
            continue
        block_lines = []
        for inner_idx in range(block_start, len(lines)):
            if lines[inner_idx].strip() == "```":
                return "\n".join(block_lines)
            block_lines.append(lines[inner_idx])
    return ""


def resolve_runtime_arg_path(raw_path: Path | str) -> Path:
    candidate = Path(raw_path).expanduser()
    if candidate.is_absolute():
        return candidate.resolve()

    cwd_candidate = (Path.cwd() / candidate).resolve()
    if cwd_candidate.exists():
        return cwd_candidate

    repo_candidate = (REPO_ROOT / candidate).resolve()
    if repo_candidate.exists():
        return repo_candidate

    return cwd_candidate


def load_agent_routing(platform_path: Path) -> dict:
    routing = json.loads(json.dumps(DEFAULT_ROUTING))
    if not platform_path.exists():
        return routing

    block = extract_heading_code_block(platform_path.read_text(encoding="utf-8"), "Agent Routing")
    if not block:
        return routing

    section = None
    current_agent = None
    for raw_line in block.splitlines():
        if not raw_line.strip():
            continue
        if raw_line.strip().startswith("#"):
            continue

        indent = len(raw_line) - len(raw_line.lstrip(" "))
        line = raw_line.strip()

        if indent == 0 and line == "agent_routing:":
            section = None
            current_agent = None
            continue
        if indent == 2 and line.startswith("agent_mode:"):
            _, value = line.split(":", 1)
            mode = str(parse_scalar(value) or "chat_native").strip()
            routing["agent_mode"] = mode if mode in VALID_AGENT_MODES else "chat_native"
            continue
        if indent == 2 and line.startswith("host_agent:"):
            _, value = line.split(":", 1)
            host = str(parse_scalar(value) or "").strip().lower()
            routing["host_agent"] = host
            continue
        if indent == 2 and line.startswith("budget_based_routing:"):
            _, value = line.split(":", 1)
            routing["budget_based_routing"] = bool(parse_scalar(value))
            continue
        if indent == 2 and line.startswith("orchestration_context_mode:"):
            _, value = line.split(":", 1)
            mode = str(parse_scalar(value) or "tiered").strip().lower()
            routing["orchestration_context_mode"] = mode if mode in VALID_ORCHESTRATION_CONTEXT_MODES else "tiered"
            continue
        if indent == 2 and line.startswith("orchestration_context_packet_max_chars:"):
            _, value = line.split(":", 1)
            parsed_value = parse_scalar(value)
            routing["orchestration_context_packet_max_chars"] = parsed_value if isinstance(parsed_value, int) and parsed_value > 0 else 16000
            continue
        if indent == 2 and line.startswith("orchestration_context_expand_on:"):
            _, value = line.split(":", 1)
            parsed_value = parse_scalar(value)
            if isinstance(parsed_value, list):
                routing["orchestration_context_expand_on"] = [str(item).strip() for item in parsed_value if str(item).strip()]
            continue
        if indent == 2 and line == "agents:":
            section = "agents"
            current_agent = None
            continue
        if indent == 2 and line == "task_routing:":
            section = "task_routing"
            current_agent = None
            continue
        if indent == 2 and line.startswith("routing_override_tags:"):
            _, value = line.split(":", 1)
            raw = value.strip().strip("[]")
            routing["routing_override_tags"] = [t.strip() for t in raw.split(",") if t.strip()]
            continue
        if indent == 2 and line.startswith("routing_override_target:"):
            _, value = line.split(":", 1)
            routing["routing_override_target"] = parse_scalar(value)
            continue
        if indent == 2 and line.startswith("fallback_policy:"):
            _, value = line.split(":", 1)
            routing["fallback_policy"] = parse_scalar(value)
            continue

        if section == "agents":
            if indent == 4 and line.endswith(":"):
                current_agent = line[:-1]
                routing["agents"].setdefault(current_agent, {})
                continue
            if indent == 6 and current_agent and ":" in line:
                key, value = line.split(":", 1)
                routing["agents"][current_agent][key.strip()] = parse_scalar(value)
                continue

        if section == "task_routing" and indent == 4 and ":" in line:
            key, value = line.split(":", 1)
            routing["task_routing"][key.strip()] = parse_scalar(value)

    return routing


def load_quality_contract(platform_path: Path) -> dict:
    contract = json.loads(json.dumps(DEFAULT_QUALITY_CONTRACT))
    if not platform_path.exists():
        return contract

    block = extract_heading_code_block(
        platform_path.read_text(encoding="utf-8"),
        "Quality Contract",
    )
    if not block:
        return contract

    in_contract = False
    for raw_line in block.splitlines():
        if not raw_line.strip():
            continue
        if raw_line.strip().startswith("#"):
            continue

        indent = len(raw_line) - len(raw_line.lstrip(" "))
        line = raw_line.strip()

        if indent == 0 and line == "quality_contract:":
            in_contract = True
            continue
        if not in_contract:
            continue
        if indent != 2 or ":" not in line:
            continue

        key, value = line.split(":", 1)
        contract[key.strip()] = parse_scalar(value)

    return contract


def build_quality_contract_preamble(local_now: str, contract: dict) -> str:
    lines = [
        f"Current local datetime: {local_now}.",
        "Use this machine-local wall-clock time for any created/updated/completed/captured fields or work log entries.",
        "Do not infer timestamps or convert from UTC unless a timezone is explicitly present.",
        "",
        "Primary objective: maximize client trust, not feature count.",
        f"Optimize for: {contract.get('optimize_for', 'credible_shipping')}.",
        "Operate under this quality contract:",
    ]

    if contract.get("no_unverified_claims", True):
        lines.append("- Do not claim, document, or summarize anything you have not verified with evidence.")
    if contract.get("claim_ledger_required", True):
        lines.append("- Maintain claim/evidence parity: every important claim should map to a command result, artifact, screenshot, or cited source.")
    if contract.get("fresh_checkout_required", True):
        lines.append("- For software deliverables, verify the documented workflow from a fresh checkout when feasible.")
    if contract.get("documented_commands_must_pass", True):
        lines.append("- Documented setup/build/test/lint commands must pass before you describe the project as ready.")
    if contract.get("zero_failing_tests", True):
        lines.append("- Do not ship or describe a software deliverable as complete if tests are failing.")

    warning_budget = contract.get("warning_budget_default")
    if warning_budget is not None:
        lines.append(f"- Warning budget default: {warning_budget}. If warnings remain, either fix them or document them explicitly as accepted debt.")

    vuln_budget = contract.get("high_or_critical_vulns_allowed")
    if vuln_budget is not None:
        lines.append(f"- Allowed shipped high/critical dependency vulnerabilities: {vuln_budget}.")

    critical_flow_pass_rate = contract.get("critical_flow_pass_rate_required")
    if critical_flow_pass_rate is not None:
        lines.append(f"- Required critical flow pass rate for ready-to-ship work: {critical_flow_pass_rate}%.")

    if contract.get("limitations_required", True):
        lines.append("- Include explicit known limitations and boundaries; do not imply perfection.")

    reserve_pct = contract.get("reserve_verification_effort_pct")
    if reserve_pct is not None:
        lines.append(f"- Reserve about {reserve_pct}% of effort for verification, contradiction checks, and pruning.")
    if contract.get("artifact_polish_review_required", True):
        lines.append("- Final output must survive a clean-room artifact polish review, not just builder-side review or technical QC.")
    polish_pct = contract.get("reserve_polish_effort_pct")
    if polish_pct is not None:
        lines.append(f"- Reserve about {polish_pct}% of effort for last-mile polish, coherence, and first-impression quality.")
    if contract.get("review_pack_required", True):
        lines.append("- Build a consumable review pack for user/client-facing artifacts so review is based on the artifact itself, not only implementation details.")
        lines.append("- For interactive browser/native artifacts, capture a short QC-stage walkthrough video and include it in the review pack; if the surface is interactive enough to need motion/flow judgment, missing video is a review failure, not a nice-to-have.")

    return "\n".join(lines)


def parse_frontmatter_map(path: Path) -> dict:
    frontmatter, _ = split_frontmatter(path.read_text(encoding="utf-8"))
    data = {}
    for raw_line in frontmatter.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        data[key.strip()] = parse_scalar(value)
    return data


def normalize_blocked_by(raw_value: object) -> list[str]:
    if raw_value is None:
        return []
    if isinstance(raw_value, list):
        candidates = raw_value
    else:
        candidates = [raw_value]
    normalized: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        text = str(candidate or "").strip().upper()
        if not text or text in seen:
            continue
        seen.add(text)
        normalized.append(text)
    return normalized


def frontmatter_string_list(raw_value: object) -> list[str]:
    if raw_value is None:
        return []
    if isinstance(raw_value, list):
        candidates = raw_value
    else:
        candidates = [raw_value]
    values: list[str] = []
    for candidate in candidates:
        text = str(candidate or "").strip().strip('"').strip("'")
        if not text:
            continue
        values.append(text)
    return values


def parse_phase_value(raw_value: object) -> int | None:
    text = str(raw_value or "").strip()
    return int(text) if text.isdigit() else None


def normalize_wave_value(raw_value: object) -> str:
    text = str(raw_value or "").strip().upper()
    if text.startswith("WAVE "):
        text = text[5:].strip()
    return text


def normalize_tags(raw_value: object) -> set[str]:
    if raw_value is None:
        return set()
    if isinstance(raw_value, list):
        candidates = raw_value
    else:
        candidates = [raw_value]
    normalized: set[str] = set()
    for candidate in candidates:
        text = str(candidate or "").strip().lower()
        if not text:
            continue
        normalized.add(text)
    return normalized


def infer_creative_brief_scope(ticket_path: Path, ticket_data: dict) -> str:
    raw_scope = str(ticket_data.get("brief_scope", "")).strip().lower()
    if raw_scope in {"project", "phase", "ticket"}:
        return raw_scope

    tags = normalize_tags(ticket_data.get("tags"))
    if "project-scope" in tags:
        return "project"
    if "phase-scope" in tags:
        return "phase"
    if "ticket-scope" in tags:
        return "ticket"

    title = str(ticket_data.get("title", "")).strip().lower()
    body = ticket_path.read_text(encoding="utf-8").lower()
    if "project-scope" in title or "project-level" in title or "master contract" in title:
        return "project"
    if "project-scope" in body or "project-level" in body or "master contract" in body:
        return "project"
    if "phase-scoped" in body or re.search(r"\bphase\s+\d+\b", title) or re.search(r"\bphase\s+\d+\b", body):
        return "phase"
    if parse_phase_value(ticket_data.get("phase")) is not None and "creative brief" in title:
        return "phase"
    return "ticket"


def creative_brief_dependency_allowed(current_scope: str, blocker_scope: str) -> bool:
    rank = {"project": 0, "phase": 1, "ticket": 2}
    current_rank = rank.get(current_scope, 99)
    blocker_rank = rank.get(blocker_scope, 99)
    return blocker_rank < current_rank


def creative_brief_gate_passes(ticket_path: Path) -> tuple[bool, str]:
    from check_brief_gate import build_report as build_brief_gate_report

    report = build_brief_gate_report(
        argparse.Namespace(
            ticket_path=str(ticket_path),
            required_grade="A",
            search_root=[],
            json_out=None,
            markdown_out=None,
        )
    )
    if report.get("verdict") == "PASS":
        return True, "fresh passing brief gate found"
    failing_checks = [check for check in (report.get("checks") or []) if not check.get("ok")]
    if failing_checks:
        details = [str(check.get("details") or check.get("name") or "").strip() for check in failing_checks]
        details = [detail for detail in details if detail]
        if details:
            return False, "; ".join(details)
    selection_reason = str(report.get("selection_reason") or "").strip()
    return False, selection_reason or "brief gate failed"


def unresolved_ticket_blockers(ticket_path: Path) -> list[dict[str, str]]:
    ticket_data = parse_frontmatter_map(ticket_path)
    project = str(ticket_data.get("project", "")).strip()
    phase = parse_phase_value(ticket_data.get("phase"))
    wave = normalize_wave_value(ticket_data.get("wave"))
    current_task_type = str(ticket_data.get("task_type", "")).strip().lower()
    current_brief_scope = infer_creative_brief_scope(ticket_path, ticket_data) if current_task_type == "creative_brief" else ""
    tickets_dir = ticket_path.parent
    current_ticket_id = infer_ticket_id(ticket_path, ticket_data)

    ticket_index: dict[str, tuple[Path, dict]] = {}
    for candidate in tickets_dir.glob("T-*.md"):
        if not candidate.is_file():
            continue
        data = parse_frontmatter_map(candidate)
        ticket_index[infer_ticket_id(candidate, data)] = (candidate, data)

    unresolved: list[dict[str, str]] = []
    seen: set[str] = set()

    def add_unresolved(ticket_id: str, reason: str, source: str) -> None:
        key = f"{ticket_id}:{source}:{reason}"
        if key in seen:
            return
        seen.add(key)
        unresolved.append({"id": ticket_id, "reason": reason, "source": source})

    explicit_blockers = normalize_blocked_by(ticket_data.get("blocked_by"))
    for blocker_id in explicit_blockers:
        blocker = ticket_index.get(blocker_id)
        if blocker is None:
            add_unresolved(blocker_id, "blocker ticket file missing", "explicit")
            continue
        blocker_path, blocker_data = blocker
        blocker_status = str(blocker_data.get("status", "")).strip().lower()
        blocker_task_type = str(blocker_data.get("task_type", "")).strip().lower()
        if blocker_task_type == "creative_brief" and current_task_type == "creative_brief":
            blocker_scope = infer_creative_brief_scope(blocker_path, blocker_data)
            if not creative_brief_dependency_allowed(current_brief_scope, blocker_scope):
                continue
        if blocker_status not in {"closed", "done"}:
            add_unresolved(blocker_id, f"status is `{blocker_status or 'missing'}`", "explicit")
            continue
        if blocker_task_type == "creative_brief":
            passes, reason = creative_brief_gate_passes(blocker_path)
            if not passes:
                add_unresolved(blocker_id, reason, "brief_gate")

    if project:
        for blocker_id, (blocker_path, blocker_data) in ticket_index.items():
            if blocker_id == current_ticket_id:
                continue
            if str(blocker_data.get("project", "")).strip() != project:
                continue
            if str(blocker_data.get("task_type", "")).strip().lower() != "creative_brief":
                continue
            blocker_scope = infer_creative_brief_scope(blocker_path, blocker_data)
            if current_task_type == "creative_brief" and not creative_brief_dependency_allowed(current_brief_scope, blocker_scope):
                continue

            blocker_phase = parse_phase_value(blocker_data.get("phase"))
            blocker_wave = normalize_wave_value(blocker_data.get("wave"))
            if blocker_phase is None:
                scope_match = True
            elif phase is None or blocker_phase != phase:
                scope_match = False
            elif blocker_wave:
                scope_match = blocker_wave == wave
            else:
                scope_match = True
            if not scope_match:
                continue

            blocker_status = str(blocker_data.get("status", "")).strip().lower()
            if blocker_status not in {"closed", "done"}:
                add_unresolved(blocker_id, f"governing brief status is `{blocker_status or 'missing'}`", "governing_brief")
                continue
            passes, reason = creative_brief_gate_passes(blocker_path)
            if not passes:
                add_unresolved(blocker_id, reason, "governing_brief")

    return unresolved


def enforce_ticket_dependency_guard(ticket_path: Path) -> None:
    unresolved = unresolved_ticket_blockers(ticket_path)
    if not unresolved:
        return

    ticket_data = parse_frontmatter_map(ticket_path)
    now = current_local_iso()
    blocker_ids = []
    for item in unresolved:
        blocker_id = item["id"]
        if blocker_id not in blocker_ids:
            blocker_ids.append(blocker_id)
    existing_blockers = normalize_blocked_by(ticket_data.get("blocked_by"))
    merged_blockers = existing_blockers[:]
    for blocker_id in blocker_ids:
        if blocker_id not in merged_blockers:
            merged_blockers.append(blocker_id)

    previous_status = str(ticket_data.get("status", "")).strip().lower()
    updates: dict[str, object] = {
        "id": infer_ticket_id(ticket_path, ticket_data),
        "status": "blocked",
        "updated": now,
        "blocked_by": merged_blockers,
    }
    update_markdown_frontmatter(ticket_path, updates)

    summary = ", ".join(f"{item['id']} ({item['reason']})" for item in unresolved)
    if previous_status != "blocked" or existing_blockers != merged_blockers:
        append_ticket_work_log(
            ticket_path,
            f"{now}: Runtime dependency guard re-blocked ticket. Unresolved blockers: {summary}.",
        )

    raise SystemExit(
        f"RUNTIME-BLOCKED: {infer_ticket_id(ticket_path, ticket_data)} cannot start until blockers resolve: {summary}"
    )


def infer_ticket_id(ticket_path: Path, ticket_data: dict | None = None) -> str:
    data = ticket_data or parse_frontmatter_map(ticket_path)
    explicit = str(data.get("id", "")).strip()
    if explicit:
        return explicit
    match = re.match(r"^(T-\d+)\b", ticket_path.stem, re.IGNORECASE)
    if match:
        return match.group(1).upper()
    return ticket_path.stem


def normalize_tags(raw_tags: list[str] | str | None) -> list[str]:
    if raw_tags is None:
        return []
    if isinstance(raw_tags, str):
        candidates = [raw_tags]
    else:
        candidates = [str(tag) for tag in raw_tags]

    normalized = []
    seen = set()
    for candidate in candidates:
        tag = candidate.strip().lower()
        if not tag:
            continue
        if tag in seen:
            continue
        seen.add(tag)
        normalized.append(tag)
    return normalized


def normalize_design_mode(value: object) -> str:
    aliases = {
        "stitch": "stitch_required",
        "stitch_required": "stitch_required",
        "concept": "concept_required",
        "concept_required": "concept_required",
        "implementation": "implementation_only",
        "implementation-only": "implementation_only",
        "implementation_only": "implementation_only",
    }
    normalized = str(value or "").strip().lower()
    mapped = aliases.get(normalized, "")
    return mapped if mapped in DESIGN_MODES else ""


def load_ticket_context(ticket_path: str | None) -> dict:
    context = {
        "path": "",
        "title": "",
        "task_type": "",
        "complexity": "",
        "tags": [],
        "ui_work": False,
        "design_mode": "",
        "stitch_required": False,
        "public_surface": False,
        "existing_surface_redesign": False,
        "page_contract_required": False,
        "route_family_required": False,
    }
    if not ticket_path:
        return context

    path = Path(ticket_path).expanduser().resolve()
    if not path.exists():
        raise SystemExit(f"Ticket path does not exist: {path}")

    data = parse_frontmatter_map(path)
    design_mode = normalize_design_mode(data.get("design_mode", ""))
    if not design_mode and bool(data.get("stitch_required", False)):
        design_mode = "stitch_required"
    context.update(
        {
            "path": str(path),
            "title": str(data.get("title", "")).strip(),
            "task_type": str(data.get("task_type", "")).strip().lower(),
            "complexity": str(data.get("complexity", "")).strip().lower(),
            "tags": normalize_tags(data.get("tags")),
            "ui_work": bool(data.get("ui_work", False)),
            "design_mode": design_mode,
            "stitch_required": bool(data.get("stitch_required", False)),
            "public_surface": bool(data.get("public_surface", False)),
            "existing_surface_redesign": bool(data.get("existing_surface_redesign", False)),
            "page_contract_required": bool(data.get("page_contract_required", False)),
            "route_family_required": bool(data.get("route_family_required", False)),
        }
    )
    return context


def project_file_for_orchestration(project: str, client: str = "_platform", platform_root: Path = REPO_ROOT) -> Path:
    project_slug = str(project or "").strip()
    if not project_slug:
        raise SystemExit("Project slug is required to build an orchestrator prompt.")
    client_slug = str(client or "_platform").strip() or "_platform"
    if client_slug != "_platform":
        return platform_root / "vault" / "clients" / client_slug / "projects" / f"{project_slug}.md"
    return platform_root / "vault" / "projects" / f"{project_slug}.md"


def tickets_dir_for_project_file(project_file: Path) -> Path:
    if project_file.parent.name == "projects":
        return project_file.parent.parent / "tickets"
    return project_file.parent / "tickets"


def packet_timestamp(local_now: str) -> str:
    match = re.match(r"(\d{4}-\d{2}-\d{2})T(\d{2}):(\d{2})", str(local_now or ""))
    if match:
        return f"{match.group(1).replace('-', '')}T{match.group(2)}{match.group(3)}"
    return datetime.now().astimezone().strftime("%Y%m%dT%H%M")


def format_file_pointer(path: Path) -> str:
    if not path.exists():
        return f"`{path}` (missing)"
    modified = datetime.fromtimestamp(path.stat().st_mtime).astimezone().strftime("%Y-%m-%dT%H:%M %Z %z")
    return f"`{path}` (mtime {modified})"


def extract_recent_matching_lines(text: str, needle: str, limit: int = 8) -> list[str]:
    matches = [line.strip() for line in text.splitlines() if needle in line]
    return matches[-limit:]


def ticket_summary_for_packet(ticket_path: Path) -> dict:
    data = parse_frontmatter_map(ticket_path)
    return {
        "id": infer_ticket_id(ticket_path, data),
        "title": str(data.get("title", ticket_path.stem)).strip().strip('"'),
        "status": str(data.get("status", "")).strip(),
        "task_type": str(data.get("task_type", "")).strip(),
        "phase": data.get("phase", ""),
        "wave": str(data.get("wave", "")).strip().strip('"'),
        "blocked_by": normalize_blocked_by(data.get("blocked_by")),
        "updated": str(data.get("updated", "")).strip(),
        "completed": str(data.get("completed", "")).strip(),
        "executor_agent": str(data.get("executor_agent", "")).strip(),
        "executor_runtime_pid": str(data.get("executor_runtime_pid", "")).strip(),
        "executor_last_heartbeat": str(data.get("executor_last_heartbeat", "")).strip(),
        "path": str(ticket_path),
    }


def collect_project_ticket_summaries(project_file: Path, project_slug: str) -> list[dict]:
    tickets_dir = tickets_dir_for_project_file(project_file)
    if not tickets_dir.exists():
        return []

    summaries: list[dict] = []
    for ticket_path in sorted(tickets_dir.glob("T-*.md")):
        try:
            data = parse_frontmatter_map(ticket_path)
        except Exception:
            continue
        ticket_project = str(data.get("project", "")).strip().strip('"')
        if ticket_project != project_slug:
            continue
        summaries.append(ticket_summary_for_packet(ticket_path))
    return summaries


def compact_ticket_line(ticket: dict) -> str:
    pieces = [
        f"- {ticket['id']}",
        str(ticket.get("title") or "").strip(),
        f"status={ticket.get('status') or 'unknown'}",
    ]
    if ticket.get("task_type"):
        pieces.append(f"task_type={ticket['task_type']}")
    if ticket.get("wave"):
        pieces.append(f"wave={ticket['wave']}")
    if ticket.get("blocked_by"):
        pieces.append(f"blocked_by={ticket['blocked_by']}")
    if ticket.get("executor_agent"):
        pieces.append(f"agent={ticket['executor_agent']}")
    if ticket.get("executor_runtime_pid"):
        pieces.append(f"pid={ticket['executor_runtime_pid']}")
    if ticket.get("executor_last_heartbeat"):
        pieces.append(f"heartbeat={ticket['executor_last_heartbeat']}")
    if ticket.get("updated"):
        pieces.append(f"updated={ticket['updated']}")
    return " — ".join(pieces)


def truncate_packet(text: str, max_chars: int) -> str:
    if max_chars <= 0 or len(text.encode("utf-8")) <= max_chars:
        return text
    marker = "\n\n## Packet Truncation Notice\n\nThis packet hit the configured context budget. Treat it as an orientation artifact only and expand into source files before making non-routine decisions.\n"
    marker_bytes = marker.encode("utf-8")
    keep = max(1000, max_chars - len(marker_bytes))
    prefix = text.encode("utf-8")[:keep].decode("utf-8", errors="ignore").rstrip()
    return prefix + marker


def build_orchestration_state_packet(
    *,
    project_file: Path,
    project_slug: str,
    client: str,
    local_now: str,
    routing: dict,
) -> str:
    project_text = project_file.read_text(encoding="utf-8") if project_file.exists() else ""
    tickets = collect_project_ticket_summaries(project_file, project_slug) if project_file.exists() else []
    status_counts: dict[str, int] = defaultdict(int)
    for ticket in tickets:
        status_counts[str(ticket.get("status") or "unknown")] += 1

    active_statuses = {"open", "in-progress", "blocked", "waiting"}
    active_tickets = [ticket for ticket in tickets if str(ticket.get("status") or "").strip() in active_statuses]
    active_tickets = sorted(active_tickets, key=lambda ticket: (str(ticket.get("status") != "in-progress"), str(ticket.get("updated", ""))), reverse=True)
    recent_checkpoints = extract_recent_matching_lines(project_text, "ORCH-CHECKPOINT", limit=8)
    recent_violations = extract_recent_matching_lines(project_text, "ORCH-VIOLATION", limit=5)

    # Derived per-project context lives in a `<slug>.derived/` sibling folder.
    # See vault/SCHEMA.md → "Project Derived Context".
    derived_dir = project_file.parent / f"{project_slug}.derived"
    context_path = derived_dir / "current-context.md"
    artifact_index_path = derived_dir / "artifact-index.yaml"
    image_index_path = derived_dir / "image-evidence-index.yaml"
    video_index_path = derived_dir / "video-evidence-index.yaml"

    expand_on = routing.get("orchestration_context_expand_on") or []
    lines = [
        "---",
        "type: orchestration-state-packet",
        f'project: "{project_slug}"',
        f'client: "{client}"',
        f'captured: "{local_now}"',
        f"mode: {routing.get('orchestration_context_mode', 'tiered')}",
        "---",
        "",
        "# Orchestration State Packet",
        "",
        "This is a compact orientation packet for the Claude control plane. It is not a substitute for canonical source files when a decision is ambiguous, high-risk, or user-facing.",
        "",
        "## Context Mode",
        "",
        f"- Configured mode: `{routing.get('orchestration_context_mode', 'tiered')}`",
        f"- Packet max chars: `{routing.get('orchestration_context_packet_max_chars', 16000)}`",
        f"- Expand triggers: {', '.join(f'`{item}`' for item in expand_on) if expand_on else '`none configured`'}",
        "",
        "## Canonical Pointers",
        "",
        f"- Project file: {format_file_pointer(project_file)}",
        f"- Current context: {format_file_pointer(context_path)}",
        f"- Artifact index: {format_file_pointer(artifact_index_path)}",
        f"- Image evidence index: {format_file_pointer(image_index_path)}",
        f"- Video evidence index: {format_file_pointer(video_index_path)}",
        f"- Tickets directory: `{tickets_dir_for_project_file(project_file)}`",
        "",
        "## Ticket State",
        "",
        f"- Total tickets for project: `{len(tickets)}`",
        f"- Status counts: `{dict(sorted(status_counts.items()))}`",
        "",
        "## Active Tickets",
        "",
    ]
    if active_tickets:
        lines.extend(compact_ticket_line(ticket) for ticket in active_tickets[:20])
        if len(active_tickets) > 20:
            lines.append(f"- ... {len(active_tickets) - 20} additional active tickets omitted from packet. Expand into the tickets directory before making a non-routine sequencing decision.")
    else:
        lines.append("- No active open/in-progress/blocked/waiting tickets found for this project.")

    lines.extend(["", "## Recent Orchestrator Checkpoints", ""])
    if recent_checkpoints:
        lines.extend(f"- {checkpoint.lstrip('- ').strip()}" for checkpoint in recent_checkpoints)
    else:
        lines.append("- No ORCH-CHECKPOINT entries found. This may require normal startup assessment.")

    lines.extend(["", "## Recent Process Violations", ""])
    if recent_violations:
        lines.extend(f"- {violation.lstrip('- ').strip()}" for violation in recent_violations)
    else:
        lines.append("- None found in the recent project log scan.")

    lines.extend(
        [
            "",
            "## Claude Escalation Rules",
            "",
            "- You may use this packet for routine monitor/dispatch loops: collect completed executors, unblock clear dependencies, and spawn the next already-planned ticket.",
            "- Expand into canonical files before phase advancement, wave closure, project replanning, admin/client communication, conflicting evidence, stale/contradictory proof, system anomalies, or any decision that changes scope.",
            "- If the packet and canonical files disagree, canonical files win. Write an ORCH-CHECKPOINT noting the contradiction.",
            "- Do not reread broad historical context just to perform routine dispatch; read exact linked files only when the decision requires it.",
            "",
            "## Suggested First Action",
            "",
            "- Read the last checkpoint above, inspect only the active tickets needed for the next decision, then either spawn/collect via `agent_runtime.py` or explicitly escalate to full context with a checkpoint explaining why.",
            "",
        ]
    )
    return truncate_packet("\n".join(lines), int(routing.get("orchestration_context_packet_max_chars") or 16000))


def build_orchestrator_prompt(
    *,
    local_now: str,
    project_slug: str,
    client: str,
    project_file: Path,
    routing: dict,
    packet_path: Path | None = None,
) -> str:
    target = f"client: '{client}' project: '{project_slug}'" if client != "_platform" else f"project: '{project_slug}'"
    base = (
        f"Current local datetime: {local_now}. "
        "Use this machine-local wall-clock time for any created/updated/completed/captured fields or work log entries. "
        "Do not infer timestamps or convert from UTC unless a timezone is explicitly present. "
        "Read SYSTEM.md, then skills/orchestrator.md. "
        "IMPORTANT: Follow the MANDATORY Orchestrator Checkpointing section at the top of the skill — read the project file for existing ORCH-CHECKPOINT entries before acting, and write ORCH-CHECKPOINT entries after every major step (Steps 0, 8a, 9, 10, 12). "
    )
    mode = str(routing.get("orchestration_context_mode", "tiered") or "tiered").strip().lower()
    if mode not in VALID_ORCHESTRATION_CONTEXT_MODES:
        mode = "tiered"

    if mode == "full":
        return (
            f"{base}"
            "Orchestration context mode is FULL. Use the legacy full-context startup path in skills/orchestrator.md. "
            f"Resume the orchestrator for {target}"
        )

    packet_clause = ""
    if packet_path:
        packet_clause = f" Before broad context loading, read the orchestration state packet at `{packet_path}`."
    if mode == "compact":
        mode_clause = (
            "Orchestration context mode is COMPACT. Use the packet as the default control-plane context and expand only when an explicit escalation rule applies."
        )
    else:
        mode_clause = (
            "Orchestration context mode is TIERED. Read the compact state packet first, then expand into exact canonical files only when the packet flags uncertainty or the decision is high-risk, ambiguous, user-facing, or scope-changing."
        )

    return (
        f"{base}"
        f"{mode_clause}{packet_clause} "
        "If you expand beyond the packet, write the reason in the next ORCH-CHECKPOINT. "
        f"Resume the orchestrator for {target}"
    )


def artifact_index_for_ticket(ticket_context: dict) -> Path | None:
    ticket_path_raw = str(ticket_context.get("path", "") or "").strip()
    if not ticket_path_raw:
        return None
    ticket_path = Path(ticket_path_raw).expanduser().resolve()
    ticket_data = parse_frontmatter_map(ticket_path)
    project = str(ticket_data.get("project", "")).strip().strip('"')
    if not project:
        return None

    parts = ticket_path.parts
    if "vault" not in parts:
        return None
    vault_idx = parts.index("vault")
    platform_root = Path(*parts[:vault_idx]) if vault_idx > 0 else Path("/")
    if "clients" in parts[vault_idx + 1 :]:
        client_idx = parts.index("clients", vault_idx + 1)
        if len(parts) <= client_idx + 1:
            return None
        client = parts[client_idx + 1]
        return platform_root / "vault" / "clients" / client / "projects" / f"{project}.derived" / "artifact-index.yaml"
    return platform_root / "vault" / "projects" / f"{project}.derived" / "artifact-index.yaml"


def load_project_code_context(ticket_context: dict) -> dict:
    artifact_index_path = artifact_index_for_ticket(ticket_context)
    if artifact_index_path is None or not artifact_index_path.exists():
        return {"available": False, "artifact_index_path": str(artifact_index_path) if artifact_index_path else "", "workspaces": []}

    data = load_yaml_map(artifact_index_path)
    workspaces = data.get("code_workspaces") or []
    if not isinstance(workspaces, list):
        workspaces = []
    code_state = load_json_map(PROJECT_CODE_INDEX_STATE_PATH)
    state_workspaces = code_state.get("workspaces") if isinstance(code_state, dict) else {}
    state_workspaces = state_workspaces if isinstance(state_workspaces, dict) else {}

    normalized_workspaces: list[dict] = []
    for workspace in workspaces:
        if not isinstance(workspace, dict):
            continue
        row = dict(workspace)
        root_path = Path(str(row.get("root", "") or "")).expanduser()
        row["exists"] = root_path.exists()
        live_git_root = discover_live_git_root(root_path) if row["exists"] else None
        if live_git_root:
            row["root"] = str(live_git_root)
            row["git_repo"] = True
            ok_branch, branch = run_git_capture(["git", "branch", "--show-current"], live_git_root)
            ok_head, head = run_git_capture(["git", "rev-parse", "HEAD"], live_git_root)
            row["branch"] = branch if ok_branch else str(row.get("branch", "") or "")
            row["head"] = head if ok_head else str(row.get("head", "") or "")

        key = str(row.get("key", "") or row.get("root", "")).strip()
        state_entry = state_workspaces.get(key, {}) if isinstance(state_workspaces, dict) else {}
        state_entry = state_entry if isinstance(state_entry, dict) else {}
        last_status = str(state_entry.get("last_status", "") or row.get("gitnexus_last_status", "") or "").strip()
        last_head = str(state_entry.get("head", "") or row.get("gitnexus_last_head", "") or "").strip()
        row["gitnexus_last_status"] = last_status
        row["gitnexus_last_head"] = last_head
        row["gitnexus_last_updated"] = str(
            state_entry.get("updated_at", "") or row.get("gitnexus_last_updated", "") or ""
        ).strip()
        row["gitnexus_index_present"] = (
            bool((Path(str(row.get("root", "") or "")) / ".gitnexus").exists()) if row.get("exists") else bool(row.get("gitnexus_index_present"))
        )
        row["gitnexus_ready"] = bool(
            row.get("git_repo")
            and row.get("gitnexus_enabled")
            and row.get("head")
            and last_status == "refreshed"
            and last_head == row.get("head")
        )
        normalized_workspaces.append(row)

    live = [workspace for workspace in normalized_workspaces if workspace.get("exists")]
    analyzable = [
        workspace
        for workspace in live
        if workspace.get("git_repo") and workspace.get("gitnexus_enabled") and workspace.get("gitnexus_ready")
    ]
    return {
        "available": bool(normalized_workspaces),
        "artifact_index_path": str(artifact_index_path),
        "workspaces": normalized_workspaces,
        "live_workspaces": live,
        "analyzable_workspaces": analyzable,
    }


def merge_ticket_tags(explicit_tags: list[str] | None, ticket_context: dict) -> list[str]:
    if str(ticket_context.get("path", "") or "").strip():
        return list(ticket_context.get("tags", []))

    merged = []
    seen = set()
    for source in (ticket_context.get("tags", []), normalize_tags(explicit_tags)):
        for tag in source:
            if tag in seen:
                continue
            seen.add(tag)
            merged.append(tag)
    return merged


def effective_task_type(ticket_context: dict | None, cli_task_type: str | None) -> str:
    ticket_task_type = str((ticket_context or {}).get("task_type", "") or "").strip().lower()
    if ticket_task_type:
        return "code_build" if ticket_task_type == "build" else ticket_task_type

    if str((ticket_context or {}).get("path", "") or "").strip():
        return "general"

    task_type = str(cli_task_type or "").strip().lower()
    if task_type == "build":
        return "code_build"
    return task_type or "general"


def determine_design_context(
    task_type: str,
    prompt: str,
    contract: dict,
    ticket_context: dict,
    ticket_tags: list[str],
) -> dict:
    tags = set(ticket_tags)
    text = " ".join(part for part in (ticket_context.get("title", ""), prompt) if part).strip()
    ui_work = bool(ticket_context.get("ui_work")) or ("ui-design" in tags)
    if not ui_work:
        if task_type in {"creative_brief", "self_review", "quality_check", "visual_review", "artifact_polish_review"} and UI_SURFACE_HINT_RE.search(text):
            ui_work = True
        elif task_type == "code_build" and STITCH_CODEBUILD_HINT_RE.search(text):
            ui_work = True
    public_surface = bool(ticket_context.get("public_surface")) or bool(PUBLIC_SURFACE_HINT_RE.search(text))
    page_contract_required = bool(ticket_context.get("page_contract_required")) or bool(PAGE_CONTRACT_HINT_RE.search(text))
    route_family_required = (
        bool(ticket_context.get("route_family_required"))
        or bool(ticket_context.get("page_contract_required"))
        or ("route-family-required" in tags)
        or bool(ROUTE_FAMILY_HINT_RE.search(text))
    )
    existing_surface_redesign = bool(ticket_context.get("existing_surface_redesign")) or ("existing-surface-redesign" in tags) or bool(
        EXISTING_SURFACE_REDESIGN_HINT_RE.search(text)
    )
    if not ui_work:
        return {
            "ui_work": False,
            "design_mode": "",
            "requested_mode": "",
            "requires_stitch": False,
            "reason": "No UI design contract detected.",
            "public_surface": public_surface,
            "page_contract_required": page_contract_required,
            "route_family_required": route_family_required,
            "existing_surface_redesign": existing_surface_redesign,
        }

    explicit_mode = normalize_design_mode(ticket_context.get("design_mode", ""))
    explicit_mode_source = "ticket metadata"
    if not explicit_mode and ticket_context.get("stitch_required"):
        explicit_mode = "stitch_required"
        explicit_mode_source = "ticket frontmatter stitch_required flag"
    if not explicit_mode and tags & STITCH_REQUIRED_TAGS:
        explicit_mode = "stitch_required"
        explicit_mode_source = "ticket tags"
    if not explicit_mode and tags & IMPLEMENTATION_ONLY_TAGS:
        explicit_mode = "implementation_only"
        explicit_mode_source = "ticket tags"

    low_risk_implementation = bool(tags & IMPLEMENTATION_ONLY_TAGS) or bool(LOW_RISK_UI_CHANGE_HINT_RE.search(text))
    high_complexity_ui = bool(MULTI_SCREEN_COMPLEXITY_HINT_RE.search(text))
    rejected_visual_work = bool(VISUAL_REJECTION_HINT_RE.search(text))
    stitch_exempt = bool(tags & STITCH_EXEMPT_TAGS) and not explicit_mode

    if explicit_mode:
        requested_mode = explicit_mode
        reason = f"{explicit_mode_source.capitalize()} selects design_mode `{explicit_mode}`."
    elif low_risk_implementation and contract.get("implementation_only_allowed_for_low_risk_ui_changes", True) and not public_surface and not existing_surface_redesign:
        requested_mode = "implementation_only"
        reason = "Prompt/tags indicate low-risk UI implementation or polish on an approved design."
    elif contract.get("concept_required_for_frontend_design", True):
        requested_mode = "concept_required"
        reason = "User-facing UI work defaults to concept_required."
    else:
        requested_mode = ""
        reason = "Platform concept contract disabled for frontend design."

    effective_mode = requested_mode
    escalation_reason = ""

    if not stitch_exempt:
        if existing_surface_redesign and public_surface and contract.get("stitch_required_for_existing_public_surface_redesigns", False):
            if effective_mode != "stitch_required":
                escalation_reason = "Existing public-surface redesigns are Stitch-governed by policy."
            effective_mode = "stitch_required"
        elif (
            existing_surface_redesign
            and route_family_required
            and contract.get("stitch_required_for_existing_route_family_redesigns", False)
        ):
            if effective_mode != "stitch_required":
                escalation_reason = "Existing route-family operator-surface redesigns are Stitch-governed by policy."
            effective_mode = "stitch_required"
        elif (
            not explicit_mode
            and (high_complexity_ui or rejected_visual_work)
            and contract.get("stitch_required_for_multi_screen_high_complexity_ui", False)
        ):
            if effective_mode != "stitch_required":
                escalation_reason = "High-ambiguity, rejected, or multi-screen UI work is Stitch-governed by policy."
            effective_mode = "stitch_required"

    if not effective_mode and contract.get("concept_required_for_frontend_design", True):
        effective_mode = "concept_required"

    if stitch_exempt and effective_mode == "stitch_required":
        effective_mode = "concept_required"
        escalation_reason = "Ticket tags explicitly exempt this task from Stitch enforcement."

    if escalation_reason:
        reason = f"{reason} {escalation_reason}"

    return {
        "ui_work": True,
        "design_mode": effective_mode,
        "requested_mode": requested_mode,
        "requires_stitch": effective_mode == "stitch_required",
        "codex_code_build_requires_sealed_stitch_package": bool(
            contract.get("stitch_required_codex_code_build_requires_sealed_design_package", False)
        ),
        "reason": reason,
        "public_surface": public_surface,
        "page_contract_required": page_contract_required,
        "route_family_required": route_family_required,
        "existing_surface_redesign": existing_surface_redesign,
    }


def determine_stitch_context(
    task_type: str,
    prompt: str,
    contract: dict,
    ticket_context: dict,
    ticket_tags: list[str],
) -> dict:
    return determine_design_context(task_type, prompt, contract, ticket_context, ticket_tags)


def determine_nexus_context(task_type: str, prompt: str, ticket_context: dict) -> dict:
    text = " ".join(part for part in (ticket_context.get("title", ""), prompt) if part).strip()
    task_requires_nexus = task_type in NEXUS_DISCOVERY_TASK_TYPES
    hint_requires_nexus = task_type == "general" and bool(NEXUS_DISCOVERY_HINT_RE.search(text))
    nexus_optional = task_requires_nexus or hint_requires_nexus

    if task_requires_nexus:
        reason = (
            f"Task type `{task_type}` is discovery-heavy, so project-scoped retrieval should lead "
            "and Nexus can help only if a curated vault is already open."
        )
    elif hint_requires_nexus:
        reason = "Prompt/title indicates vault discovery or related-context lookup; use project-scoped retrieval first."
    else:
        reason = "No Nexus-specific discovery hint detected."

    return {
        "nexus_first": False,
        "nexus_optional": nexus_optional,
        "reason": reason,
    }


def determine_code_intelligence_context(task_type: str, prompt: str, ticket_context: dict) -> dict:
    text = " ".join(part for part in (ticket_context.get("title", ""), prompt) if part).strip().lower()
    code_task = task_type in CODE_INTELLIGENCE_TASK_TYPES or any(
        hint in text for hint in ("refactor", "module", "component", "api", "schema", "rename", "impact", "blast radius")
    )
    project_code = load_project_code_context(ticket_context) if code_task else {"available": False, "artifact_index_path": "", "workspaces": [], "live_workspaces": [], "analyzable_workspaces": []}
    if not code_task:
        reason = "No code-intelligence hint detected."
    elif not project_code.get("available"):
        reason = "Code task detected, but no project code workspace is registered yet."
    elif project_code.get("analyzable_workspaces"):
        reason = "Use GitNexus MCP for structural code questions after orienting from project context."
    else:
        reason = "Code workspaces exist, but none are analyzable through GitNexus yet."
    return {
        "code_task": code_task,
        "reason": reason,
        **project_code,
    }


def determine_hybrid_retrieval_context(task_type: str, prompt: str, ticket_context: dict) -> dict:
    title = str(ticket_context.get("title", "") or "").strip()
    complexity = str(ticket_context.get("complexity", "") or "").strip().lower()
    text = " ".join(part for part in (title, prompt) if part).strip()
    clean_room = task_type in HYBRID_RETRIEVAL_CLEAN_ROOM_TASK_TYPES or bool(
        re.search(r"\b(clean-room|clean room|first-impression|first impression)\b", text, re.IGNORECASE)
    )
    deep_task = complexity == "deep"
    task_type_requires = task_type in HYBRID_RETRIEVAL_ESCALATION_TASK_TYPES
    cross_cutting_hint = bool(CROSS_CUTTING_RETRIEVAL_HINT_RE.search(text))
    required = not clean_room and (deep_task or task_type_requires or cross_cutting_hint)

    reasons: list[str] = []
    if clean_room:
        reasons.append("Task is explicitly clean-room/first-impression scoped, so broader retrieval should stay minimal.")
    else:
        if deep_task:
            reasons.append("Ticket complexity is `deep`.")
        if task_type_requires:
            reasons.append(f"Task type `{task_type}` usually spans multiple project artifacts.")
        if cross_cutting_hint:
            reasons.append("Prompt/title references cross-cutting review, proof, or remediation work.")

    query_count = 3 if deep_task or (task_type_requires and cross_cutting_hint) else 2
    return {
        "required": required,
        "clean_room": clean_room,
        "query_count": query_count,
        "reason": " ".join(reasons).strip() or "No targeted hybrid-retrieval escalation needed.",
    }


def build_runtime_preamble(
    local_now: str,
    contract: dict,
    design_context: dict | None = None,
    ticket_context: dict | None = None,
    nexus_context: dict | None = None,
    code_intelligence_context: dict | None = None,
    hybrid_retrieval_context: dict | None = None,
) -> str:
    lines = [
        build_quality_contract_preamble(local_now, contract),
        "",
        (
            "For active projects with derived context artifacts, prefer project-scoped hybrid retrieval first: exact pointers from the current "
            "context and artifact index, then semantic text search over the curated project corpus, then "
            "project-scoped media search over the image-evidence index. Use broader semantic search for "
            "cross-project conceptual lookups and keyword search for exact matches. If a curated Nexus/Obsidian "
            "vault is already open, you may use Nexus MCP as an accelerator for backlinks and link traversal, "
            "but it is optional and not the primary path. If the task is explicitly clean-room (for example stress tests, "
            "phase-level adversarial probes, or artifact-polish first-impression review), keep prior-project retrieval minimal "
            "and follow the clean-room brief. "
            "Once you know the exact target files, read them directly."
        ),
    ]

    ticket_context = ticket_context or {}
    design_context = design_context or {"ui_work": False, "design_mode": "", "reason": "No UI design contract detected."}
    nexus_context = nexus_context or {"nexus_first": False, "nexus_optional": False, "reason": "No Nexus-specific discovery hint detected."}
    code_intelligence_context = code_intelligence_context or {"code_task": False, "reason": "No code-intelligence hint detected.", "workspaces": [], "analyzable_workspaces": []}
    hybrid_retrieval_context = hybrid_retrieval_context or {
        "required": False,
        "clean_room": False,
        "query_count": 0,
        "reason": "No targeted hybrid-retrieval escalation needed.",
    }
    if hybrid_retrieval_context.get("required"):
        query_count = max(1, int(hybrid_retrieval_context.get("query_count") or 1))
        lines.extend(
            [
                "",
                "Hybrid retrieval escalation for this task:",
                f"Reason: {hybrid_retrieval_context.get('reason', 'This task is broad enough that project-scoped retrieval should be deliberate.')}",
                f"- Before broad repo wandering, run {query_count} targeted project-scoped hybrid retrieval quer{'y' if query_count == 1 else 'ies'}.",
                "- Derive those queries from the ticket title, acceptance criteria, and current phase goal rather than browsing aimlessly.",
                "- Keep the output tight: write a short retrieval digest of the artifacts, proofs, or surfaces that actually matter for this task.",
                "- Good query shapes: `surface + requirement`, `phase goal + risk`, `evidence/proof + artifact family`, `review finding + source of truth`.",
            ]
        )
    elif hybrid_retrieval_context.get("clean_room"):
        lines.extend(
            [
                "",
                "Clean-room retrieval note for this task:",
                f"Reason: {hybrid_retrieval_context.get('reason', 'Task is explicitly clean-room scoped.')}",
                "- Do not widen into broad project retrieval unless the brief explicitly authorizes it.",
                "- Use only the exact assigned artifacts, runtime surface, and constraints needed to preserve the clean-room posture.",
            ]
        )
    if nexus_context.get("nexus_optional"):
        lines.extend(
            [
                "",
                "Optional Nexus assist for this task: if a curated Nexus/Obsidian vault is already open, you may use Nexus MCP for backlinks and link traversal after checking the project's derived context artifacts.",
                f"Reason: {nexus_context.get('reason', 'This task may benefit from link-graph acceleration.')}",
                "- Do not block on Nexus availability; fall back to project-scoped retrieval, direct file reads, wiki links, and `## See Also` sections immediately.",
            ]
        )

    if code_intelligence_context.get("code_task"):
        lines.extend(
            [
                "",
                "Code-intelligence contract for this task:",
                f"Reason: {code_intelligence_context.get('reason', 'Code task detected.')}",
            ]
        )
        analyzable = code_intelligence_context.get("analyzable_workspaces") or []
        workspaces = code_intelligence_context.get("workspaces") or []
        if analyzable:
            roots = ", ".join(f"`{workspace.get('root', '')}`" for workspace in analyzable[:3])
            lines.extend(
                [
                    f"- Registered GitNexus workspaces: {roots}",
                    "- Use project truth first (`current-context.md`, `artifact-index.yaml`, hybrid project retrieval), then GitNexus MCP for code structure questions.",
                    "- Preferred GitNexus MCP flow: read `gitnexus://repos` or the repo context resource, then use `query`, `context`, `impact`, or `detect_changes` for structural analysis.",
                    "- GitNexus complements direct file reads; it does not replace reading the exact files you are editing.",
                ]
            )
        elif workspaces:
            roots = ", ".join(f"`{workspace.get('root', '')}`" for workspace in workspaces[:3])
            lines.extend(
                [
                    f"- Known code workspaces: {roots}",
                    "- No live GitNexus-ready workspace yet. If the repo scaffold appears during this task, refresh the code index before relying on code-graph context.",
                ]
            )
        else:
            lines.append("- No code workspace is registered yet; rely on project context and direct file reads until one exists.")

    if str(ticket_context.get("complexity", "")).strip().lower() == "deep":
        lines.extend(
            [
                "",
                "Deep execution reporting contract for this task:",
                "- If the work log does not already contain a `PLAN — Decomposed into N sub-steps:` entry, your first work-log update must add one with 3-7 concrete, stable step labels.",
                "- Reuse those exact step labels in later checkpoints so the dashboard and the next agent can track progress mechanically.",
                "- Avoid vague progress updates like `Sub-step 1/2` with no readable step names when you can name the work precisely.",
                "- If the execution shape changes materially, append a revised PLAN entry before continuing instead of silently reusing old step numbers for different work.",
            ]
        )

    if design_context.get("ui_work"):
        mode = str(design_context.get("design_mode") or "")
        task_kind = str(ticket_context.get("task_type") or "").strip().lower()
        mode_label = {
            "stitch_required": "STITCH REQUIRED",
            "concept_required": "CONCEPT REQUIRED",
            "implementation_only": "IMPLEMENTATION ONLY",
        }.get(mode, "UI WORK")
        lines.extend(
            [
                "",
                f"UI design contract: {mode_label} for this task.",
                f"Reason: {design_context.get('reason', 'User-facing UI work detected.')}",
                "- Runtime screenshot proof is mandatory for any user-visible change. Do not rely on code structure or prose alone.",
                "- Interactive or multi-step user-visible flows should ship with a QC-stage walkthrough video, not just screenshots.",
                "- Upstream-owned visual artifacts must exist before later review stages can rely on them. If a Stitch/design/build stage was supposed to leave behind benchmark screenshots or comparable visual proof, missing files are a real defect for that producing stage.",
            ]
        )
        if contract.get("qc_runtime_screenshot_reference_required", True):
            lines.append("- Any stage that cites runtime screenshots as evidence must name the concrete screenshot filenames. QC owns mandatory runtime screenshot capture by default unless the brief explicitly assigns it earlier.")
        if contract.get("runtime_screenshot_hashes_are_copy_integrity_only", True):
            lines.append("- Runtime screenshot/video hashes prove copy integrity for the same captured artifact; they must not be used as byte-identical visual-preservation requirements across separate dynamic UI captures.")
        if contract.get("dynamic_ui_preservation_requires_semantic_gate", True):
            lines.append("- Existing dynamic UI preservation must be judged by a semantic preservation gate: route/state reachable, protected labels and sections visible, screenshots fresh/nonblank, required themes covered, and deterministic source/manifest artifacts checked where exact identity is meaningful.")
        if contract.get("screenshot_laundering_for_gate_pass_prohibited", True):
            lines.append("- Do not copy stale screenshots into a new evidence bundle to force matching hashes. Capture fresh evidence and document intentional visual changes instead.")
        if task_kind == "self_review":
            lines.append("- Self-review does not own QC-stage runtime screenshot/video capture unless the brief explicitly assigns it. Self-review DOES own checking that upstream-required visual artifacts already exist; if they are missing, verdict cannot be `Ship It`.")
        elif task_kind == "quality_check":
            lines.append("- QC owns runtime screenshot and walkthrough capture for interactive browser/native flows. Missing QC-stage screenshot/video artifacts are QC defects, not optional niceties.")
        elif task_kind == "visual_review":
            lines.append("- This is the authoritative visual judgment pass for governed UI work. Inspect the actual runtime screenshots and review-surface image evidence named by QC/review-pack artifacts; filename existence alone is not enough.")
            lines.append("- Write a structured visual verdict with screenshot filenames, parity decisions, and explicit anti-pattern calls (generic admin drift, duplicate shell chrome, missing composition anchors).")

        if mode == "stitch_required":
            if design_context.get("implementation_from_sealed_stitch_package"):
                package_ref = str(design_context.get("sealed_design_package_ref", "")).strip()
                package_path = str(design_context.get("sealed_design_package_path", "")).strip()
                lines.extend(
                    [
                        "- This is a Codex implementation pass from a sealed Stitch/design package, not a live Stitch design pass.",
                        "- Use the sealed Stitch/design package as the source of truth for layout, visual states, screen IDs, and artifact names.",
                        "- Do not call live Stitch MCP or generate new Stitch screens unless the ticket explicitly changes into a design-package task.",
                        "- Compare runtime screenshots against the sealed package and cite the relevant package artifacts in the review pack.",
                    ]
                )
                if package_ref:
                    lines.append(f"- Sealed Stitch/design package reference: `{package_ref}`.")
                if package_path and package_path != package_ref:
                    lines.append(f"- Resolved sealed package path: `{package_path}`.")
            else:
                lines.extend(
                    [
                        "- Use Stitch MCP via the stitch-design skill as the source of truth for this UI work.",
                        "- Create or update `.stitch/DESIGN.md` for the relevant UI surface before claiming the design is complete.",
                        "- Generate named Stitch screens for major states and keep those screen IDs in the brief/QC evidence trail.",
                        "- Save/download Stitch HTML and screenshot artifacts under `.stitch/designs/` so delivery gates can verify them mechanically.",
                        "- If the brief or media contract calls for benchmark comparisons or named design screenshots, capture them during the Stitch/design stage and save them under `.stitch/designs/benchmarks/` or another clearly named subdirectory before handing off to self-review/QC.",
                    ]
                )
            if contract.get("stitch_qc_reference_required", True):
                lines.append("- Self-review and QC must compare the built UI against Stitch targets and cite the relevant screen IDs or screen names.")
            if contract.get("stitch_block_on_unavailable", False) and not design_context.get("implementation_from_sealed_stitch_package"):
                lines.append("- If Stitch MCP is unavailable, stop and mark the task blocked. Do not replace Stitch with ad-hoc CSS or prose-only visual specs.")
        elif mode == "concept_required":
            lines.extend(
                [
                    "- Establish a real concept source of truth before implementation: references, visual targets, narrative intent, and concrete structural anchors.",
                    "- Do not let a generic template or the current DOM stand in for design intent.",
                    "- QC must compare runtime screenshots against the concept package, not just against acceptance-criteria checklists.",
                ]
            )
        elif mode == "implementation_only":
            lines.extend(
                [
                    "- This is low-risk UI implementation/polish against an already-approved design or source of truth, not a license to invent a new visual direction.",
                    "- Preserve the approved concept and document any meaningful deviation explicitly.",
                ]
            )

        if mode in {"stitch_required", "concept_required"} and contract.get("visual_quality_bar_required", True):
            lines.append("- The brief must define an explicit Visual Quality Bar. Generic SaaS layouts, card soup, weak hierarchy, or “clean enough” aesthetics are failures, not acceptable defaults.")
        if design_context.get("route_family_required") and mode in {"stitch_required", "concept_required"}:
            if contract.get("route_family_section_required_for_operator_surfaces", True):
                lines.append("- This surface is route-family-governed. The brief must include a Route Family section naming the approved sibling surfaces, shared hierarchy, and anti-patterns that would make the page feel like a different product.")
            if contract.get("composition_anchors_required_for_route_family_surfaces", True):
                lines.append("- Route-family surfaces must define Composition Anchors too. Matching colors/tokens is not enough if the layout drifts into generic admin chrome.")
        if design_context.get("public_surface") and mode in {"stitch_required", "concept_required"} and contract.get("narrative_structure_required_for_public_surfaces", True):
            lines.append("- This is a public-facing surface. The brief/design must include a Narrative Structure section and a stronger product argument than a feature inventory.")
            if contract.get("separate_design_stage_for_public_surfaces", True):
                lines.append("- Separate design direction from implementation: establish the concept source of truth first, then build against it.")
        if design_context.get("public_surface") and mode in {"stitch_required", "concept_required"} and contract.get("composition_anchors_required_for_public_surfaces", True):
            lines.append("- Public-facing UI must define Composition Anchors: 3-7 concrete structural ideas that are visible in runtime screenshots and survive implementation.")
        existing_surface_redesign = bool(design_context.get("existing_surface_redesign"))
        if existing_surface_redesign and mode in {"stitch_required", "concept_required"} and contract.get("replace_vs_preserve_required_for_existing_surface_redesigns", True):
            lines.append("- Existing-surface redesign detected. Treat the current page as untrusted design input, not the baseline to preserve by default.")
            lines.append("- The brief must include a Replace vs Preserve section that explicitly names what wiring/behavior survives and what layout/composition is being replaced.")
        if existing_surface_redesign and design_context.get("public_surface") and mode in {"stitch_required", "concept_required"} and contract.get("greenfield_concept_required_for_existing_public_surfaces", True):
            lines.append("- Do a greenfield concept pass first: define the new public-facing surface as if the old page did not exist, then map that concept back into the current codebase.")
        if existing_surface_redesign and design_context.get("public_surface") and mode == "stitch_required" and contract.get("runtime_stitch_parity_required_for_public_surface_redesigns", False):
            lines.append("- Copy/colors/section order are not enough. The built runtime must preserve the primary above-the-fold composition anchors from the Stitch concept.")
        if design_context.get("route_family_required") and existing_surface_redesign and contract.get("route_family_parity_required_in_qc", True):
            lines.append("- QC must explicitly audit same-product-family parity for this route. A generic admin split view under correct tokens is still a failure.")
        if design_context.get("page_contract_required") and contract.get("page_contract_required_for_nav_surfaces", True):
            lines.append("- This surface requires a Page Contract section defining its core sections, primary jobs-to-be-done, and state coverage before implementation.")
            if contract.get("dangerous_actions_must_be_nested", True):
                lines.append("- Dangerous actions must live inside a clearly labeled danger zone within a broader settings/account surface. A top-level nav page must not collapse to a single destructive action.")
    return "\n".join(lines)


def build_executor_environment(
    *,
    project: str,
    client: str,
    task_type: str,
    ticket_path: Path | None,
) -> dict[str, str]:
    env = os.environ.copy()
    if project:
        env["AGENT_PLATFORM_PROJECT"] = project
    if client:
        env["AGENT_PLATFORM_CLIENT"] = client
    if task_type:
        env["AGENT_PLATFORM_TASK_TYPE"] = task_type
    if ticket_path:
        env["AGENT_PLATFORM_TICKET_ID"] = ticket_identifier(ticket_path)
        env["AGENT_PLATFORM_TICKET_PATH"] = str(ticket_path)
    return env


def split_frontmatter(text: str) -> tuple[str, str]:
    if text.startswith("---\n"):
        parts = text.split("---", 2)
        if len(parts) == 3:
            return parts[1].strip("\n"), parts[2].lstrip("\n")
    return "", text


def atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=path.parent) as handle:
        handle.write(content)
        temp_name = handle.name
    os.replace(temp_name, path)


def format_frontmatter_value(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, list):
        inner = ", ".join(format_frontmatter_value(item) for item in value)
        return f"[{inner}]"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value)
    if re.fullmatch(r"[A-Za-z0-9_./:@+\-]+", text):
        return text
    return json.dumps(text)


def update_markdown_frontmatter(path: Path, updates: dict[str, object], remove_keys: set[str] | None = None) -> None:
    remove_keys = remove_keys or set()
    text = path.read_text(encoding="utf-8")
    existing_frontmatter, body = split_frontmatter(text)
    frontmatter_lines = existing_frontmatter.splitlines() if existing_frontmatter else []

    key_to_index: dict[str, int] = {}
    ordered_keys: list[str] = []
    for idx, raw_line in enumerate(frontmatter_lines):
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#") or ":" not in stripped:
            continue
        key = stripped.split(":", 1)[0].strip()
        key_to_index[key] = idx
        ordered_keys.append(key)

    for key, value in updates.items():
        rendered = f"{key}: {format_frontmatter_value(value)}"
        if key in key_to_index:
            frontmatter_lines[key_to_index[key]] = rendered
        else:
            frontmatter_lines.append(rendered)
            key_to_index[key] = len(frontmatter_lines) - 1
            ordered_keys.append(key)

    if remove_keys:
        frontmatter_lines = [
            raw_line
            for raw_line in frontmatter_lines
            if raw_line.strip().split(":", 1)[0].strip() not in remove_keys
        ]

    rendered_frontmatter = "---\n" + "\n".join(frontmatter_lines).rstrip() + "\n---\n\n"
    atomic_write_text(path, rendered_frontmatter + body.lstrip("\n"))


def append_ticket_work_log(path: Path, message: str) -> None:
    text = path.read_text(encoding="utf-8")
    entry = f"- {message}"
    if "## Work Log" in text:
        updated = text.rstrip() + "\n" + entry + "\n"
    else:
        updated = text.rstrip() + "\n\n## Work Log\n\n" + entry + "\n"
    atomic_write_text(path, updated)


def current_local_iso() -> str:
    return datetime.now().astimezone().strftime(ISO_FMT)


def load_json_map(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def write_json_map(path: Path, payload: dict) -> None:
    atomic_write_text(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def parse_local_iso(raw_value: object) -> datetime | None:
    text = str(raw_value or "").strip()
    if not text:
        return None
    try:
        return datetime.strptime(text, ISO_FMT)
    except ValueError:
        return None


def ticket_client_slug(ticket_path: Path) -> str:
    parts = ticket_path.resolve().parts
    if "clients" not in parts:
        return "_platform"
    client_idx = parts.index("clients")
    if len(parts) <= client_idx + 1:
        return "_platform"
    return parts[client_idx + 1]


def stitch_auth_snapshot_path(ticket_path: Path) -> Path:
    client = ticket_client_slug(ticket_path)
    ticket_id = infer_ticket_id(ticket_path).lower()
    date = datetime.now().astimezone().strftime("%Y-%m-%d")
    return REPO_ROOT / "vault" / "clients" / client / "snapshots" / f"{date}-stitch-auth-{ticket_id}.md"


def stitch_auth_state() -> dict:
    return load_json_map(STITCH_AUTH_STATE_PATH)


def write_stitch_auth_state(payload: dict) -> None:
    write_json_map(STITCH_AUTH_STATE_PATH, payload)


def stitch_auth_flow_is_fresh(state: dict) -> bool:
    if str(state.get("status", "")).strip().lower() != "pending":
        return False
    requested_at = parse_local_iso(state.get("requested_at"))
    if requested_at is None:
        return False
    age = datetime.now().astimezone().replace(tzinfo=None) - requested_at
    return age.total_seconds() <= STITCH_AUTH_FLOW_TTL_SECS


def run_claude_capture(command: list[str], *, timeout_secs: int = 30) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=str(STITCH_CLAUDE_CWD),
        text=True,
        capture_output=True,
        check=False,
        timeout=timeout_secs,
    )


def load_project_mcp_config() -> dict:
    path = REPO_ROOT / ".mcp.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def stitch_server_uses_local_proxy() -> bool:
    servers = load_project_mcp_config().get("mcpServers")
    if not isinstance(servers, dict):
        return False
    stitch = servers.get("stitch")
    if not isinstance(stitch, dict):
        return False
    command = str(stitch.get("command", "")).strip().lower()
    args = stitch.get("args") or []
    command_name = Path(command.replace("\\", "/")).name
    if command_name not in {"node", "nodejs", "node.exe", "nodejs.exe"}:
        return False
    resolved_args = [str(arg) for arg in args if isinstance(arg, (str, Path))]
    proxy_path = str((REPO_ROOT / STITCH_PROXY_SERVER_RELATIVE).resolve())
    return any(str(Path(arg).resolve()) == proxy_path for arg in resolved_args if arg)


def read_repo_env_map() -> dict[str, str]:
    env_path = REPO_ROOT / ".env"
    if not env_path.exists():
        return {}
    values: dict[str, str] = {}
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        parsed = parse_scalar(value)
        values[key.strip()] = "" if parsed is None else str(parsed).strip()
    return values


def stitch_api_key_present() -> bool:
    env_value = os.environ.get("STITCH_API_KEY", "").strip()
    if env_value:
        return True
    return bool(read_repo_env_map().get("STITCH_API_KEY", "").strip())


def get_stitch_mcp_status() -> dict:
    if stitch_server_uses_local_proxy() and not stitch_api_key_present():
        return {
            "status": "api_key_missing",
            "detail": (
                "Project-local Stitch MCP proxy is configured, but STITCH_API_KEY is missing. "
                f"Add STITCH_API_KEY to {REPO_ROOT / '.env'} or export it before starting Claude."
            ),
        }
    command = ["claude", "mcp", "get", "stitch"]
    try:
        result = run_claude_capture(command, timeout_secs=20)
    except FileNotFoundError:
        return {"status": "cli_missing", "detail": "Claude CLI is not installed or not on PATH."}
    except subprocess.TimeoutExpired:
        return {"status": "timeout", "detail": "Timed out while checking Stitch MCP status."}

    output = "\n".join(part for part in (result.stdout, result.stderr) if part).strip()
    lower = output.lower()
    if "needs authentication" in lower:
        status = "needs_auth"
    elif "connected" in lower:
        status = "connected"
    elif "failed to connect" in lower:
        status = "failed"
    elif "not found" in lower:
        status = "missing"
    else:
        status = "unknown"
    return {"status": status, "detail": output, "returncode": result.returncode}


def get_codex_stitch_mcp_config_status(config_path: Path | None = None) -> dict:
    path = config_path or CODEX_CONFIG_PATH
    data, error = load_toml_map(path)
    if error:
        return {
            "status": "parse_error" if path.exists() else "missing",
            "detail": error,
            "config_path": str(path),
        }

    servers = data.get("mcp_servers")
    stitch = servers.get("stitch") if isinstance(servers, dict) else None
    if not isinstance(stitch, dict):
        return {
            "status": "missing",
            "detail": f"Codex target requires [mcp_servers.stitch] in {path}.",
            "config_path": str(path),
        }

    return {
        "status": "configured",
        "detail": f"Codex config contains [mcp_servers.stitch] in {path}.",
        "config_path": str(path),
        "command": stitch.get("command", ""),
        "args": stitch.get("args", []),
    }


def extract_stitch_auth_url(text: str) -> str:
    match = STITCH_OAUTH_URL_RE.search(text)
    if match:
        return match.group(0)
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line.startswith("https://accounts.google.com/o/oauth2/v2/auth?"):
            return line
    return ""


def request_stitch_auth_flow() -> dict:
    existing = stitch_auth_state()
    if stitch_auth_flow_is_fresh(existing) and existing.get("auth_url"):
        return existing

    session_id = str(uuid.uuid4())
    command = [
        "claude",
        "-p",
        "--session-id",
        session_id,
        "--permission-mode",
        "bypassPermissions",
        "--allowedTools=mcp__stitch__authenticate",
        "Call mcp__stitch__authenticate and reply with only the authorization URL.",
    ]
    result = run_claude_capture(command, timeout_secs=30)
    combined = "\n".join(part for part in (result.stdout, result.stderr) if part)
    auth_url = extract_stitch_auth_url(combined)
    state = {
        "status": "pending" if auth_url else "error",
        "session_id": session_id,
        "auth_url": auth_url,
        "requested_at": current_local_iso(),
        "detail": combined.strip(),
    }
    write_stitch_auth_state(state)
    return state


def format_stitch_auth_snapshot(ticket_path: Path, auth_url: str, state: dict) -> str:
    ticket_id = infer_ticket_id(ticket_path)
    requested_at = str(state.get("requested_at", current_local_iso()))
    return (
        "---\n"
        'type: snapshot\n'
        'subtype: stitch-auth\n'
        f'ticket: "{ticket_id}"\n'
        f"captured: {requested_at}\n"
        "---\n\n"
        f"# Stitch Authentication Required — {ticket_id}\n\n"
        "Stitch MCP is required for this ticket, but the current Claude MCP session needs OAuth authorization.\n\n"
        "## What To Do\n\n"
        "1. Open the authorization URL below in your browser.\n"
        "2. Complete Google authorization.\n"
        "3. If the browser lands on a localhost connection error page, copy the full callback URL from the address bar.\n"
        "4. Complete the auth handoff with:\n\n"
        "```bash\n"
        f"python scripts/agent_runtime.py complete-stitch-auth --callback-url '<PASTE_FULL_CALLBACK_URL>'\n"
        "```\n\n"
        "## Authorization URL\n\n"
        f"{auth_url}\n"
    )


def format_stitch_api_key_snapshot(ticket_path: Path, detail: str) -> str:
    ticket_id = infer_ticket_id(ticket_path)
    captured = current_local_iso()
    return (
        "---\n"
        'type: snapshot\n'
        'subtype: stitch-config\n'
        f'ticket: "{ticket_id}"\n'
        f"captured: {captured}\n"
        "---\n\n"
        f"# Stitch API Key Required — {ticket_id}\n\n"
        "This ticket requires Stitch MCP, and the project is configured to use the local API-key-backed Stitch proxy.\n\n"
        "## What To Do\n\n"
        "1. Open the platform repo `.env` file.\n"
        "2. Set `STITCH_API_KEY=<your-stitch-api-key>`.\n"
        "3. Re-run the ticket or let the orchestrator pick it up again. Fresh Claude executor runs will load the key automatically.\n"
        "4. Only restart the current desktop Claude/Codex session if you want this interactive session itself to see the new Stitch tools immediately.\n\n"
        "## Current Status\n\n"
        f"{detail}\n"
    )


def mark_ticket_waiting_for_stitch(ticket_path: Path, blocker: str, snapshot_path: Path, note: str) -> None:
    ticket_data = parse_frontmatter_map(ticket_path)
    previous_status = str(ticket_data.get("status", "")).strip().lower()
    blockers = normalize_blocked_by(ticket_data.get("blocked_by"))
    blockers = [
        entry
        for entry in blockers
        if entry not in {STITCH_AUTH_BLOCKER, STITCH_API_KEY_BLOCKER} or entry == blocker
    ]
    had_blocker = blocker in blockers
    if blocker not in blockers:
        blockers.append(blocker)
    now = current_local_iso()
    update_markdown_frontmatter(
        ticket_path,
        {
            "id": infer_ticket_id(ticket_path, ticket_data),
            "status": "waiting",
            "updated": now,
            "blocked_by": blockers,
        },
        remove_keys=EXECUTOR_FRONTMATTER_KEYS | {"completed"},
    )
    if previous_status != "waiting" or not had_blocker:
        append_ticket_work_log(
            ticket_path,
            f"{now}: {note} Waiting on `{blocker}`. Instructions: {snapshot_path}.",
        )


def reopen_ticket_after_stitch_blocker(ticket_path: Path, blocker: str) -> bool:
    ticket_data = parse_frontmatter_map(ticket_path)
    blockers = normalize_blocked_by(ticket_data.get("blocked_by"))
    if blocker not in blockers:
        return False
    remaining_blockers = [entry for entry in blockers if entry != blocker]
    now = current_local_iso()
    new_status = "blocked" if remaining_blockers else "open"
    update_markdown_frontmatter(
        ticket_path,
        {
            "id": infer_ticket_id(ticket_path, ticket_data),
            "status": new_status,
            "updated": now,
            "blocked_by": remaining_blockers,
        },
    )
    append_ticket_work_log(
        ticket_path,
        f"{now}: Stitch MCP prerequisite is ready. Removed `{blocker}` blocker and moved ticket to `{new_status}`.",
    )
    return True


def reopen_ticket_after_stitch_auth(ticket_path: Path) -> bool:
    return reopen_ticket_after_stitch_blocker(ticket_path, STITCH_AUTH_BLOCKER)


def normalize_target_agent(target_agent: str | None) -> str:
    return str(target_agent or "").strip().lower()


def resolve_stitch_design_package_ref(ticket_path: Path, ref: str) -> str | None:
    text = str(ref or "").strip().strip('"').strip("'")
    if not text:
        return None
    if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", text):
        # Remote design package references are acceptable as sealed handoff
        # pointers; downstream review gates still own content verification.
        return text

    candidate = Path(text).expanduser()
    candidates = [candidate] if candidate.is_absolute() else [
        REPO_ROOT / candidate,
        ticket_path.parent / candidate,
        ticket_path.parent.parent / candidate,
    ]
    for path in candidates:
        try:
            if path.exists():
                return str(path.resolve())
        except OSError:
            continue
    return None


def stitch_design_package_status(ticket_path: Path, ticket_data: dict | None = None) -> dict:
    data = ticket_data or parse_frontmatter_map(ticket_path)
    refs: list[str] = []
    for field in STITCH_DESIGN_PACKAGE_REF_FIELDS:
        refs.extend(frontmatter_string_list(data.get(field)))

    for ref in refs:
        resolved = resolve_stitch_design_package_ref(ticket_path, ref)
        if resolved is not None:
            return {
                "status": "ready",
                "ref": ref,
                "resolved_path": resolved,
            }

    ready_flags = [field for field in STITCH_DESIGN_PACKAGE_READY_FIELDS if bool(data.get(field))]
    if ready_flags and refs:
        return {
            "status": "missing_ref",
            "detail": (
                "Ticket declares a sealed Stitch/design package ready flag, "
                "but none of the recorded package paths resolve on disk."
            ),
            "refs": refs,
            "ready_flags": ready_flags,
        }
    if ready_flags:
        return {
            "status": "missing_ref",
            "detail": (
                "Ticket declares a sealed Stitch/design package ready flag, "
                "but no package reference field is recorded."
            ),
            "refs": [],
            "ready_flags": ready_flags,
        }
    return {
        "status": "missing",
        "detail": "No sealed Stitch/design package reference is recorded on this Codex implementation ticket.",
        "refs": refs,
        "fields_checked": list(STITCH_DESIGN_PACKAGE_REF_FIELDS),
    }


def codex_code_build_requires_sealed_stitch_package(
    task_type: str,
    design_context: dict,
    target_agent: str | None,
) -> bool:
    return (
        normalize_target_agent(target_agent) == "codex"
        and str(task_type or "").strip().lower() == "code_build"
        and bool(design_context.get("requires_stitch"))
        and bool(design_context.get("codex_code_build_requires_sealed_stitch_package", True))
    )


def mark_ticket_blocked_for_stitch_design_package(ticket_path: Path, package_status: dict) -> None:
    ticket_data = parse_frontmatter_map(ticket_path)
    previous_status = str(ticket_data.get("status", "")).strip().lower()
    blockers = normalize_blocked_by(ticket_data.get("blocked_by"))
    had_blocker = STITCH_DESIGN_PACKAGE_BLOCKER in blockers
    if not had_blocker:
        blockers.append(STITCH_DESIGN_PACKAGE_BLOCKER)
    now = current_local_iso()
    update_markdown_frontmatter(
        ticket_path,
        {
            "id": infer_ticket_id(ticket_path, ticket_data),
            "status": "blocked",
            "updated": now,
            "blocked_by": blockers,
        },
        remove_keys=EXECUTOR_FRONTMATTER_KEYS | {"completed"},
    )
    if previous_status != "blocked" or not had_blocker:
        append_ticket_work_log(
            ticket_path,
            (
                f"{now}: Runtime Stitch package guard blocked Codex implementation. "
                "This ticket is `stitch_required` and `task_type: code_build`, but no sealed "
                "Stitch/design package is recorded. Create/close a Claude-routed design-package "
                "ticket, then set `stitch_design_package_ref:` (or another accepted sealed package "
                f"field) to the generated artifact path before respawning. Detail: {package_status.get('detail', '')}"
            ),
        )


def ensure_stitch_ticket_ready(ticket_path: Path, design_context: dict, target_agent: str | None = None) -> dict:
    if not design_context.get("requires_stitch"):
        return {"status": "not_applicable"}

    agent = normalize_target_agent(target_agent)
    if agent not in {"claude", "codex"}:
        return {
            "status": "target_agent_unknown",
            "detail": (
                "Stitch preflight could not determine the spawning agent. "
                "Pass target_agent as 'claude' or 'codex' so the correct MCP config is checked."
            ),
            "target_agent": agent,
        }

    ticket_data = parse_frontmatter_map(ticket_path)
    task_type = str(ticket_data.get("task_type", "")).strip().lower()
    if codex_code_build_requires_sealed_stitch_package(task_type, design_context, agent):
        package_status = stitch_design_package_status(ticket_path, ticket_data)
        if package_status.get("status") == "ready":
            reopened_package = reopen_ticket_after_stitch_blocker(ticket_path, STITCH_DESIGN_PACKAGE_BLOCKER)
            return {
                "status": "ready",
                "target_agent": agent,
                "sealed_design_package_ref": package_status.get("ref", ""),
                "sealed_design_package_path": package_status.get("resolved_path", ""),
                "implementation_from_sealed_stitch_package": True,
                "reopened": reopened_package,
            }
        mark_ticket_blocked_for_stitch_design_package(ticket_path, package_status)
        return {
            "status": "stitch_design_package_required",
            "detail": package_status.get("detail", ""),
            "target_agent": agent,
            "blocker": STITCH_DESIGN_PACKAGE_BLOCKER,
            "package_status": package_status,
        }

    status = get_stitch_mcp_status()
    if status.get("status") == "connected":
        if agent == "codex":
            codex_status = get_codex_stitch_mcp_config_status()
            if codex_status.get("status") != "configured":
                return {
                    "status": "codex_config_missing",
                    "detail": (
                        "Claude MCP registry reports Stitch connected, but the target agent is Codex and "
                        f"{codex_status.get('detail', 'Codex Stitch MCP config is not ready')}"
                    ),
                    "target_agent": agent,
                    "claude_status": status,
                    "codex_status": codex_status,
                }
        reopened_api_key = reopen_ticket_after_stitch_blocker(ticket_path, STITCH_API_KEY_BLOCKER)
        reopened_auth = reopen_ticket_after_stitch_auth(ticket_path)
        return {
            **status,
            "status": "ready",
            "reopened": reopened_api_key or reopened_auth,
            "target_agent": agent,
        }

    if status.get("status") == "api_key_missing":
        snapshot_path = stitch_auth_snapshot_path(ticket_path)
        snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(snapshot_path, format_stitch_api_key_snapshot(ticket_path, str(status.get("detail", "")).strip()))
        mark_ticket_waiting_for_stitch(
            ticket_path,
            STITCH_API_KEY_BLOCKER,
            snapshot_path,
            "Stitch MCP requires STITCH_API_KEY for the local project proxy.",
        )
        return {
            "status": "api_key_required",
            "detail": status.get("detail", ""),
            "snapshot_path": str(snapshot_path),
        }

    auth_state = request_stitch_auth_flow()
    auth_url = str(auth_state.get("auth_url", "")).strip()
    snapshot_path = stitch_auth_snapshot_path(ticket_path)
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(snapshot_path, format_stitch_auth_snapshot(ticket_path, auth_url, auth_state))
    mark_ticket_waiting_for_stitch(
        ticket_path,
        STITCH_AUTH_BLOCKER,
        snapshot_path,
        "Stitch MCP requires OAuth authorization.",
    )
    return {
        "status": "auth_required",
        "detail": status.get("detail", ""),
        "auth_url": auth_url,
        "snapshot_path": str(snapshot_path),
        "session_id": auth_state.get("session_id", ""),
    }


def complete_stitch_auth(callback_url: str) -> dict:
    state = stitch_auth_state()
    session_id = str(state.get("session_id", "")).strip()
    if not session_id:
        return {"status": "missing_session", "detail": "No pending Stitch auth session is recorded."}

    command = [
        "claude",
        "-p",
        "--resume",
        session_id,
        "--permission-mode",
        "bypassPermissions",
        "--allowedTools=mcp__stitch__complete_authentication",
        (
            "Call mcp__stitch__complete_authentication with this exact callback URL and reply only with the final tool result: "
            f"{callback_url}"
        ),
    ]
    result = run_claude_capture(command, timeout_secs=30)
    combined = "\n".join(part for part in (result.stdout, result.stderr) if part).strip()
    status = get_stitch_mcp_status()
    payload = {
        "status": "connected" if status.get("status") == "connected" else "failed",
        "session_id": session_id,
        "callback_url": callback_url,
        "completed_at": current_local_iso(),
        "detail": combined,
        "mcp_status": status,
    }
    write_stitch_auth_state(payload)
    return payload


def stitch_auth_waiting_tickets() -> list[Path]:
    waiting: list[Path] = []
    tickets_root = REPO_ROOT / "vault" / "clients"
    for ticket_path in tickets_root.glob("*/tickets/T-*.md"):
        if not ticket_path.is_file():
            continue
        data = parse_frontmatter_map(ticket_path)
        status = str(data.get("status", "")).strip().lower()
        blockers = normalize_blocked_by(data.get("blocked_by"))
        if status in {"waiting", "blocked"} and STITCH_AUTH_BLOCKER in blockers:
            waiting.append(ticket_path)
    return waiting


def reopen_waiting_stitch_tickets() -> list[str]:
    reopened: list[str] = []
    for ticket_path in stitch_auth_waiting_tickets():
        if reopen_ticket_after_stitch_auth(ticket_path):
            reopened.append(infer_ticket_id(ticket_path))
    return reopened


def executor_ledger_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "data" / "executors"


def executor_log_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "logs" / "executors"


def ticket_identifier(ticket_path: Path) -> str:
    return infer_ticket_id(ticket_path)


def executor_ledger_path(ticket_path: Path) -> Path:
    ticket_id = re.sub(r"[^A-Za-z0-9._-]+", "-", ticket_identifier(ticket_path))
    return executor_ledger_dir() / f"{ticket_id}.json"


def executor_log_paths(ticket_path: Path) -> tuple[Path, Path]:
    ticket_id = re.sub(r"[^A-Za-z0-9._-]+", "-", ticket_identifier(ticket_path))
    log_dir = executor_log_dir()
    return log_dir / f"{ticket_id}.stdout.log", log_dir / f"{ticket_id}.stderr.log"


def executor_prompt_path(ticket_path: Path) -> Path:
    ticket_id = re.sub(r"[^A-Za-z0-9._-]+", "-", ticket_identifier(ticket_path))
    return executor_log_dir() / f"{ticket_id}.prompt.txt"


def build_run_task_subprocess_command(args: argparse.Namespace, *, cwd: str, prompt_file: str) -> list[str]:
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "run-task",
        "--platform",
        str(resolve_runtime_arg_path(args.platform)),
        "--metering",
        str(resolve_runtime_arg_path(args.metering)),
        "--project",
        args.project,
        "--client",
        args.client,
        "--cwd",
        cwd,
        "--prompt-file",
        prompt_file,
    ]
    if args.task_type is not None:
        command.extend(["--task-type", args.task_type])
    if args.force_agent:
        command.extend(["--force-agent", args.force_agent])
    if args.ticket_tags:
        command.extend(["--ticket-tags", *args.ticket_tags])
    if args.ticket_path:
        command.extend(["--ticket-path", str(Path(args.ticket_path).expanduser().resolve())])
    return command


def write_executor_ledger(ledger_path: Path, payload: dict) -> None:
    atomic_write_text(ledger_path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def read_executor_ledger(ledger_path: Path) -> dict:
    return json.loads(ledger_path.read_text(encoding="utf-8"))


def wait_for_executor_spawn(
    ledger_path: Path,
    *,
    runtime_pid: int,
    timeout_secs: float = EXECUTOR_SPAWN_WAIT_SECS,
    poll_secs: float = EXECUTOR_SPAWN_POLL_SECS,
) -> dict:
    deadline = time.monotonic() + timeout_secs
    latest_payload: dict = {}
    while time.monotonic() < deadline:
        if ledger_path.exists():
            try:
                payload = read_executor_ledger(ledger_path)
            except Exception:
                payload = {}
            else:
                latest_payload = payload
                payload_runtime_pid = int(payload.get("runtime_pid") or 0)
                if payload_runtime_pid == runtime_pid:
                    return payload
        time.sleep(poll_secs)
    return latest_payload


def is_process_alive(pid: int | None) -> bool:
    if not pid or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def stop_subprocess(process: subprocess.Popen[str], timeout_secs: int = EXECUTOR_STOP_WAIT_SECS) -> int:
    if process.poll() is not None:
        return int(process.returncode or 0)
    process.terminate()
    try:
        return int(process.wait(timeout=timeout_secs))
    except subprocess.TimeoutExpired:
        process.kill()
        return int(process.wait(timeout=timeout_secs))


def terminate_executor_processes(runtime_pid: int | None, child_pid: int | None) -> None:
    pids: list[int] = []
    for pid in (child_pid, runtime_pid):
        if not pid or pid <= 0 or pid == os.getpid() or pid in pids:
            continue
        pids.append(pid)

    for pid in pids:
        if is_process_alive(pid):
            try:
                os.kill(pid, signal.SIGTERM)
            except OSError:
                continue

    deadline = time.monotonic() + EXECUTOR_STOP_WAIT_SECS
    while time.monotonic() < deadline and any(is_process_alive(pid) for pid in pids):
        time.sleep(0.25)

    for pid in pids:
        if is_process_alive(pid):
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                continue

    deadline = time.monotonic() + 1.0
    while time.monotonic() < deadline and any(is_process_alive(pid) for pid in pids):
        time.sleep(0.1)


def mark_ticket_spawned(
    ticket_path: Path,
    agent_name: str,
    task_type: str,
    runtime_pid: int,
    ledger_path: Path,
    routing_choice: dict | None = None,
) -> None:
    now = current_local_iso()
    routing_choice = routing_choice or {}
    preferred_agent = str(routing_choice.get("preferred") or agent_name).strip() or agent_name
    routing_reason = str(routing_choice.get("reason") or "").strip()
    agent_mode = str(routing_choice.get("agent_mode") or "").strip()

    updates: dict[str, object] = {
        "id": infer_ticket_id(ticket_path),
        "status": "in-progress",
        "updated": now,
        "blocked_by": [],
        "executor_agent": agent_name,
        "executor_preferred_agent": preferred_agent,
        "executor_task_type": task_type,
        "executor_runtime_pid": runtime_pid,
        "executor_started": now,
        "executor_last_heartbeat": now,
        "executor_ledger": str(ledger_path),
    }
    if routing_reason:
        updates["executor_routing_reason"] = routing_reason
    if agent_mode:
        updates["executor_agent_mode"] = agent_mode

    update_markdown_frontmatter(
        ticket_path,
        updates,
        remove_keys={"completed"},
    )
    routing_parts = [f"preferred={preferred_agent}", f"actual={agent_name}"]
    if agent_mode:
        routing_parts.append(f"mode={agent_mode}")
    if routing_reason:
        routing_parts.append(f"reason={routing_reason}")
    append_ticket_work_log(
        ticket_path,
        (
            f"{now}: Executor spawned via agent_runtime ({agent_name}, {task_type}). "
            f"Routing: {'; '.join(routing_parts)}. Runtime PID {runtime_pid}."
        ),
    )


def update_ticket_executor_heartbeat(ticket_path: Path, child_pid: int | None = None) -> None:
    updates: dict[str, object] = {
        "id": infer_ticket_id(ticket_path),
        "executor_last_heartbeat": current_local_iso(),
    }
    if child_pid:
        updates["executor_child_pid"] = child_pid
    update_markdown_frontmatter(ticket_path, updates)


def clear_ticket_executor_fields(ticket_path: Path, status: str | None = None, note: str | None = None) -> None:
    updates = {
        "id": infer_ticket_id(ticket_path),
        "updated": current_local_iso(),
    }
    if status:
        updates["status"] = status
    update_markdown_frontmatter(ticket_path, updates, remove_keys=EXECUTOR_FRONTMATTER_KEYS | {"completed"} if status != "closed" else EXECUTOR_FRONTMATTER_KEYS)
    if note:
        append_ticket_work_log(ticket_path, note)


def describe_executor_termination(
    returncode: int,
    *,
    cleanup_action: str = "",
    stdout_text: str = "",
    stderr_text: str = "",
) -> str:
    if cleanup_action:
        return cleanup_action

    combined_output = f"{stdout_text}\n{stderr_text}".lower()
    if returncode == 0:
        return "exited_cleanly"
    if returncode < 0:
        return f"terminated_by_signal_{abs(returncode)}"
    if "unable to locate a java runtime" in combined_output:
        return "missing_java_runtime"
    if "command not found" in combined_output:
        return "missing_command"
    if "rate limit" in combined_output or "too many requests" in combined_output or "overloaded" in combined_output:
        return "rate_limited"
    if is_sandbox_retryable_failure(stderr_text):
        return "sandbox_retryable_failure"
    return f"nonzero_exit_{returncode}"


def format_executor_loss_note(now: str, runtime_pid: int, child_pid: int, payload: dict) -> str:
    note = f"{now}: Executor lost (runtime PID {runtime_pid}, child PID {child_pid})."
    termination_reason = str(payload.get("termination_reason") or "").strip()
    exit_code = payload.get("exit_code")
    has_exit_code = exit_code not in ("", None)
    if termination_reason or has_exit_code:
        detail = "Last recorded termination"
        if termination_reason and has_exit_code:
            detail += f": {termination_reason} (exit code {exit_code})."
        elif termination_reason:
            detail += f": {termination_reason}."
        else:
            detail += f": exit code {exit_code}."
        note += f" {detail}"
    note += " Reopened automatically by runtime recovery."
    return note


def finalize_ticket_after_executor(ticket_path: Path, returncode: int) -> None:
    ticket_data = parse_frontmatter_map(ticket_path)
    status = str(ticket_data.get("status", "")).strip()
    now = current_local_iso()

    if returncode == 0:
        if status in TERMINAL_TICKET_STATUSES:
            update_markdown_frontmatter(ticket_path, {"updated": now}, remove_keys=EXECUTOR_FRONTMATTER_KEYS)
            return
        update_markdown_frontmatter(ticket_path, {"updated": now}, remove_keys=EXECUTOR_FRONTMATTER_KEYS)
        return

    if status in TERMINAL_TICKET_STATUSES:
        update_markdown_frontmatter(ticket_path, {"updated": now}, remove_keys=EXECUTOR_FRONTMATTER_KEYS)
        return

    clear_ticket_executor_fields(
        ticket_path,
        status="open",
        note=f"{now}: Executor exited unexpectedly with code {returncode}. Reopened by agent_runtime.",
    )


def reconcile_executor_ledgers(ledger_dir: Path) -> list[dict]:
    recoveries: list[dict] = []
    if not ledger_dir.exists():
        return recoveries

    for ledger_path in sorted(ledger_dir.glob("*.json")):
        try:
            payload = read_executor_ledger(ledger_path)
        except Exception:
            continue

        if payload.get("status") != "running":
            continue

        ticket_path = Path(str(payload.get("ticket_path", ""))).expanduser()
        if not ticket_path.exists():
            payload["status"] = "orphaned_missing_ticket"
            payload["reconciled_at"] = current_local_iso()
            write_executor_ledger(ledger_path, payload)
            continue

        runtime_pid = int(payload.get("runtime_pid") or 0)
        child_pid = int(payload.get("child_pid") or 0)
        runtime_alive = is_process_alive(runtime_pid)
        child_alive = is_process_alive(child_pid)
        ticket_data = parse_frontmatter_map(ticket_path)
        ticket_status = str(ticket_data.get("status", "")).strip().lower()
        ticket_id = infer_ticket_id(ticket_path, ticket_data)
        now = current_local_iso()

        if ticket_status in TERMINAL_TICKET_STATUSES:
            if runtime_alive or child_alive:
                terminate_executor_processes(runtime_pid, child_pid)
            update_markdown_frontmatter(ticket_path, {"updated": now}, remove_keys=EXECUTOR_FRONTMATTER_KEYS)
            payload["status"] = "completed" if ticket_status == "closed" else "recovered"
            payload["completed_at"] = payload.get("completed_at") or now
            payload["reconciled_at"] = now
            payload["recovery_action"] = f"cleaned_terminal_{ticket_status}"
            write_executor_ledger(ledger_path, payload)
            recoveries.append(
                {
                    "ticket_id": ticket_id,
                    "ticket_path": str(ticket_path),
                    "action": "cleaned_terminal",
                }
            )
            continue

        if runtime_alive or child_alive:
            continue

        if ticket_status == "in-progress":
            clear_ticket_executor_fields(
                ticket_path,
                status="open",
                note=format_executor_loss_note(now, runtime_pid, child_pid, payload),
            )
            action = "reopened"
        else:
            update_markdown_frontmatter(ticket_path, {"updated": now}, remove_keys=EXECUTOR_FRONTMATTER_KEYS)
            action = "cleaned"

        payload["status"] = "recovered"
        payload["reconciled_at"] = now
        payload["recovery_action"] = action
        write_executor_ledger(ledger_path, payload)
        recoveries.append(
            {
                "ticket_id": ticket_id,
                "ticket_path": str(ticket_path),
                "action": action,
            }
        )

    return recoveries


def with_updated_frontmatter(existing_frontmatter: str) -> str:
    updated_value = datetime.now().strftime(ISO_FMT)
    if not existing_frontmatter:
        frontmatter = [
            'type: config',
            'title: "Token Usage & Metering"',
            (
                'description: "Tracks per-agent invocation counts, token usage, '
                'estimated spend, and relative monthly credit pool usage. Written '
                'by chat-native orchestration cycles and scripts/agent_runtime.py."'
            ),
            f"updated: {updated_value}",
        ]
        return "---\n" + "\n".join(frontmatter) + "\n---\n\n"

    lines = existing_frontmatter.splitlines()
    updated = False
    for idx, line in enumerate(lines):
        if line.startswith("updated:"):
            lines[idx] = f"updated: {updated_value}"
            updated = True
            break
    if not updated:
        lines.append(f"updated: {updated_value}")
    return "---\n" + "\n".join(lines) + "\n---\n\n"


def parse_daily_usage_entries(body: str) -> list[dict]:
    section = None
    entries = []
    new_format = re.compile(
        r"^\|\s*(\d{4}-\d{2}-\d{2} \d{2}:\d{2})\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([0-9]+)\s*\|\s*([0-9]+)\s*\|\s*([0-9]+)\s*\|\s*\$?([0-9.]+)\s*\|$"
    )
    old_format = re.compile(
        r"^\|\s*(\d{4}-\d{2}-\d{2} \d{2}:\d{2})\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([0-9]+)\s*\|\s*([0-9]+)\s*\|\s*([0-9]+)\s*\|\s*\$?([0-9.]+)\s*\|$"
    )

    for raw_line in body.splitlines():
        if raw_line.startswith("## "):
            section = raw_line.strip()
            continue
        if section != "## Daily Usage":
            continue
        line = raw_line.strip()
        if not line.startswith("|") or "Date" in line or "---" in line or "—" in line:
            continue

        match = new_format.match(line)
        if match:
            ts_str, agent, client, project, task_type, invocations, tokens_in, tokens_out, est_cost = match.groups()
        else:
            match = old_format.match(line)
            if not match:
                continue
            ts_str, client, project, invocations, tokens_in, tokens_out, est_cost = match.groups()
            agent = "claude"
            task_type = "legacy"

        try:
            timestamp = datetime.strptime(ts_str, DATE_FMT)
        except ValueError:
            continue

        entries.append(
            {
                "timestamp": timestamp,
                "timestamp_str": ts_str,
                "agent": agent.strip(),
                "client": client.strip(),
                "project": project.strip(),
                "task_type": task_type.strip(),
                "invocations": int(invocations),
                "tokens_in": int(tokens_in),
                "tokens_out": int(tokens_out),
                "cost": float(est_cost),
            }
        )
    return entries


def estimate_cost(tokens_in: int, tokens_out: int) -> float:
    return (tokens_in * 3 / 1_000_000) + (tokens_out * 15 / 1_000_000)


def sorted_agent_names(routing: dict) -> list[str]:
    return sorted(
        routing["agents"],
        key=lambda name: (
            routing["agents"].get(name, {}).get("priority", 999),
            name,
        ),
    )


def build_agent_pool_state(routing: dict, entries: list[dict], now: datetime | None = None) -> dict:
    now = now or datetime.now()
    monthly_invocations = defaultdict(int)
    for entry in entries:
        if entry["timestamp"].year == now.year and entry["timestamp"].month == now.month:
            monthly_invocations[entry["agent"]] += entry["invocations"]

    pools = {}
    for agent in sorted_agent_names(routing):
        cfg = routing["agents"].get(agent, {})
        budget = int(cfg.get("monthly_credit_budget", 0) or 0)
        enabled = bool(cfg.get("enabled", False))
        used = monthly_invocations[agent]
        pct = 0.0 if budget <= 0 else (used / budget) * 100
        if not enabled:
            status = "disabled"
        elif pct >= CRITICAL_THRESHOLD_PCT:
            status = "critical"
        elif pct >= TIGHT_THRESHOLD_PCT:
            status = "tight"
        else:
            status = "healthy"
        pools[agent] = {
            "enabled": enabled,
            "used": used,
            "budget": budget,
            "pct": pct,
            "status": status,
            "cli": cfg.get("cli", ""),
            "priority": int(cfg.get("priority", 999) or 999),
        }
    return pools


def format_pct(value: float) -> str:
    if abs(value - round(value)) < 0.05:
        return f"{round(value):.0f}%"
    return f"{value:.1f}%"


def format_agent_label(name: str) -> str:
    return name.replace("_", " ").title()


def render_metering_body(routing: dict, entries: list[dict]) -> str:
    now = datetime.now()
    pools = build_agent_pool_state(routing, entries, now=now)
    agents = sorted_agent_names(routing)

    credit_rows = []
    for agent in agents:
        pool = pools[agent]
        credit_rows.append(
            f"| {agent} | {str(pool['enabled']).lower()} | {pool['used']} | {pool['budget']} | {format_pct(pool['pct'])} | {pool['status']} |"
        )
    if not credit_rows:
        credit_rows.append("| — | — | — | — | — | — |")

    entries_sorted = sorted(entries, key=lambda entry: entry["timestamp"])
    daily_rows = []
    for entry in entries_sorted:
        daily_rows.append(
            f"| {entry['timestamp_str']} | {entry['agent']} | {entry['client']} | {entry['project']} | {entry['task_type']} | {entry['invocations']} | {entry['tokens_in']} | {entry['tokens_out']} | ${entry['cost']:.4f} |"
        )
    if not daily_rows:
        daily_rows.append("| — | — | — | — | — | — | — | — | — |")

    windows = {
        "last_hour": now - timedelta(hours=1),
        "last_24h": now - timedelta(hours=24),
        "last_7d": now - timedelta(days=7),
    }
    rolling_rows = []
    for label, cutoff in windows.items():
        matching = [entry for entry in entries if entry["timestamp"] >= cutoff]
        row = [label]
        for agent in agents:
            row.append(str(sum(entry["invocations"] for entry in matching if entry["agent"] == agent)))
        row.append(str(sum(entry["tokens_in"] + entry["tokens_out"] for entry in matching)))
        row.append(f"${sum(entry['cost'] for entry in matching):.4f}")
        rolling_rows.append("| " + " | ".join(row) + " |")

    per_client = defaultdict(lambda: {"tokens": 0, "cost": 0.0, "agents": defaultdict(int)})
    for entry in entries:
        client_key = entry["client"] or "_unknown"
        per_client[client_key]["tokens"] += entry["tokens_in"] + entry["tokens_out"]
        per_client[client_key]["cost"] += entry["cost"]
        per_client[client_key]["agents"][entry["agent"]] += entry["invocations"]

    client_rows = []
    for client_name in sorted(per_client):
        row = [client_name]
        for agent in agents:
            row.append(str(per_client[client_name]["agents"].get(agent, 0)))
        row.append(str(per_client[client_name]["tokens"]))
        row.append(f"${per_client[client_name]['cost']:.4f}")
        client_rows.append("| " + " | ".join(row) + " |")
    if not client_rows:
        empty = ["—"] + ["—"] * len(agents) + ["—", "—"]
        client_rows.append("| " + " | ".join(empty) + " |")

    rolling_headers = ["Window"] + [f"{format_agent_label(agent)} Invocations" for agent in agents] + ["Total Tokens", "Est Cost"]
    rolling_separator = ["-" * len(header) for header in rolling_headers]
    client_headers = ["Client"] + [f"{format_agent_label(agent)} Invocations" for agent in agents] + ["Total Tokens", "Est Cost"]
    client_separator = ["-" * len(header) for header in client_headers]

    return "\n".join(
        [
            "# Token Usage & Metering",
            "",
            "## Agent Credit Pools",
            "",
            "Usage is tracked as relative invocation units month-to-date until provider-specific credit APIs are available.",
            "",
            "| Agent | Enabled | Used (month) | Budget (month) | Pct Used | Status |",
            "|-------|---------|--------------|----------------|----------|--------|",
            *credit_rows,
            "",
            "## Daily Usage",
            "",
            "| Date | Agent | Client | Project | Task Type | Invocations | Tokens In | Tokens Out | Est Cost |",
            "|------|-------|--------|---------|-----------|-------------|-----------|------------|----------|",
            *daily_rows,
            "",
            "## Rolling Totals",
            "",
            "| " + " | ".join(rolling_headers) + " |",
            "| " + " | ".join(rolling_separator) + " |",
            *rolling_rows,
            "",
            "## Per-Client Summary",
            "",
            "| " + " | ".join(client_headers) + " |",
            "| " + " | ".join(client_separator) + " |",
            *client_rows,
            "",
            "## See Also",
            "",
            "- [[platform]]",
            "- [[orchestrator]]",
            "",
        ]
    )


def load_entries(metering_path: Path) -> tuple[str, list[dict]]:
    if not metering_path.exists():
        return "", []
    frontmatter, body = split_frontmatter(metering_path.read_text(encoding="utf-8"))
    return frontmatter, parse_daily_usage_entries(body)


def resolve_shadow_metering_path(metering_path: Path) -> Path:
    if metering_path.name == "metering.md":
        return metering_path.with_name("metering-observer.md")
    return metering_path


def load_effective_metering(metering_path: Path) -> tuple[Path, str, list[dict]]:
    effective_path = resolve_shadow_metering_path(metering_path)
    if effective_path == metering_path:
        frontmatter, entries = load_entries(metering_path)
        return effective_path, frontmatter, entries

    if effective_path.exists():
        frontmatter, entries = load_entries(effective_path)
        return effective_path, frontmatter, entries

    frontmatter, entries = load_entries(metering_path)
    return effective_path, frontmatter, entries


def write_metering(metering_path: Path, frontmatter: str, routing: dict, entries: list[dict]) -> None:
    content = with_updated_frontmatter(frontmatter) + render_metering_body(routing, entries)
    metering_path.write_text(content, encoding="utf-8")


def is_project_reconciliation_task(
    task_type: str,
    ticket_tags: list[str] | None = None,
    ticket_context: dict | None = None,
) -> bool:
    normalized_task = str(task_type or "").strip().lower()
    if normalized_task in PROJECT_RECONCILIATION_TASK_TYPES:
        return True

    if normalized_task != "orchestration":
        return False

    tags = set(ticket_tags or [])
    if tags & CLAUDE_JUDGMENT_TAGS:
        return False
    if tags & PROJECT_RECONCILIATION_TAGS:
        return True

    title = str((ticket_context or {}).get("title", "") or "").strip()
    return bool(PROJECT_RECONCILIATION_TITLE_RE.search(title))


def resolve_force_agent_role(role: str, routing: dict) -> tuple[str, str]:
    """Resolve a semantic --force-agent role name to a concrete agent.

    Roles let gate prompts in skills stay mode-agnostic. Instead of hardcoding
    `--force-agent codex` (which is misleading in chat_native mode where the
    runtime substitutes it anyway), prompts use `--force-agent gate_reviewer`
    and the runtime resolves it per-mode here.

    Resolution per agent_mode:
      chat_native    → host (via detect_host_agent)
      normal         → task_routing[role.normal_routing_key]  (default: role.normal_default)
      claude_fallback → claude
      codex_fallback  → codex

    Returns (agent_name, reason_string) where reason explains the resolution
    so RUNTIME-ROUTING log lines can show what happened.
    """
    if role not in FORCE_AGENT_ROLES:
        raise ValueError(f"Unknown --force-agent role: {role!r}. Known roles: {sorted(FORCE_AGENT_ROLES)}")
    spec = FORCE_AGENT_ROLES[role]

    agent_mode = str(routing.get("agent_mode", "chat_native") or "chat_native").strip()
    if agent_mode not in VALID_AGENT_MODES:
        agent_mode = "chat_native"

    if agent_mode == "chat_native":
        host_agent, host_reason = detect_host_agent(routing)
        return host_agent, f"role={role} resolved via chat_native: {host_reason}"

    if agent_mode in FALLBACK_MODE_TARGETS:
        target = FALLBACK_MODE_TARGETS[agent_mode]
        return target, f"role={role} resolved via {agent_mode}: routing to {target}"

    # normal mode: look up the role's canonical task_routing entry.
    routing_key = spec["normal_routing_key"]
    default = spec["normal_default"]
    resolved = routing.get("task_routing", {}).get(routing_key, default)
    return resolved, f"role={role} resolved via normal mode: task_routing[{routing_key}] = {resolved}"


def detect_host_agent(routing: dict, env: dict | None = None) -> tuple[str, str]:
    """Resolve which CLI the orchestrator is running inside.

    Priority:
      1. Explicit `host_agent` set in platform.md (operator override).
      2. Env-var fingerprint from HOST_AGENT_ENV_FINGERPRINTS.
      3. Default to `claude` (the most common host) with an explanatory reason.

    Returns (agent_name, reason_string). The reason is logged so operators see
    why a particular host was chosen — especially the default-claude case.
    """
    env = env if env is not None else os.environ

    explicit = str(routing.get("host_agent") or "").strip().lower()
    if explicit:
        agents = routing.get("agents", {})
        if explicit in agents:
            return explicit, f"host_agent: {explicit} set in platform.md"
        # Unknown agent name in config — fall through to env detection but log.
    for env_var, agent_name in HOST_AGENT_ENV_FINGERPRINTS:
        if env.get(env_var):
            return agent_name, f"detected {agent_name} via {env_var} env var"
    return (
        "claude",
        "no host signal found (no host_agent in platform.md, no CLAUDECODE/CODEX env vars); defaulting to claude — set host_agent: codex in platform.md if running in Codex",
    )


def choose_agent(
    routing: dict,
    entries: list[dict],
    task_type: str,
    ticket_tags: list[str] | None = None,
    ticket_context: dict | None = None,
) -> dict:
    agents = routing.get("agents", {})
    pools = build_agent_pool_state(routing, entries)
    sorted_agents = sorted_agent_names(routing)
    agent_mode = str(routing.get("agent_mode", "chat_native") or "chat_native").strip()
    if agent_mode not in VALID_AGENT_MODES:
        agent_mode = "chat_native"

    # chat_native: detect the host CLI and route everything to it, the same
    # way claude_fallback / codex_fallback already do for their named agent.
    chat_native_reason: str | None = None
    if agent_mode == "chat_native":
        host_agent, chat_native_reason = detect_host_agent(routing)
        fallback_target: str | None = host_agent
    else:
        fallback_target = FALLBACK_MODE_TARGETS.get(agent_mode)
    if fallback_target is not None:
        target_pool = pools.get(fallback_target, {})
        if agents.get(fallback_target, {}).get("enabled", False):
            if chat_native_reason:
                reason = f"chat_native mode: {chat_native_reason}; routing {task_type} to {fallback_target}."
            else:
                reason = f"{agent_mode} mode is active; routing {task_type} to {fallback_target}."
            return {
                "agent": fallback_target,
                "preferred": fallback_target,
                "reason": reason,
                "pool": target_pool,
                "agent_mode": agent_mode,
            }

        fallback_agent = None
        for agent_name in sorted_agents:
            if pools.get(agent_name, {}).get("enabled", False):
                fallback_agent = agent_name
                break
        if fallback_agent:
            if chat_native_reason:
                reason = (
                    f"chat_native mode: {chat_native_reason}, but {fallback_target} is disabled; "
                    f"routing {task_type} to {fallback_agent} instead."
                )
            else:
                reason = (
                    f"{agent_mode} mode is active, but {fallback_target} is disabled; "
                    f"routing {task_type} to {fallback_agent} instead."
                )
            return {
                "agent": fallback_agent,
                "preferred": fallback_target,
                "reason": reason,
                "pool": pools.get(fallback_agent, {}),
                "agent_mode": agent_mode,
            }

    # Routing override: if ticket has any override tag from config, route to override target
    override_tags = set(routing.get("routing_override_tags", []))
    override_target = routing.get("routing_override_target", "claude")
    matching_override_tags = override_tags & set(ticket_tags or [])
    if ticket_context and ticket_context.get("design_mode") == "implementation_only":
        matching_override_tags.discard("ui-design")
    if ticket_context and task_type == "creative_brief":
        visual_brief = bool(ticket_context.get("ui_work")) or bool(ticket_context.get("stitch_required")) or bool(
            ticket_context.get("design_mode")
        )
        if not visual_brief:
            matching_override_tags.difference_update({"stitch-required", "ui-design"})
    override_reason = ""
    if str(task_type or "").strip().lower() == "orchestration" and is_project_reconciliation_task(task_type, ticket_tags, ticket_context):
        preferred = "codex"
        override_reason = "project amendment/reconciliation routing"
    elif matching_override_tags:
        preferred = override_target
        override_reason = f"routing override tag(s) {', '.join(sorted(matching_override_tags))}"
    else:
        preferred = routing.get("task_routing", {}).get(task_type) or routing.get("task_routing", {}).get("general", "claude")
    if preferred not in agents and sorted_agents:
        preferred = sorted_agents[0]

    budget_based_routing = bool(routing.get("budget_based_routing", False))

    def can_take(agent_name: str) -> bool:
        pool = pools.get(agent_name, {})
        if not pool.get("enabled"):
            return False
        if not budget_based_routing:
            return True
        return float(pool.get("pct", 100.0)) < TIGHT_THRESHOLD_PCT

    if preferred in agents and can_take(preferred):
        if budget_based_routing:
            if override_reason:
                reason = (
                    f"{preferred} is selected for {task_type} by {override_reason} and is below the "
                    f"{int(TIGHT_THRESHOLD_PCT)}% threshold."
                )
            else:
                reason = (
                    f"{preferred} is the preferred routed agent for {task_type} and is below the "
                    f"{int(TIGHT_THRESHOLD_PCT)}% threshold."
                )
        else:
            if override_reason:
                reason = (
                    f"{preferred} is selected for {task_type} by {override_reason}; "
                    "budget-based routing is disabled."
                )
            else:
                reason = (
                    f"{preferred} is the preferred routed agent for {task_type}; "
                    "budget-based routing is disabled."
                )
        return {
            "agent": preferred,
            "preferred": preferred,
            "reason": reason,
            "pool": pools.get(preferred, {}),
            "agent_mode": agent_mode,
        }

    for agent_name in sorted_agents:
        if agent_name == preferred:
            continue
        if can_take(agent_name):
            reason = f"{preferred} is unavailable for {task_type}; routing to {agent_name} under fallback policy."
            if preferred in agents:
                if not pools.get(preferred, {}).get("enabled", False):
                    reason = f"{preferred} is disabled; routing {task_type} to {agent_name}."
                elif budget_based_routing and float(pools.get(preferred, {}).get("pct", 100.0)) >= TIGHT_THRESHOLD_PCT:
                    reason = (
                        f"{preferred} is at {format_pct(float(pools[preferred]['pct']))} of its monthly budget; "
                        f"routing {task_type} to {agent_name}."
                    )
            return {
                "agent": agent_name,
                "preferred": preferred,
                "reason": reason,
                "pool": pools.get(agent_name, {}),
                "agent_mode": agent_mode,
            }

    enabled_agents = [agent_name for agent_name in sorted_agents if pools.get(agent_name, {}).get("enabled")]
    if enabled_agents:
        if budget_based_routing:
            chosen = max(
                enabled_agents,
                key=lambda agent_name: (
                    (pools[agent_name]["budget"] - pools[agent_name]["used"]),
                    -pools[agent_name]["priority"],
                ),
            )
            reason = "All enabled agents are above the normal threshold; using the one with the most remaining monthly budget."
        else:
            chosen = min(
                enabled_agents,
                key=lambda agent_name: pools[agent_name]["priority"],
            )
            reason = (
                "Preferred agent was unavailable and budget-based routing is disabled; "
                "using the highest-priority enabled fallback agent."
            )
        return {
            "agent": chosen,
            "preferred": preferred,
            "reason": reason,
            "pool": pools.get(chosen, {}),
            "agent_mode": agent_mode,
        }

    fallback = preferred if preferred in agents else (sorted_agents[0] if sorted_agents else "claude")
    return {
        "agent": fallback,
        "preferred": preferred,
        "reason": "No enabled agents were configured; falling back to the preferred/default agent entry.",
        "pool": pools.get(fallback, {}),
        "agent_mode": agent_mode,
    }


def resolve_agent_choice_for_task(
    args: argparse.Namespace,
    routing: dict,
    entries: list[dict],
    task_type: str,
    ticket_context: dict,
    ticket_tags: list[str],
    *,
    emit_force_ignore: bool = False,
) -> dict:
    # Resolve semantic role names (gate_reviewer, visual_reviewer) into
    # concrete agent names BEFORE the existing logic runs. This lets gate
    # prompts in skills use mode-agnostic role names; the runtime is the one
    # place model substitution happens.
    if args.force_agent and args.force_agent in FORCE_AGENT_ROLES:
        resolved_agent, role_reason = resolve_force_agent_role(args.force_agent, routing)
        print(
            f"RUNTIME-ROUTING: {role_reason}; using {resolved_agent} for task_type={task_type}.",
            file=sys.stderr,
        )
        args.force_agent = resolved_agent

    agent_mode = str(routing.get("agent_mode", "chat_native") or "chat_native").strip()
    if agent_mode not in VALID_AGENT_MODES:
        agent_mode = "chat_native"
    if agent_mode == "chat_native":
        host_agent, _ = detect_host_agent(routing)
        fallback_target: str | None = host_agent
    else:
        fallback_target = FALLBACK_MODE_TARGETS.get(agent_mode)

    if args.force_agent and task_type in GATE_TASK_TYPES:
        if (
            fallback_target is not None
            and args.force_agent != fallback_target
            and routing["agents"].get(fallback_target, {}).get("enabled", False)
        ):
            print(
                (
                    f"RUNTIME-ROUTING: {agent_mode} mode overrides --force-agent "
                    f"{args.force_agent} for task_type={task_type}; routing to {fallback_target}."
                ),
                file=sys.stderr,
            )
            return {
                "agent": fallback_target,
                "preferred": fallback_target,
                "reason": (
                    f"{agent_mode} mode is active; overriding --force-agent "
                    f"{args.force_agent} for {task_type}."
                ),
                "pool": build_agent_pool_state(routing, entries).get(fallback_target, {}),
                "agent_mode": agent_mode,
            }
        agent_name = args.force_agent
        if agent_name not in routing["agents"]:
            raise SystemExit(f"Unknown forced agent: {agent_name}")
        if not routing["agents"][agent_name].get("enabled", False):
            raise SystemExit(f"Forced agent '{agent_name}' is disabled in platform config")
        return {
            "agent": agent_name,
            "preferred": agent_name,
            "reason": "Forced by caller.",
            "pool": build_agent_pool_state(routing, entries).get(agent_name, {}),
            "agent_mode": agent_mode,
        }

    if args.force_agent and emit_force_ignore:
        gate_task_types = ", ".join(sorted(GATE_TASK_TYPES))
        routing_scope = f"task_type={task_type}"
        ticket_path = Path(ticket_context["path"]) if ticket_context.get("path") else None
        ticket_id = ticket_identifier(ticket_path) if ticket_path else ""
        if ticket_id:
            routing_scope = f"{routing_scope} ticket={ticket_id}"
        print(
            (
                f"RUNTIME-ROUTING: Ignoring --force-agent {args.force_agent} for {routing_scope}. "
                f"Automatic routing is enforced unless task_type is one of {gate_task_types}."
            ),
            file=sys.stderr,
        )

    return choose_agent(routing, entries, task_type, ticket_tags=ticket_tags, ticket_context=ticket_context)


def parse_token_usage(output: str) -> tuple[int, int]:
    best_tokens_in = 0
    best_tokens_out = 0
    best_total = 0

    for line in output.splitlines():
        line = line.strip()
        if not line or not line.startswith("{"):
            continue
        try:
            payload = json.loads(line)
        except Exception:
            continue

        stack: list[object] = [payload]
        while stack:
            current = stack.pop()
            if isinstance(current, dict):
                usage = current.get("usage")
                if isinstance(usage, dict):
                    tokens_in = int(usage.get("input_tokens") or 0)
                    tokens_out = int(usage.get("output_tokens") or 0)
                    total = tokens_in + tokens_out
                    if total > best_total:
                        best_total = total
                        best_tokens_in = tokens_in
                        best_tokens_out = tokens_out
                stack.extend(current.values())
            elif isinstance(current, list):
                stack.extend(current)

    if best_total:
        return best_tokens_in, best_tokens_out

    patterns = [
        (r"input[:\s=]+([0-9,]+)", r"output[:\s=]+([0-9,]+)"),
        (r"([0-9,]+)\s+input", r"([0-9,]+)\s+output"),
    ]
    for in_pattern, out_pattern in patterns:
        match_in = re.search(in_pattern, output, flags=re.IGNORECASE)
        match_out = re.search(out_pattern, output, flags=re.IGNORECASE)
        if match_in or match_out:
            raw_in = match_in.group(1).replace(",", "").strip() if match_in else ""
            raw_out = match_out.group(1).replace(",", "").strip() if match_out else ""
            tokens_in = int(raw_in) if raw_in else 0
            tokens_out = int(raw_out) if raw_out else 0
            return tokens_in, tokens_out
    return 0, 0


def append_entry(metering_path: Path, platform_path: Path, entry: dict) -> None:
    effective_path, frontmatter, entries = load_effective_metering(metering_path)
    entries.append(entry)
    routing = load_agent_routing(platform_path)
    write_metering(effective_path, frontmatter, routing, entries)


def split_cli_command(cli: str) -> list[str]:
    command = shlex.split(cli, posix=os.name != "nt")
    if os.name == "nt":
        command = [token.strip('"') for token in command]
    return command


def command_basename(command: str) -> str:
    return PurePosixPath(command.replace("\\", "/")).name.lower()


def build_command(agent: str, cli: str, prompt: str, cwd: str) -> list[str]:
    command = split_cli_command(cli)
    if not command:
        raise SystemExit(f"No CLI configured for agent '{agent}'")

    if agent == "claude":
        if not any(token in {"-p", "--print"} for token in command):
            command.append("-p")
        command.append(prompt)
        if not any(token in {"-o", "--output-format"} for token in command):
            command.extend(["--output-format", "stream-json"])
        if "--verbose" not in command:
            command.append("--verbose")
        if "--dangerously-skip-permissions" not in command:
            command.append("--dangerously-skip-permissions")
        return command

    if agent == "codex" and len(command) >= 2 and command_basename(command[0]) in {"codex", "codex.exe"} and command[1] == "exec":
        command.extend(["--dangerously-bypass-approvals-and-sandbox", "--skip-git-repo-check", "--cd", cwd, prompt])
        return command

    if agent == "gemini":
        if not any(token in {"-p", "--prompt"} for token in command):
            command.extend(["-p", prompt])
        else:
            command.append(prompt)
        if "--approval-mode" not in command:
            command.extend(["--approval-mode", "yolo"])
        if not any(token in {"-o", "--output-format"} for token in command):
            command.extend(["--output-format", "stream-json"])
        return command

    command.append(prompt)
    return command


def read_prompt(args: argparse.Namespace) -> str:
    if args.prompt:
        return args.prompt
    if args.prompt_file:
        if args.prompt_file == "-":
            return sys.stdin.read()
        return Path(args.prompt_file).read_text(encoding="utf-8")
    data = sys.stdin.read()
    if data:
        return data
    raise SystemExit("No prompt provided. Use --prompt, --prompt-file, or stdin.")


def is_sandbox_retryable_failure(stderr_text: str) -> bool:
    return any(marker in stderr_text for marker in ("Operation not permitted", "PermissionError"))


def append_task_metering_entry(
    entries: list[dict],
    agent_name: str,
    client: str,
    project: str,
    task_type: str,
    output: str,
) -> None:
    tokens_in, tokens_out = parse_token_usage(output)
    now = datetime.now()
    entries.append(
        {
            "timestamp": now,
            "timestamp_str": now.strftime(DATE_FMT),
            "agent": agent_name,
            "client": client,
            "project": project,
            "task_type": task_type,
            "invocations": 1,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "cost": estimate_cost(tokens_in, tokens_out),
        }
    )


def run_task_attempt(
    *,
    agent_name: str,
    choice: dict,
    routing: dict,
    prompt: str,
    cwd: str,
    ticket_path: Path | None,
    ledger_path: Path | None,
    task_type: str,
    project: str,
    client: str,
) -> dict:
    cli = routing["agents"].get(agent_name, {}).get("cli", "")
    command = build_command(agent_name, cli, prompt, cwd)
    child_env = build_executor_environment(
        project=project,
        client=client,
        task_type=task_type,
        ticket_path=ticket_path,
    )
    stdout_log_path: Path | None = None
    stderr_log_path: Path | None = None
    prompt_log_path: Path | None = None

    if ticket_path and ledger_path:
        stdout_log_path, stderr_log_path = executor_log_paths(ticket_path)
        prompt_log_path = executor_prompt_path(ticket_path)
        stdout_log_path.parent.mkdir(parents=True, exist_ok=True)
        stdout_log_path.write_text("", encoding="utf-8")
        stderr_log_path.write_text("", encoding="utf-8")
        prompt_log_path.write_text(prompt, encoding="utf-8")
        mark_ticket_spawned(
            ticket_path,
            agent_name,
            task_type,
            os.getpid(),
            ledger_path,
            routing_choice=choice,
        )
        write_executor_ledger(
            ledger_path,
            {
                "ticket_id": ticket_identifier(ticket_path),
                "ticket_path": str(ticket_path),
                "project": project,
                "client": client,
                "task_type": task_type,
                "agent": agent_name,
                "preferred_agent": choice.get("preferred", agent_name),
                "routing_reason": choice.get("reason", ""),
                "agent_mode": choice.get("agent_mode", routing.get("agent_mode", "normal")),
                "cwd": cwd,
                "runtime_pid": os.getpid(),
                "child_pid": None,
                "started_at": current_local_iso(),
                "last_heartbeat": current_local_iso(),
                "status": "running",
                "prompt_path": str(prompt_log_path) if prompt_log_path else "",
                "stdout_log": str(stdout_log_path) if stdout_log_path else "",
                "stderr_log": str(stderr_log_path) if stderr_log_path else "",
            },
        )

    stdout_text = ""
    stderr_text = ""
    process: subprocess.Popen[str] | None = None
    forced_terminal_cleanup = False
    forced_terminal_status = ""
    try:
        if stdout_log_path and stderr_log_path:
            stdout_handle = stdout_log_path.open("w+", encoding="utf-8")
            stderr_handle = stderr_log_path.open("w+", encoding="utf-8")
        else:
            stdout_handle = tempfile.NamedTemporaryFile("w+", encoding="utf-8", delete=False)
            stderr_handle = tempfile.NamedTemporaryFile("w+", encoding="utf-8", delete=False)

        with stdout_handle, stderr_handle:
            try:
                process = subprocess.Popen(
                    command,
                    cwd=cwd,
                    env=child_env,
                    text=True,
                    stdin=subprocess.DEVNULL,
                    stdout=stdout_handle,
                    stderr=stderr_handle,
                    start_new_session=True,
                    close_fds=True,
                )
            except Exception:
                if ticket_path and ledger_path and ledger_path.exists():
                    payload = read_executor_ledger(ledger_path)
                    payload["status"] = "failed"
                    payload["completed_at"] = current_local_iso()
                    payload["exit_code"] = 1
                    write_executor_ledger(ledger_path, payload)
                    clear_ticket_executor_fields(
                        ticket_path,
                        status="open",
                        note=f"{current_local_iso()}: Executor failed to launch. Reopened by agent_runtime.",
                    )
                raise

            if ticket_path and ledger_path:
                update_ticket_executor_heartbeat(ticket_path, child_pid=process.pid)
                payload = read_executor_ledger(ledger_path)
                payload["child_pid"] = process.pid
                payload["last_heartbeat"] = current_local_iso()
                write_executor_ledger(ledger_path, payload)

            last_heartbeat = time.monotonic()
            terminal_status_seen_at: float | None = None
            while process.poll() is None:
                time.sleep(1)
                if ticket_path:
                    ticket_status = str(parse_frontmatter_map(ticket_path).get("status", "")).strip().lower()
                    if ticket_status in TERMINAL_TICKET_STATUSES:
                        if terminal_status_seen_at is None:
                            terminal_status_seen_at = time.monotonic()
                        elif (time.monotonic() - terminal_status_seen_at) >= EXECUTOR_TERMINAL_GRACE_SECS:
                            stop_subprocess(process)
                            forced_terminal_cleanup = True
                            forced_terminal_status = ticket_status
                            break
                    else:
                        terminal_status_seen_at = None
                if ticket_path and ledger_path and (time.monotonic() - last_heartbeat) >= EXECUTOR_HEARTBEAT_SECS:
                    update_ticket_executor_heartbeat(ticket_path, child_pid=process.pid)
                    payload = read_executor_ledger(ledger_path)
                    payload["last_heartbeat"] = current_local_iso()
                    payload["child_pid"] = process.pid
                    write_executor_ledger(ledger_path, payload)
                    last_heartbeat = time.monotonic()

        if stdout_log_path:
            stdout_text = stdout_log_path.read_text(encoding="utf-8")
        elif 'stdout_handle' in locals():
            stdout_text = Path(stdout_handle.name).read_text(encoding="utf-8")
        if stderr_log_path:
            stderr_text = stderr_log_path.read_text(encoding="utf-8")
        elif 'stderr_handle' in locals():
            stderr_text = Path(stderr_handle.name).read_text(encoding="utf-8")
    finally:
        if not stdout_log_path and 'stdout_handle' in locals():
            Path(stdout_handle.name).unlink(missing_ok=True)
        if not stderr_log_path and 'stderr_handle' in locals():
            Path(stderr_handle.name).unlink(missing_ok=True)

    returncode = process.returncode if process is not None else 1
    cleanup_action = ""
    if forced_terminal_cleanup and forced_terminal_status in TERMINAL_TICKET_STATUSES:
        returncode = 0
        cleanup_action = f"terminated_after_ticket_{forced_terminal_status}"
    termination_reason = describe_executor_termination(
        returncode,
        cleanup_action=cleanup_action,
        stdout_text=stdout_text,
        stderr_text=stderr_text,
    )

    return {
        "agent": agent_name,
        "choice": choice,
        "returncode": returncode,
        "stdout_text": stdout_text,
        "stderr_text": stderr_text,
        "cleanup_action": cleanup_action,
        "termination_reason": termination_reason,
    }


def command_refresh_metering(args: argparse.Namespace) -> int:
    platform_path = resolve_runtime_arg_path(args.platform)
    metering_path = resolve_runtime_arg_path(args.metering)
    effective_path, frontmatter, entries = load_effective_metering(metering_path)
    routing = load_agent_routing(platform_path)
    write_metering(effective_path, frontmatter, routing, entries)
    return 0


def command_append_metering(args: argparse.Namespace) -> int:
    timestamp = datetime.strptime(args.timestamp, DATE_FMT) if args.timestamp else datetime.now()
    platform_path = resolve_runtime_arg_path(args.platform)
    metering_path = resolve_runtime_arg_path(args.metering)
    append_entry(
        metering_path,
        platform_path,
        {
            "timestamp": timestamp,
            "timestamp_str": timestamp.strftime(DATE_FMT),
            "agent": args.agent,
            "client": args.client,
            "project": args.project,
            "task_type": args.task_type,
            "invocations": args.invocations,
            "tokens_in": args.tokens_in,
            "tokens_out": args.tokens_out,
            "cost": estimate_cost(args.tokens_in, args.tokens_out),
        },
    )
    return 0


def command_choose_agent(args: argparse.Namespace) -> int:
    platform_path = resolve_runtime_arg_path(args.platform)
    metering_path = resolve_runtime_arg_path(args.metering)
    _, _, entries = load_effective_metering(metering_path)
    routing = load_agent_routing(platform_path)
    ticket_context = load_ticket_context(getattr(args, "ticket_path", None))
    ticket_tags = merge_ticket_tags(getattr(args, "ticket_tags", None), ticket_context)
    task_type = effective_task_type(ticket_context, args.task_type)
    choice = choose_agent(routing, entries, task_type, ticket_tags=ticket_tags, ticket_context=ticket_context)
    agent_name = choice["agent"]
    pool = choice["pool"]
    payload = {
        "agent": agent_name,
        "cli": routing["agents"].get(agent_name, {}).get("cli", ""),
        "preferred": choice["preferred"],
        "reason": choice["reason"],
        "agent_mode": choice.get("agent_mode", routing.get("agent_mode", "normal")),
        "used": pool.get("used", 0),
        "budget": pool.get("budget", 0),
        "pct_used": round(float(pool.get("pct", 0.0)), 2),
        "ticket_tags": ticket_tags,
        "ticket_path": ticket_context.get("path", ""),
    }
    if args.format == "json":
        print(json.dumps(payload))
    else:
        for key, value in payload.items():
            print(f"{key}={value}")
    return 0


def command_run_task(args: argparse.Namespace) -> int:
    if hasattr(signal, "SIGHUP"):
        try:
            signal.signal(signal.SIGHUP, signal.SIG_IGN)
        except (AttributeError, OSError, RuntimeError, ValueError):
            pass

    recoveries = reconcile_executor_ledgers(executor_ledger_dir())
    for recovery in recoveries:
        print(
            f"RUNTIME-RECOVERY: {recovery['ticket_id']} {recovery['action']} after lost executor.",
            file=sys.stderr,
        )

    prompt = read_prompt(args)
    platform_path = resolve_runtime_arg_path(args.platform)
    metering_path = resolve_runtime_arg_path(args.metering)
    effective_metering_path, frontmatter, entries = load_effective_metering(metering_path)
    routing = load_agent_routing(platform_path)
    quality_contract = load_quality_contract(platform_path)
    ticket_context = load_ticket_context(getattr(args, "ticket_path", None))
    ticket_tags = merge_ticket_tags(getattr(args, "ticket_tags", None), ticket_context)
    task_type = effective_task_type(ticket_context, args.task_type)
    ticket_path = Path(ticket_context["path"]) if ticket_context.get("path") else None
    ticket_id = ticket_identifier(ticket_path) if ticket_path else ""
    design_context = determine_design_context(task_type, prompt, quality_contract, ticket_context, ticket_tags)
    choice = resolve_agent_choice_for_task(
        args,
        routing,
        entries,
        task_type,
        ticket_context,
        ticket_tags,
        emit_force_ignore=True,
    )

    if ticket_path:
        enforce_ticket_dependency_guard(ticket_path)
        stitch_preflight = ensure_stitch_ticket_ready(ticket_path, design_context, target_agent=choice["agent"])
        if stitch_preflight.get("status") in {"auth_required", "api_key_required"}:
            print(
                json.dumps(
                    {
                        "ticket_id": ticket_id,
                        "ticket_path": str(ticket_path),
                        **stitch_preflight,
                    }
                )
            )
            return 0
        if stitch_preflight.get("status") not in {"ready", "not_applicable"}:
            print(
                json.dumps(
                    {
                        "ticket_id": ticket_id,
                        "ticket_path": str(ticket_path),
                        **stitch_preflight,
                    }
                )
            )
            return 1
        if stitch_preflight.get("implementation_from_sealed_stitch_package"):
            design_context["implementation_from_sealed_stitch_package"] = True
            design_context["sealed_design_package_ref"] = str(stitch_preflight.get("sealed_design_package_ref", ""))
            design_context["sealed_design_package_path"] = str(stitch_preflight.get("sealed_design_package_path", ""))

    cwd = str(Path(args.cwd).resolve()) if args.cwd else str(args.platform.parent.parent.resolve())
    local_now = datetime.now().astimezone().strftime("%Y-%m-%dT%H:%M %Z %z")
    nexus_context = determine_nexus_context(task_type, prompt, ticket_context)
    code_intelligence_context = determine_code_intelligence_context(task_type, prompt, ticket_context)
    hybrid_retrieval_context = determine_hybrid_retrieval_context(task_type, prompt, ticket_context)
    preamble = build_runtime_preamble(
        local_now,
        quality_contract,
        design_context=design_context,
        ticket_context=ticket_context,
        nexus_context=nexus_context,
        code_intelligence_context=code_intelligence_context,
        hybrid_retrieval_context=hybrid_retrieval_context,
    )
    prompt = f"{preamble}\n\n{prompt}"

    ledger_path = executor_ledger_path(ticket_path) if ticket_path else None

    attempts: list[dict] = []
    stdout_chunks: list[str] = []
    stderr_chunks: list[str] = []

    attempt = run_task_attempt(
        agent_name=choice["agent"],
        choice=choice,
        routing=routing,
        prompt=prompt,
        cwd=cwd,
        ticket_path=ticket_path,
        ledger_path=ledger_path,
        task_type=task_type,
        project=args.project,
        client=args.client,
    )
    attempts.append(attempt)
    if attempt["stdout_text"]:
        stdout_chunks.append(attempt["stdout_text"])
    if attempt["stderr_text"]:
        stderr_chunks.append(attempt["stderr_text"])
    combined_attempt_output = attempt["stdout_text"]
    if attempt["stderr_text"]:
        combined_attempt_output = (
            f"{combined_attempt_output}\n{attempt['stderr_text']}"
            if combined_attempt_output
            else attempt["stderr_text"]
        )
    append_task_metering_entry(entries, attempt["agent"], args.client, args.project, task_type, combined_attempt_output)

    if (
        ticket_id
        and attempt["agent"] == "codex"
        and attempt["returncode"] != 0
        and is_sandbox_retryable_failure(attempt["stderr_text"])
    ):
        claude_enabled = bool(routing.get("agents", {}).get("claude", {}).get("enabled", False))
        if claude_enabled:
            retry_message = (
                f"RUNTIME-RETRY: Codex sandbox failure detected for {ticket_id}. "
                "Automatically retrying with Claude."
            )
            stderr_chunks.append(retry_message + "\n")
            if ticket_path:
                append_ticket_work_log(ticket_path, f"{current_local_iso()}: {retry_message}")
            retry_choice = {
                "agent": "claude",
                "preferred": choice.get("preferred", "codex"),
                "reason": "Runtime retry after Codex sandbox failure.",
                "pool": build_agent_pool_state(routing, entries).get("claude", {}),
                "agent_mode": routing.get("agent_mode", "normal"),
            }
            attempt = run_task_attempt(
                agent_name="claude",
                choice=retry_choice,
                routing=routing,
                prompt=prompt,
                cwd=cwd,
                ticket_path=ticket_path,
                ledger_path=ledger_path,
                task_type=task_type,
                project=args.project,
                client=args.client,
            )
            attempts.append(attempt)
            if attempt["stdout_text"]:
                stdout_chunks.append(attempt["stdout_text"])
            if attempt["stderr_text"]:
                stderr_chunks.append(attempt["stderr_text"])
            combined_attempt_output = attempt["stdout_text"]
            if attempt["stderr_text"]:
                combined_attempt_output = (
                    f"{combined_attempt_output}\n{attempt['stderr_text']}"
                    if combined_attempt_output
                    else attempt["stderr_text"]
                )
            append_task_metering_entry(entries, attempt["agent"], args.client, args.project, task_type, combined_attempt_output)
        else:
            retry_message = (
                f"RUNTIME-RETRY: Codex sandbox failure detected for {ticket_id}. "
                "Claude retry skipped because Claude is disabled."
            )
            stderr_chunks.append(retry_message + "\n")
            if ticket_path:
                append_ticket_work_log(ticket_path, f"{current_local_iso()}: {retry_message}")

    final_attempt = attempts[-1]
    returncode = final_attempt["returncode"]
    cleanup_action = final_attempt["cleanup_action"]
    if ticket_path and ledger_path and ledger_path.exists():
        payload = read_executor_ledger(ledger_path)
        payload["completed_at"] = current_local_iso()
        payload["status"] = "completed" if returncode == 0 else "failed"
        payload["exit_code"] = returncode
        payload["termination_reason"] = final_attempt["termination_reason"]
        if cleanup_action:
            payload["recovery_action"] = cleanup_action
            payload["forced_terminal_cleanup"] = True
        write_executor_ledger(ledger_path, payload)
        finalize_ticket_after_executor(ticket_path, returncode)

    write_metering(effective_metering_path, frontmatter, routing, entries)

    stdout_text = "".join(stdout_chunks)
    stderr_text = "".join(stderr_chunks)
    if stdout_text:
        sys.stdout.write(stdout_text)
    if stderr_text:
        sys.stderr.write(stderr_text)
    return returncode


def command_spawn_task(args: argparse.Namespace) -> int:
    if not args.ticket_path:
        raise SystemExit("spawn-task requires --ticket-path")

    ticket_path = Path(args.ticket_path).expanduser().resolve()
    ledger_path = executor_ledger_path(ticket_path)
    prompt = read_prompt(args)
    platform_path = resolve_runtime_arg_path(args.platform)
    metering_path = resolve_runtime_arg_path(args.metering)
    _, _, entries = load_effective_metering(metering_path)
    routing = load_agent_routing(platform_path)
    quality_contract = load_quality_contract(platform_path)
    ticket_context = load_ticket_context(str(ticket_path))
    ticket_tags = merge_ticket_tags(getattr(args, "ticket_tags", None), ticket_context)
    task_type = effective_task_type(ticket_context, args.task_type)
    design_context = determine_design_context(task_type, prompt, quality_contract, ticket_context, ticket_tags)
    choice = resolve_agent_choice_for_task(args, routing, entries, task_type, ticket_context, ticket_tags)
    stitch_preflight = ensure_stitch_ticket_ready(ticket_path, design_context, target_agent=choice["agent"])
    if stitch_preflight.get("status") in {"auth_required", "api_key_required"}:
        waiting_status = "waiting_for_stitch_auth"
        if stitch_preflight.get("status") == "api_key_required":
            waiting_status = "waiting_for_stitch_api_key"
        response = {
            "ticket_id": ticket_identifier(ticket_path),
            "ticket_path": str(ticket_path),
            "ledger_path": str(ledger_path),
            "runtime_pid": None,
            "child_pid": None,
            "status": waiting_status,
            "auth_url": stitch_preflight.get("auth_url", ""),
            "auth_snapshot_path": stitch_preflight.get("snapshot_path", ""),
        }
        print(json.dumps(response))
        return 0
    if stitch_preflight.get("status") not in {"ready", "not_applicable"}:
        response = {
            "ticket_id": ticket_identifier(ticket_path),
            "ticket_path": str(ticket_path),
            "ledger_path": str(ledger_path),
            "runtime_pid": None,
            "child_pid": None,
            **stitch_preflight,
        }
        print(json.dumps(response))
        return 1
    cwd = str(Path(args.cwd).resolve()) if args.cwd else str(args.platform.parent.parent.resolve())

    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        delete=False,
        prefix=f"{ticket_identifier(ticket_path)}-spawn-",
        suffix=".prompt.txt",
    ) as prompt_handle:
        prompt_handle.write(prompt)
        prompt_file = prompt_handle.name

    command = build_run_task_subprocess_command(args, cwd=cwd, prompt_file=prompt_file)
    with open(os.devnull, "w", encoding="utf-8") as devnull:
        process = subprocess.Popen(
            command,
            cwd=cwd,
            text=True,
            stdin=subprocess.DEVNULL,
            stdout=devnull,
            stderr=devnull,
            start_new_session=True,
            close_fds=True,
        )

    payload = wait_for_executor_spawn(ledger_path, runtime_pid=process.pid)
    response = {
        "ticket_id": ticket_identifier(ticket_path),
        "ticket_path": str(ticket_path),
        "ledger_path": str(ledger_path),
        "runtime_pid": process.pid,
        "child_pid": payload.get("child_pid"),
        "status": payload.get("status", "spawned"),
    }
    print(json.dumps(response))
    return 0


def command_reconcile_executors(args: argparse.Namespace) -> int:
    recoveries = reconcile_executor_ledgers(args.ledger_dir)
    for recovery in recoveries:
        print(
            f"{recovery['ticket_id']}: {recovery['action']} ({recovery['ticket_path']})"
        )
    return 0


def command_ensure_stitch_auth(args: argparse.Namespace) -> int:
    ticket_path = Path(args.ticket_path).expanduser().resolve()
    ticket_context = load_ticket_context(str(ticket_path))
    design_context = {"requires_stitch": True}
    if ticket_context.get("path"):
        design_context["requires_stitch"] = bool(
            ticket_context.get("stitch_required") or ticket_context.get("design_mode") == "stitch_required"
        )
    target_agent = getattr(args, "target_agent", None)
    if design_context.get("requires_stitch") and not target_agent:
        try:
            platform_path = resolve_runtime_arg_path(args.platform)
            metering_path = resolve_runtime_arg_path(args.metering)
            _, _, entries = load_effective_metering(metering_path)
            routing = load_agent_routing(platform_path)
            ticket_tags = merge_ticket_tags(getattr(args, "ticket_tags", None), ticket_context)
            task_type = effective_task_type(ticket_context, args.task_type)
            choice = resolve_agent_choice_for_task(args, routing, entries, task_type, ticket_context, ticket_tags)
            target_agent = choice["agent"]
        except Exception as exc:
            result = {
                "status": "target_agent_unknown",
                "detail": f"Could not infer target agent for Stitch preflight: {exc}",
            }
            print(json.dumps(result))
            return 1

    result = ensure_stitch_ticket_ready(ticket_path, design_context, target_agent=target_agent)
    print(json.dumps(result))
    return 0 if result.get("status") in {"ready", "auth_required", "api_key_required", "not_applicable"} else 1


def command_complete_stitch_auth(args: argparse.Namespace) -> int:
    result = complete_stitch_auth(args.callback_url)
    if result.get("status") == "connected":
        result["reopened_tickets"] = reopen_waiting_stitch_tickets()
    print(json.dumps(result))
    return 0 if result.get("status") == "connected" else 1


def command_build_orchestrator_prompt(args: argparse.Namespace) -> int:
    platform_path = resolve_runtime_arg_path(args.platform)
    routing = load_agent_routing(platform_path)
    project_slug = str(args.project or "").strip()
    client = str(args.client or "_platform").strip() or "_platform"
    project_file = resolve_runtime_arg_path(args.project_file) if args.project_file else project_file_for_orchestration(project_slug, client)
    local_now = str(args.local_now or "").strip() or datetime.now().astimezone().strftime("%Y-%m-%dT%H:%M %Z %z")
    mode = str(routing.get("orchestration_context_mode", "tiered") or "tiered").strip().lower()
    if mode not in VALID_ORCHESTRATION_CONTEXT_MODES:
        mode = "tiered"
        routing["orchestration_context_mode"] = mode

    packet_path: Path | None = None
    if mode in {"tiered", "compact"}:
        packet_dir = resolve_runtime_arg_path(args.packet_dir) if args.packet_dir else REPO_ROOT / "data" / "control-plane" / "orchestration-packets"
        packet_dir.mkdir(parents=True, exist_ok=True)
        safe_project = re.sub(r"[^A-Za-z0-9_.-]+", "-", project_slug).strip("-") or "project"
        packet_path = packet_dir / f"orchestration-state-{safe_project}-{packet_timestamp(local_now)}.md"
        packet = build_orchestration_state_packet(
            project_file=project_file,
            project_slug=project_slug,
            client=client,
            local_now=local_now,
            routing=routing,
        )
        packet_path.write_text(packet, encoding="utf-8")

    prompt = build_orchestrator_prompt(
        local_now=local_now,
        project_slug=project_slug,
        client=client,
        project_file=project_file,
        routing=routing,
        packet_path=packet_path,
    )
    print(prompt)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Agent routing and metering runtime helpers.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    refresh = subparsers.add_parser("refresh-metering")
    refresh.add_argument("--platform", type=Path, required=True)
    refresh.add_argument("--metering", type=Path, required=True)
    refresh.set_defaults(func=command_refresh_metering)

    append = subparsers.add_parser("append-metering")
    append.add_argument("--platform", type=Path, required=True)
    append.add_argument("--metering", type=Path, required=True)
    append.add_argument("--agent", required=True)
    append.add_argument("--client", default="_platform")
    append.add_argument("--project", required=True)
    append.add_argument("--task-type", default="general")
    append.add_argument("--tokens-in", type=int, default=0)
    append.add_argument("--tokens-out", type=int, default=0)
    append.add_argument("--invocations", type=int, default=1)
    append.add_argument("--timestamp")
    append.set_defaults(func=command_append_metering)

    choose = subparsers.add_parser("choose-agent")
    choose.add_argument("--platform", type=Path, required=True)
    choose.add_argument("--metering", type=Path, required=True)
    choose.add_argument("--task-type", default=None)
    choose.add_argument("--ticket-tags", nargs="*", default=None, help="Ticket tags for routing override (e.g., multimodal-required tool-orchestration)")
    choose.add_argument("--ticket-path", help="Ticket markdown path. Runtime will read frontmatter tags and Stitch metadata from it.")
    choose.add_argument("--format", choices=["json", "shell"], default="json")
    choose.set_defaults(func=command_choose_agent)

    run = subparsers.add_parser("run-task")
    run.add_argument("--platform", type=Path, required=True)
    run.add_argument("--metering", type=Path, required=True)
    run.add_argument("--task-type", default=None)
    run.add_argument("--project", required=True)
    run.add_argument("--client", default="_platform")
    run.add_argument("--cwd")
    run.add_argument("--prompt")
    run.add_argument("--prompt-file")
    run.add_argument("--force-agent")
    run.add_argument("--ticket-tags", nargs="*", default=None, help="Ticket tags for routing override")
    run.add_argument("--ticket-path", help="Ticket markdown path. Runtime will read frontmatter tags and Stitch metadata from it.")
    run.set_defaults(func=command_run_task)

    spawn = subparsers.add_parser("spawn-task")
    spawn.add_argument("--platform", type=Path, required=True)
    spawn.add_argument("--metering", type=Path, required=True)
    spawn.add_argument("--task-type", default=None)
    spawn.add_argument("--project", required=True)
    spawn.add_argument("--client", default="_platform")
    spawn.add_argument("--cwd")
    spawn.add_argument("--prompt")
    spawn.add_argument("--prompt-file")
    spawn.add_argument("--force-agent")
    spawn.add_argument("--ticket-tags", nargs="*", default=None, help="Ticket tags for routing override")
    spawn.add_argument("--ticket-path", required=True, help="Ticket markdown path. Runtime will read frontmatter tags and Stitch metadata from it.")
    spawn.set_defaults(func=command_spawn_task)

    reconcile = subparsers.add_parser("reconcile-executors")
    reconcile.add_argument("--ledger-dir", type=Path, default=executor_ledger_dir())
    reconcile.set_defaults(func=command_reconcile_executors)

    ensure_stitch = subparsers.add_parser("ensure-stitch-auth")
    ensure_stitch.add_argument("--ticket-path", required=True)
    ensure_stitch.add_argument("--platform", type=Path, default=REPO_ROOT / "vault" / "config" / "platform.md")
    ensure_stitch.add_argument("--metering", type=Path, default=REPO_ROOT / "vault" / "config" / "metering.md")
    ensure_stitch.add_argument("--task-type", default=None)
    ensure_stitch.add_argument("--force-agent")
    ensure_stitch.add_argument("--ticket-tags", nargs="*", default=None, help="Ticket tags for routing override")
    ensure_stitch.add_argument("--target-agent", help="Explicit spawning agent for Stitch MCP preflight.")
    ensure_stitch.set_defaults(func=command_ensure_stitch_auth)

    complete_stitch = subparsers.add_parser("complete-stitch-auth")
    complete_stitch.add_argument("--callback-url", required=True)
    complete_stitch.set_defaults(func=command_complete_stitch_auth)

    orch_prompt = subparsers.add_parser("build-orchestrator-prompt")
    orch_prompt.add_argument("--platform", type=Path, required=True)
    orch_prompt.add_argument("--project", required=True)
    orch_prompt.add_argument("--client", default="_platform")
    orch_prompt.add_argument("--project-file", type=Path)
    orch_prompt.add_argument("--packet-dir", type=Path)
    orch_prompt.add_argument("--local-now")
    orch_prompt.set_defaults(func=command_build_orchestrator_prompt)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
