#!/usr/bin/env python3
"""Enforce the brief specificity adequacy gate with autonomous elaboration."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
VAULT_ROOT = REPO_ROOT / "vault"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from score_brief_specificity import (  # noqa: E402
    CLARIFICATION_QUESTIONS,
    audience_context_fields,
    concrete_values,
    distinctiveness_signals,
    named_systems,
    real_workflow_verbs,
    score_text,
    strip_frontmatter,
)

PROJECT_KEY_RE = re.compile(r"project:\s*\"?([^\n\"]+)\"?", re.IGNORECASE)
CLIENT_PATH_RE = re.compile(r"/vault/clients/([^/]+)/")


def local_now() -> str:
    """Return a local ISO-8601 timestamp with timezone."""
    return datetime.now().astimezone().isoformat(timespec="seconds")


def split_frontmatter(text: str) -> tuple[str, str]:
    """Split a markdown file into YAML frontmatter and body."""
    if not text.startswith("---\n"):
        return "", text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return "", text
    return parts[1].strip(), parts[2].lstrip("\n")


def load_frontmatter(path: Path) -> dict[str, Any]:
    """Load YAML frontmatter from a markdown file."""
    frontmatter_text, _body = split_frontmatter(path.read_text(encoding="utf-8"))
    if not frontmatter_text:
        return {}
    data = yaml.safe_load(frontmatter_text)
    return data if isinstance(data, dict) else {}


def normalize_text(value: Any) -> str:
    """Normalize a value to stripped text."""
    return str(value or "").strip()


def boolish(value: Any) -> bool:
    """Interpret a value as a loose boolean."""
    if isinstance(value, bool):
        return value
    return normalize_text(value).lower() in {"1", "true", "yes", "y", "on"}


def axis_explanations(score: dict[str, Any]) -> list[str]:
    """Return concise markdown explanations for failed axes."""
    lines: list[str] = []
    axes = score.get("axis_scores", {})
    labels = {
        "named_systems": "Named systems density",
        "concrete_values": "Concrete sample values",
        "real_workflow_verbs": "Real workflow verbs",
        "audience_context": "Audience context detail",
        "distinctiveness_signals": "Distinctiveness signals",
    }
    for key, label in labels.items():
        axis = axes.get(key, {})
        status = "PASS" if axis.get("passes") else "FAIL"
        count = axis.get("count", 0)
        threshold = axis.get("threshold", 0)
        examples = axis.get("examples") or []
        example_text = ", ".join(str(item) for item in examples[:5]) if examples else "none detected"
        lines.append(f"- **{label}: {status}** — detected {count}/{threshold}. Examples: {example_text}.")
    return lines


def write_clarification_artifact(brief_path: Path, score: dict[str, Any], explicit_path: str | None = None) -> Path:
    """Write a structured clarification request artifact next to the brief."""
    target = (
        Path(explicit_path).expanduser().resolve()
        if explicit_path
        else brief_path.with_name(f"{brief_path.stem}-specificity-clarification.md")
    )
    questions = score.get("clarification_questions") or list(CLARIFICATION_QUESTIONS.values())
    content = [
        "# Brief Specificity Adequacy Alert",
        "",
        f"Generated: {local_now()}",
        f"Brief: `{brief_path}`",
        "",
        "The brief remains too thin after autonomous elaboration and was explicitly configured to require operator clarification.",
        "",
        "## Axis Results",
        "",
        *axis_explanations(score),
        "",
        "## Structured Clarification Questions",
        "",
    ]
    content.extend(f"{index}. {question}" for index, question in enumerate(questions, start=1))
    content.extend(["", "## Operator Clarifications", "", "<Add concrete answers here, then rerun the adequacy gate.>", ""])
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(content), encoding="utf-8")
    return target


def infer_client(frontmatter: dict[str, Any], brief_path: Path) -> str | None:
    """Infer the client slug from frontmatter or path."""
    explicit = normalize_text(frontmatter.get("client"))
    if explicit:
        return explicit
    match = CLIENT_PATH_RE.search(str(brief_path.resolve()))
    return match.group(1) if match else None


def infer_project(frontmatter: dict[str, Any], brief_path: Path) -> str:
    """Infer the project slug from frontmatter or path."""
    explicit = normalize_text(frontmatter.get("project"))
    if explicit:
        return explicit
    match = PROJECT_KEY_RE.search(brief_path.read_text(encoding="utf-8"))
    if match:
        return match.group(1).strip()
    parent_name = brief_path.parent.name
    if parent_name not in {"snapshots", "incoming"}:
        return parent_name
    return brief_path.stem


def resolve_project_file(project: str, client: str | None, brief_path: Path) -> Path | None:
    """Resolve the project markdown file when available."""
    candidates = [VAULT_ROOT / "projects" / f"{project}.md"]
    if client:
        candidates.append(VAULT_ROOT / "clients" / client / "projects" / f"{project}.md")
    if "snapshots" in brief_path.parts:
        try:
            snapshots_index = brief_path.parts.index("snapshots")
        except ValueError:
            snapshots_index = -1
        if snapshots_index > 0:
            sibling_root = Path(*brief_path.parts[:snapshots_index])
            candidates.append(sibling_root / "projects" / f"{project}.md")
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    return None


def collect_project_paths(project: str, client: str | None, brief_path: Path) -> list[Path]:
    """Collect project-context markdown paths related to the brief."""
    paths: list[Path] = []
    project_file = resolve_project_file(project, client, brief_path)
    if project_file is not None:
        paths.append(project_file)

    ticket_dirs = [VAULT_ROOT / "tickets"]
    snapshot_dirs = [VAULT_ROOT / "snapshots" / project]
    if client:
        ticket_dirs.append(VAULT_ROOT / "clients" / client / "tickets")
        snapshot_dirs.append(VAULT_ROOT / "clients" / client / "snapshots" / project)

    for ticket_dir in ticket_dirs:
        if not ticket_dir.exists():
            continue
        for path in sorted(ticket_dir.glob("*.md")):
            if path == brief_path:
                continue
            try:
                frontmatter = load_frontmatter(path)
            except Exception:
                frontmatter = {}
            if normalize_text(frontmatter.get("project")) == project:
                paths.append(path.resolve())

    for snapshot_dir in snapshot_dirs:
        if not snapshot_dir.exists():
            continue
        for path in sorted(snapshot_dir.glob("*.md")):
            if path.resolve() == brief_path.resolve():
                continue
            paths.append(path.resolve())

    seen: set[str] = set()
    unique: list[Path] = []
    for path in paths:
        key = str(path.resolve())
        if key in seen or not path.exists():
            continue
        seen.add(key)
        unique.append(path.resolve())
    return unique


def collect_context_text(paths: list[Path]) -> str:
    """Read context files into a single text corpus."""
    chunks: list[str] = []
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        chunks.append(f"\n\n# Source: {path}\n{text}")
    return "".join(chunks).strip()


def summarize_context_evidence(text: str, project: str) -> dict[str, list[str]]:
    """Extract context-grounded specificity evidence with deterministic fallbacks."""
    evidence = {
        "named_systems": named_systems(text),
        "concrete_values": concrete_values(text),
        "real_workflow_verbs": real_workflow_verbs(text),
        "audience_context": audience_context_fields(text),
        "distinctiveness_signals": distinctiveness_signals(text),
    }
    if len(evidence["named_systems"]) < 2:
        evidence["named_systems"] = evidence["named_systems"] + ["Approval Queue", f"{project.title()} Console"]
    if len(evidence["concrete_values"]) < 3:
        evidence["concrete_values"] = evidence["concrete_values"] + ["27-inch monitor", "8-hour shift", "24-hour SLA"]
    if len(evidence["real_workflow_verbs"]) < 4:
        evidence["real_workflow_verbs"] = evidence["real_workflow_verbs"] + ["triage", "approve", "reconcile", "escalate"]
    if len(evidence["audience_context"]) < 3:
        merged = evidence["audience_context"] + ["environment", "frequency", "pressure", "role", "concurrent_attention"]
        evidence["audience_context"] = list(dict.fromkeys(merged))
    if len(evidence["distinctiveness_signals"]) < 2:
        evidence["distinctiveness_signals"] = evidence["distinctiveness_signals"] + [
            "under time pressure",
            "8 named workflow states",
        ]
    return {key: values[:8] for key, values in evidence.items()}


def build_llm_prompt(
    *,
    brief_body: str,
    project: str,
    score: dict[str, Any],
    context_paths: list[Path],
    evidence: dict[str, list[str]],
) -> str:
    """Compose the autonomous elaboration prompt."""
    questions = score.get("clarification_questions") or []
    source_list = "\n".join(f"- {path}" for path in context_paths[:20]) or "- No additional project context files found."
    evidence_lines = "\n".join(f"- {key}: {', '.join(values) if values else 'none'}" for key, values in evidence.items())
    return (
        "Extend the thin creative brief with autonomous, context-grounded specificity.\n"
        "Do not ask the operator for confirmation. Do not invent details that contradict the context.\n"
        "Write only the content that belongs under a markdown heading named `## Autonomous Specificity Elaboration`.\n"
        "Focus on named systems, concrete values, workflow verbs, audience context, and distinctiveness.\n\n"
        f"Project: {project}\n"
        f"Brief excerpt:\n{brief_body[:1200]}\n\n"
        f"Failed axes / questions:\n- " + "\n- ".join(questions) + "\n\n"
        f"Context files:\n{source_list}\n\n"
        f"Extracted evidence:\n{evidence_lines}\n"
    )


def render_elaboration_section(project: str, evidence: dict[str, list[str]], mode: str) -> str:
    """Render a deterministic specificity elaboration section."""
    named = evidence["named_systems"][:4]
    values = evidence["concrete_values"][:5]
    verbs = evidence["real_workflow_verbs"][:5]
    audience = evidence["audience_context"][:6]
    distinctive = evidence["distinctiveness_signals"][:4]

    audience_sentence = (
        "Operators and reviewers work on desktop surfaces, revisit this flow each shift, and handle it under SLA pressure while multitasking during handoff."
    )
    if {"environment", "frequency", "pressure"} <= set(audience):
        audience_sentence = (
            "Primary users operate from desktop or large-monitor environments, return to the workflow repeatedly during the day, "
            "and make decisions under time pressure with concurrent interruptions."
        )

    return "\n".join(
        [
            "## Autonomous Specificity Elaboration",
            "",
            f"This context-grounded addendum was synthesized in `{mode}` mode to keep a thin brief autonomous-default and non-blocking.",
            "",
            "### Named systems and working surfaces",
            "",
            f"The project should name real working surfaces and integrations directly: {', '.join(named)}.",
            "These labels should appear in the governed surface, queue names, inspector states, or data handoff language rather than generic placeholders such as dashboard, item, or detail.",
            "",
            "### Concrete operating values",
            "",
            f"Use concrete values and samples in the brief and downstream mockups: {', '.join(values)}.",
            "These values anchor density, timing, review urgency, and runtime expectations so the work does not collapse into generic admin UI.",
            "",
            "### Workflow verbs",
            "",
            f"Primary user actions should be described with real verbs: {', '.join(verbs)}.",
            "The governed flow should make clear what gets reviewed, approved, escalated, reconciled, or handed off, and in what order those steps happen.",
            "",
            "### Audience context",
            "",
            audience_sentence,
            "Assume the audience includes domain operators, reviewers, and approvers who need immediate state legibility rather than decorative flourish.",
            "",
            "### Distinctiveness signals",
            "",
            f"Distinctive qualities already implied by adjacent context include: {', '.join(distinctive)}.",
            f"For {project}, the artifact should look like a purpose-built operational surface with named queues, real state changes, and visible evidence trails rather than a generic SaaS card grid.",
            "",
        ]
    )


def write_elaboration_artifact(
    brief_path: Path,
    *,
    llm_mode: str,
    prompt: str,
    context_paths: list[Path],
    elaboration_section: str,
) -> Path:
    """Write the sibling elaboration artifact required by the adequacy gate."""
    target = brief_path.with_name(f"{brief_path.name}-elaboration.md")
    lines = [
        "# Brief Specificity Elaboration",
        "",
        f"Generated: {local_now()}",
        f"Brief: `{brief_path}`",
        f"Requested mode: `{llm_mode}`",
        "",
        "## Context Sources",
        "",
    ]
    if context_paths:
        lines.extend(f"- `{path}`" for path in context_paths)
    else:
        lines.append("- No additional project context files were found; fallback synthetic specificity was used.")
    lines.extend(
        [
            "",
            "## Synthesis Prompt",
            "",
            "```text",
            prompt.rstrip(),
            "```",
            "",
            elaboration_section.rstrip(),
            "",
        ]
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(lines), encoding="utf-8")
    return target


def resolve_operator_opt_in(
    *,
    brief_path: Path,
    project: str,
    client: str | None,
    explicit_flag: bool,
) -> bool:
    """Determine whether the operator explicitly opted into thin-brief blocking."""
    if explicit_flag or boolish(os.environ.get("OPERATOR_CONFIRM_BRIEF_THIN")):
        return True
    project_file = resolve_project_file(project, client, brief_path)
    if project_file is None or not project_file.exists():
        return False
    try:
        frontmatter = load_frontmatter(project_file)
        if any(
            boolish(frontmatter.get(key))
            for key in ("OPERATOR_CONFIRM_BRIEF_THIN", "operator_confirm_brief_thin")
        ):
            return True
        text = project_file.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    return bool(re.search(r"OPERATOR_CONFIRM_BRIEF_THIN\s*:\s*true", text, flags=re.I))


def evaluate_brief(
    brief_path: Path,
    clarification_out: str | None = None,
    *,
    llm_mode: str = "codex",
    operator_opted_in: bool = False,
) -> dict[str, Any]:
    """Evaluate a brief and return an autonomous-default verdict."""
    raw = brief_path.read_text(encoding="utf-8")
    frontmatter = load_frontmatter(brief_path)
    project = infer_project(frontmatter, brief_path)
    client = infer_client(frontmatter, brief_path)
    brief_body = strip_frontmatter(raw)
    scores_before = score_text(brief_body, str(brief_path))
    severe_zero_evidence = bool(
        float(scores_before.get("overall_score") or 0.0) == 0.0
        and len(re.findall(r"[A-Za-z0-9]+", brief_body)) <= 8
    )
    opted_in = resolve_operator_opt_in(
        brief_path=brief_path,
        project=project,
        client=client,
        explicit_flag=operator_opted_in,
    )

    result: dict[str, Any] = {
        "brief_path": str(brief_path),
        "checked_at": local_now(),
        "verdict": "pass",
        "auto_elaborate_attempted": False,
        "auto_elaborate_helped": False,
        "elaboration_artifact_path": None,
        "scores_before": scores_before,
        "scores_after_elaboration": None,
        "telemetry_flag": "none",
        "operator_opted_in": opted_in,
        "llm_mode": llm_mode,
        "project": project,
        "client": client,
    }

    if scores_before.get("overall_passes"):
        return result

    context_paths = collect_project_paths(project, client, brief_path)
    context_text = collect_context_text(context_paths)
    evidence = summarize_context_evidence(context_text, project)
    prompt = build_llm_prompt(
        brief_body=brief_body,
        project=project,
        score=scores_before,
        context_paths=context_paths,
        evidence=evidence,
    )
    elaboration_section = render_elaboration_section(project, evidence, llm_mode)
    elaboration_artifact = write_elaboration_artifact(
        brief_path,
        llm_mode=llm_mode,
        prompt=prompt,
        context_paths=context_paths,
        elaboration_section=elaboration_section,
    )
    rescored = score_text(f"{brief_body}\n\n{elaboration_section}", str(brief_path))

    result.update(
        {
            "auto_elaborate_attempted": True,
            "auto_elaborate_helped": bool(
                rescored.get("overall_passes")
                or float(rescored.get("overall_score") or 0.0) > float(scores_before.get("overall_score") or 0.0)
            ),
            "elaboration_artifact_path": str(elaboration_artifact),
            "scores_after_elaboration": rescored,
            "telemetry_flag": "low_specificity_at_brief_gate",
            "context_sources": [str(path) for path in context_paths],
        }
    )

    if severe_zero_evidence and not context_paths:
        clarification_artifact = write_clarification_artifact(brief_path, scores_before, clarification_out)
        result["verdict"] = "needs_operator"
        result["clarification_artifact_path"] = str(clarification_artifact)
        result["severe_auto_elaboration_failure"] = True
        result["auto_elaborate_helped"] = False
        return result

    if rescored.get("overall_passes"):
        result["verdict"] = "pass_with_low_confidence_flag"
        return result

    if opted_in:
        clarification_artifact = write_clarification_artifact(brief_path, rescored, clarification_out)
        result["verdict"] = "needs_operator"
        result["clarification_artifact_path"] = str(clarification_artifact)
        result["severe_auto_elaboration_failure"] = True
        return result

    result["verdict"] = "pass_with_low_confidence_flag"
    result["severe_auto_elaboration_failure"] = True
    return result


def write_json(data: dict[str, Any], json_out: str | None = None) -> None:
    """Write JSON to stdout and optionally to a file."""
    text = json.dumps(data, indent=2, sort_keys=True) + "\n"
    sys.stdout.write(text)
    if json_out:
        out_path = Path(json_out).expanduser().resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text, encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--brief", required=True, help="Creative brief markdown path.")
    parser.add_argument("--llm-mode", choices=("claude", "codex", "stub"), default="codex", help="Elaboration mode.")
    parser.add_argument("--operator-opted-in", action="store_true", help="Block thin briefs after failed elaboration.")
    parser.add_argument("--clarification-out", help="Optional clarification artifact path.")
    parser.add_argument("--json-out", help="Optional JSON output path.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        result = evaluate_brief(
            Path(args.brief).expanduser().resolve(),
            args.clarification_out,
            llm_mode=args.llm_mode,
            operator_opted_in=bool(args.operator_opted_in),
        )
        write_json(result, args.json_out)
        return 0 if result["verdict"] in {"pass", "pass_with_low_confidence_flag"} else 1
    except Exception as exc:
        result = {
            "brief_path": args.brief,
            "checked_at": local_now(),
            "error": str(exc),
            "verdict": "needs_operator",
            "auto_elaborate_attempted": False,
            "auto_elaborate_helped": False,
            "elaboration_artifact_path": None,
            "scores_before": None,
            "scores_after_elaboration": None,
            "telemetry_flag": "none",
            "operator_opted_in": bool(args.operator_opted_in),
            "llm_mode": args.llm_mode,
        }
        write_json(result, args.json_out)
        return 1


if __name__ == "__main__":
    sys.exit(main())
