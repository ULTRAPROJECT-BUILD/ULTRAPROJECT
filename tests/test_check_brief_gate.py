from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CHECK_BRIEF_GATE_PATH = REPO_ROOT / "scripts" / "check_brief_gate.py"

ADEQUATE_BRIEF_BODY = [
    "Demo Console serves operations leads using Stripe, Linear, and PagerDuty during 24/7 review.",
    "Users triage alerts every 8-hour shift, approve escalations, reconcile status, suppress duplicates, and hand off decisions within 15 minutes.",
    "The distinctive bar is a dense queue with SLA breach flags, merchant-risk states, and evidence bundle panels rather than a generic dashboard.",
]


def load_module(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def write_ticket(
    path: Path,
    *,
    ticket_id: str,
    title: str,
    project: str,
    status: str = "closed",
    updated: str = "2026-04-08T21:16",
    completed: str | None = None,
    phase: int | None = None,
) -> None:
    lines = [
        "---",
        "type: ticket",
        f"id: {ticket_id}",
        f'title: "{title}"',
        f"status: {status}",
        "task_type: creative_brief",
        f'project: "{project}"',
        "created: 2026-04-08T21:00",
        f"updated: {updated}",
        f"completed: {completed or updated}",
    ]
    if phase is not None:
        lines.append(f"phase: {phase}")
    lines.extend(["blocked_by: []", "---", "", f"# {title}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_creative_brief_snapshot(
    path: Path,
    *,
    project: str,
    title: str,
    captured: str,
    brief_scope: str | None = None,
    phase: int | None = None,
    ticket: str | None = None,
) -> None:
    lines = [
        "---",
        "type: snapshot",
        "subtype: creative-brief",
        f'title: "{title}"',
        f'project: "{project}"',
    ]
    if brief_scope is not None:
        lines.append(f"brief_scope: {brief_scope}")
    if phase is not None:
        lines.append(f"phase: {phase}")
    if ticket is not None:
        lines.append(f'ticket: "{ticket}"')
    lines.extend([f"captured: {captured}", f"updated: {captured}", "---", "", f"# {title}", ""])
    lines.extend(ADEQUATE_BRIEF_BODY)
    lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_brief_review_snapshot(
    path: Path,
    *,
    project: str,
    title: str,
    updated: str,
    grade: str,
    advance_allowed: str | None = None,
    phase: int | None = None,
    ticket: str | None = None,
    review_target: str | None = None,
    body_lines: list[str] | None = None,
) -> None:
    lines = [
        "---",
        "type: snapshot",
        "subtype: brief-review",
        f'title: "{title}"',
        f'project: "{project}"',
        f'grade: "{grade}"',
    ]
    if phase is not None:
        lines.append(f"phase: {phase}")
    if ticket is not None:
        lines.append(f'ticket: "{ticket}"')
    if review_target is not None:
        lines.append(f'review_target: "{review_target}"')
    if advance_allowed is not None:
        lines.append(f'advance_allowed: "{advance_allowed}"')
    lines.extend([f"captured: {updated}", f"updated: {updated}", "---", "", f"# {title}", ""])
    if body_lines:
        lines.extend(body_lines)
        lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def build_args(tmp_path: Path, ticket_path: Path) -> argparse.Namespace:
    return argparse.Namespace(
        ticket_path=str(ticket_path),
        required_grade="A",
        search_root=[str(tmp_path / "snapshots")],
        json_out=None,
        markdown_out=None,
    )


def test_brief_gate_passes_for_fresh_phase_review(tmp_path):
    check_brief_gate = load_module("check_brief_gate_under_test_pass", CHECK_BRIEF_GATE_PATH)
    ticket_path = tmp_path / "tickets" / "T-535-phase-2-creative-brief.md"
    snapshots = tmp_path / "snapshots"

    write_ticket(
        ticket_path,
        ticket_id="T-535",
        title="Phase 2 Creative Brief — Enterprise Hardening",
        project="ship-it",
        updated="2026-04-08T21:16",
        phase=2,
    )
    write_creative_brief_snapshot(
        snapshots / "2026-04-08-creative-brief-phase2-ship-it.md",
        project="ship-it",
        title="Creative Brief — Phase 2: Enterprise Hardening",
        captured="2026-04-08T21:08",
        brief_scope="phase",
        phase=2,
        ticket="T-535",
    )
    write_brief_review_snapshot(
        snapshots / "2026-04-08-brief-review-phase2-ship-it.md",
        project="ship-it",
        title="Brief Review — Phase 2",
        updated="2026-04-08T21:18",
        grade="A",
        advance_allowed="yes",
        phase=2,
        body_lines=["Reviewed `2026-04-08-creative-brief-phase2-ship-it.md`."],
    )

    report = check_brief_gate.build_report(build_args(tmp_path, ticket_path))

    checks = {check["name"]: check for check in report["checks"]}
    assert report["verdict"] == "PASS"
    assert report["target_brief"]["scope"] == "phase"
    assert checks["review_fresh"]["ok"] is True
    assert checks["review_passes_threshold"]["ok"] is True


def test_brief_gate_fails_without_matching_review(tmp_path):
    check_brief_gate = load_module("check_brief_gate_under_test_missing", CHECK_BRIEF_GATE_PATH)
    ticket_path = tmp_path / "tickets" / "T-535-phase-2-creative-brief.md"
    snapshots = tmp_path / "snapshots"

    write_ticket(
        ticket_path,
        ticket_id="T-535",
        title="Phase 2 Creative Brief — Enterprise Hardening",
        project="ship-it",
        updated="2026-04-08T21:16",
        phase=2,
    )
    write_creative_brief_snapshot(
        snapshots / "2026-04-08-creative-brief-phase2-ship-it.md",
        project="ship-it",
        title="Creative Brief — Phase 2: Enterprise Hardening",
        captured="2026-04-08T21:08",
        brief_scope="phase",
        phase=2,
        ticket="T-535",
    )

    report = check_brief_gate.build_report(build_args(tmp_path, ticket_path))

    checks = {check["name"]: check for check in report["checks"]}
    assert report["verdict"] == "FAIL"
    assert checks["matching_review_found"]["ok"] is False
    assert checks["review_passes_threshold"]["ok"] is False


def test_brief_gate_prefers_project_brief_for_project_scope_ticket(tmp_path):
    check_brief_gate = load_module("check_brief_gate_under_test_project_scope", CHECK_BRIEF_GATE_PATH)
    ticket_path = tmp_path / "tickets" / "T-486-creative-brief-ship-it.md"
    snapshots = tmp_path / "snapshots"

    write_ticket(
        ticket_path,
        ticket_id="T-486",
        title="Creative brief — Project #048 Ship It (project-scope)",
        project="ship-it",
        updated="2026-04-07T02:15",
        phase=0,
    )
    write_creative_brief_snapshot(
        snapshots / "2026-04-07-creative-brief-ship-it.md",
        project="ship-it",
        title="Creative Brief — Project #048 Ship It",
        captured="2026-04-07T00:36",
        brief_scope="project",
    )
    write_brief_review_snapshot(
        snapshots / "2026-04-07-brief-review-v5-ship-it.md",
        project="ship-it",
        title="Brief Review v5 — Ship It",
        updated="2026-04-07T02:16",
        grade="A",
        body_lines=["Reviewed `2026-04-07-creative-brief-ship-it.md`."],
    )
    write_creative_brief_snapshot(
        snapshots / "2026-04-07-creative-brief-phase0-ship-it.md",
        project="ship-it",
        title="Creative Brief — Phase 0",
        captured="2026-04-07T03:00",
        brief_scope="phase",
        phase=0,
        ticket="T-999",
    )
    write_brief_review_snapshot(
        snapshots / "2026-04-07-brief-review-phase0-ship-it.md",
        project="ship-it",
        title="Brief Review — Phase 0",
        updated="2026-04-07T03:05",
        grade="A",
        advance_allowed="yes",
        phase=0,
        body_lines=["Reviewed `2026-04-07-creative-brief-phase0-ship-it.md`."],
    )

    report = check_brief_gate.build_report(build_args(tmp_path, ticket_path))

    assert report["verdict"] == "PASS"
    assert report["target_brief"]["scope"] == "project"
    assert report["target_brief"]["path"].endswith("2026-04-07-creative-brief-ship-it.md")
    assert report["latest_review"]["path"].endswith("2026-04-07-brief-review-v5-ship-it.md")


def test_brief_gate_requires_review_after_ticket_close(tmp_path):
    check_brief_gate = load_module("check_brief_gate_under_test_stale", CHECK_BRIEF_GATE_PATH)
    ticket_path = tmp_path / "tickets" / "T-535-phase-2-creative-brief.md"
    snapshots = tmp_path / "snapshots"

    write_ticket(
        ticket_path,
        ticket_id="T-535",
        title="Phase 2 Creative Brief — Enterprise Hardening",
        project="ship-it",
        updated="2026-04-08T21:16",
        phase=2,
    )
    write_creative_brief_snapshot(
        snapshots / "2026-04-08-creative-brief-phase2-ship-it.md",
        project="ship-it",
        title="Creative Brief — Phase 2: Enterprise Hardening",
        captured="2026-04-08T21:08",
        brief_scope="phase",
        phase=2,
        ticket="T-535",
    )
    write_brief_review_snapshot(
        snapshots / "2026-04-08-brief-review-phase2-ship-it.md",
        project="ship-it",
        title="Brief Review — Phase 2",
        updated="2026-04-08T21:15",
        grade="A",
        advance_allowed="yes",
        phase=2,
        body_lines=["Reviewed `2026-04-08-creative-brief-phase2-ship-it.md`."],
    )

    report = check_brief_gate.build_report(build_args(tmp_path, ticket_path))

    checks = {check["name"]: check for check in report["checks"]}
    assert report["verdict"] == "FAIL"
    assert checks["review_fresh"]["ok"] is False


def test_brief_gate_ignores_post_close_ticket_bump_when_brief_and_review_are_fresh(tmp_path):
    check_brief_gate = load_module("check_brief_gate_under_test_post_close_bump", CHECK_BRIEF_GATE_PATH)
    ticket_path = tmp_path / "tickets" / "T-769-wave-1c-brief-supplement.md"
    snapshots = tmp_path / "snapshots"
    brief_path = snapshots / "2026-04-18-wave-1c-brief-supplement.md"

    write_ticket(
        ticket_path,
        ticket_id="T-769",
        title="Wave 1C brief supplement — Agent Console + Live Watch",
        project="employee-platform-upgrades",
        completed="2026-04-18T12:06",
        updated="2026-04-18T14:15",
        phase=1,
    )
    write_creative_brief_snapshot(
        brief_path,
        project="employee-platform-upgrades",
        title="Wave 1C Brief Supplement — Agent Console + Live Watch",
        captured="2026-04-18T11:56",
        brief_scope="ticket",
        phase=1,
        ticket="T-769",
    )
    write_brief_review_snapshot(
        snapshots / "noncanonical-wave-1c-review-name.md",
        project="employee-platform-upgrades",
        title="Brief Review — Wave 1C",
        updated="2026-04-18T12:14",
        grade="A",
        advance_allowed="yes",
        ticket="T-769",
        review_target=str(brief_path),
    )

    report = check_brief_gate.build_report(build_args(tmp_path, ticket_path))

    checks = {check["name"]: check for check in report["checks"]}
    assert report["verdict"] == "PASS"
    assert report["freshness_anchor"] == "2026-04-18T12:06:00"
    assert checks["review_fresh"]["ok"] is True
    assert report["latest_review"]["path"].endswith("noncanonical-wave-1c-review-name.md")


def test_brief_gate_requires_review_after_delivered_brief_amendment(tmp_path):
    check_brief_gate = load_module("check_brief_gate_under_test_brief_amendment", CHECK_BRIEF_GATE_PATH)
    ticket_path = tmp_path / "tickets" / "T-769-wave-1c-brief-supplement.md"
    snapshots = tmp_path / "snapshots"
    brief_path = snapshots / "2026-04-18-wave-1c-brief-supplement.md"

    write_ticket(
        ticket_path,
        ticket_id="T-769",
        title="Wave 1C brief supplement — Agent Console + Live Watch",
        project="employee-platform-upgrades",
        completed="2026-04-18T12:06",
        updated="2026-04-18T14:15",
        phase=1,
    )
    write_creative_brief_snapshot(
        brief_path,
        project="employee-platform-upgrades",
        title="Wave 1C Brief Supplement — Agent Console + Live Watch",
        captured="2026-04-18T13:59",
        brief_scope="ticket",
        phase=1,
        ticket="T-769",
    )
    write_brief_review_snapshot(
        snapshots / "noncanonical-wave-1c-review-name.md",
        project="employee-platform-upgrades",
        title="Brief Review — Wave 1C",
        updated="2026-04-18T12:14",
        grade="A",
        advance_allowed="yes",
        ticket="T-769",
        review_target=str(brief_path),
    )

    report = check_brief_gate.build_report(build_args(tmp_path, ticket_path))

    checks = {check["name"]: check for check in report["checks"]}
    assert report["verdict"] == "FAIL"
    assert report["freshness_anchor"] == "2026-04-18T13:59:00"
    assert checks["review_fresh"]["ok"] is False
