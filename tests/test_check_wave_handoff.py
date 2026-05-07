from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CHECK_WAVE_HANDOFF_PATH = REPO_ROOT / "scripts" / "check_wave_handoff.py"


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
    status: str,
    task_type: str = "code_build",
    updated: str = "2026-04-08T23:30",
    phase: int = 2,
    wave: str = "2A",
) -> None:
    lines = [
        "---",
        "type: ticket",
        f"id: {ticket_id}",
        f'title: "{title}"',
        f"status: {status}",
        f"task_type: {task_type}",
        f'project: "{project}"',
        "created: 2026-04-08T23:00",
        f"updated: {updated}",
        f"completed: {updated}",
        f"phase: {phase}",
        f'wave: "{wave}"',
        "blocked_by: []",
        "---",
        "",
        f"# {title}",
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_brief(
    path: Path,
    *,
    project: str,
    title: str,
    captured: str,
    brief_scope: str | None = None,
    phase: int | None = None,
    ticket: str | None = None,
    covered_waves: str | None = None,
    body_lines: list[str] | None = None,
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
    if covered_waves is not None:
        lines.append(f"covered_waves: {covered_waves}")
    lines.extend([f"captured: {captured}", f"updated: {captured}", "---", "", f"# {title}", ""])
    if body_lines:
        lines.extend(body_lines)
        lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_brief_review(
    path: Path,
    *,
    project: str,
    title: str,
    updated: str,
    grade: str = "A",
    advance_allowed: str | None = "yes",
    phase: int | None = None,
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
    if advance_allowed is not None:
        lines.append(f'advance_allowed: "{advance_allowed}"')
    lines.extend([f"captured: {updated}", f"updated: {updated}", "---", "", f"# {title}", ""])
    if body_lines:
        lines.extend(body_lines)
        lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_plan(path: Path, *, project: str, rows: list[tuple[str, str, str]]) -> None:
    lines = [
        "---",
        "type: snapshot",
        "subtype: project-plan",
        f'project: "{project}"',
        "captured: 2026-04-08T23:28",
        "updated: 2026-04-08T23:28",
        "---",
        "",
        f"# Project Plan — {project}",
        "",
        "## Dynamic Wave Log",
        "",
        "| Wave | Status | Anchor Phase | Capability Lanes | Purpose | Success Signal | Tickets |",
        "|---|---|---|---|---|---|---|",
    ]
    for wave, status, tickets in rows:
        lines.append(f"| {wave} | {status} | Phase 2 | lane | purpose | signal | {tickets} |")
    lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def build_args(tmp_path: Path, *, closing_wave: str = "Wave 2A", next_wave: str | None = "Wave 2B") -> argparse.Namespace:
    return argparse.Namespace(
        project_plan=str(tmp_path / "snapshots" / "project-plan.md"),
        tickets_dir=str(tmp_path / "tickets"),
        phase=2,
        closing_wave=closing_wave,
        next_wave=next_wave,
        search_root=[str(tmp_path / "snapshots")],
        json_out=None,
        markdown_out=None,
    )


def test_wave_handoff_green_when_wave_closed_and_next_wave_covered(tmp_path):
    check_wave_handoff = load_module("check_wave_handoff_under_test_green", CHECK_WAVE_HANDOFF_PATH)
    snapshots = tmp_path / "snapshots"
    tickets = tmp_path / "tickets"

    write_plan(
        snapshots / "project-plan.md",
        project="ship-it",
        rows=[("Wave 2A", "active", "T-600, T-601"), ("Wave 2B", "planned", "T-602")],
    )
    write_brief(
        snapshots / "project-brief.md",
        project="ship-it",
        title="Creative Brief — Ship It",
        captured="2026-04-08T21:00",
    )
    write_ticket(tickets / "T-600-wave-brief.md", ticket_id="T-600", title="Wave 2A Brief", project="ship-it", status="closed", task_type="creative_brief")
    write_ticket(tickets / "T-601-wave-build.md", ticket_id="T-601", title="Wave 2A Build", project="ship-it", status="closed")
    write_ticket(tickets / "T-602-wave-next.md", ticket_id="T-602", title="Wave 2B Build", project="ship-it", status="open", wave="2B")
    write_brief(
        snapshots / "wave2a-brief.md",
        project="ship-it",
        title="Creative Brief — Phase 2 Enterprise Hardening",
        captured="2026-04-08T23:10",
        brief_scope="phase",
        phase=2,
        ticket="T-600",
    )
    write_brief_review(
        snapshots / "wave2a-brief-review.md",
        project="ship-it",
        title="Brief Review — Wave 2A",
        updated="2026-04-08T23:31",
        phase=2,
        body_lines=["Reviewed `wave2a-brief.md`."],
    )

    report = check_wave_handoff.build_report(build_args(tmp_path))

    assert report["verdict"] == "PASS"
    assert report["handoff_state"] == "GREEN"
    assert report["next_wave"] == "Wave 2B"


def test_wave_handoff_yellow_when_next_wave_needs_supplement(tmp_path):
    check_wave_handoff = load_module("check_wave_handoff_under_test_yellow", CHECK_WAVE_HANDOFF_PATH)
    snapshots = tmp_path / "snapshots"
    tickets = tmp_path / "tickets"

    write_plan(
        snapshots / "project-plan.md",
        project="ship-it",
        rows=[("Wave 2A", "active", "T-610"), ("Wave 2B", "planned", "T-611")],
    )
    write_brief(
        snapshots / "project-brief.md",
        project="ship-it",
        title="Creative Brief — Ship It",
        captured="2026-04-08T21:00",
    )
    write_brief(
        snapshots / "phase2-wave2a.md",
        project="ship-it",
        title="Creative Brief — Phase 2 Wave 2A",
        captured="2026-04-08T21:08",
        brief_scope="phase",
        phase=2,
        covered_waves='["Wave 2A"]',
    )
    write_ticket(tickets / "T-610-wave2a-build.md", ticket_id="T-610", title="Wave 2A Build", project="ship-it", status="closed")
    write_ticket(tickets / "T-611-wave2b-build.md", ticket_id="T-611", title="Wave 2B Build", project="ship-it", status="open", wave="2B")

    report = check_wave_handoff.build_report(build_args(tmp_path))

    assert report["verdict"] == "PASS"
    assert report["handoff_state"] == "YELLOW"
    assert "next_wave_requires_supplement_brief" in report["issues"]


def test_wave_handoff_red_when_closing_wave_ticket_still_open(tmp_path):
    check_wave_handoff = load_module("check_wave_handoff_under_test_red_open", CHECK_WAVE_HANDOFF_PATH)
    snapshots = tmp_path / "snapshots"
    tickets = tmp_path / "tickets"

    write_plan(
        snapshots / "project-plan.md",
        project="ship-it",
        rows=[("Wave 2A", "active", "T-620"), ("Wave 2B", "planned", "T-621")],
    )
    write_brief(
        snapshots / "project-brief.md",
        project="ship-it",
        title="Creative Brief — Ship It",
        captured="2026-04-08T21:00",
    )
    write_ticket(tickets / "T-620-wave2a-build.md", ticket_id="T-620", title="Wave 2A Build", project="ship-it", status="in-progress")
    write_ticket(tickets / "T-621-wave2b-build.md", ticket_id="T-621", title="Wave 2B Build", project="ship-it", status="open", wave="2B")

    report = check_wave_handoff.build_report(build_args(tmp_path))

    assert report["verdict"] == "FAIL"
    assert report["handoff_state"] == "RED"
    assert "closing_wave_has_open_tickets" in report["issues"]


def test_wave_handoff_red_when_closing_wave_brief_gate_failed(tmp_path):
    check_wave_handoff = load_module("check_wave_handoff_under_test_red_brief", CHECK_WAVE_HANDOFF_PATH)
    snapshots = tmp_path / "snapshots"
    tickets = tmp_path / "tickets"

    write_plan(
        snapshots / "project-plan.md",
        project="ship-it",
        rows=[("Wave 2A", "active", "T-630"), ("Wave 2B", "planned", "T-631")],
    )
    write_brief(
        snapshots / "project-brief.md",
        project="ship-it",
        title="Creative Brief — Ship It",
        captured="2026-04-08T21:00",
    )
    write_ticket(
        tickets / "T-630-wave2a-brief.md",
        ticket_id="T-630",
        title="Wave 2A Creative Brief",
        project="ship-it",
        status="closed",
        task_type="creative_brief",
    )
    write_ticket(tickets / "T-631-wave2b-build.md", ticket_id="T-631", title="Wave 2B Build", project="ship-it", status="open", wave="2B")
    write_brief(
        snapshots / "wave2a-brief.md",
        project="ship-it",
        title="Creative Brief — Wave 2A",
        captured="2026-04-08T23:10",
        brief_scope="phase",
        phase=2,
        ticket="T-630",
        covered_waves='["Wave 2A"]',
    )

    report = check_wave_handoff.build_report(build_args(tmp_path))

    assert report["verdict"] == "FAIL"
    assert report["handoff_state"] == "RED"
    assert "closing_wave_brief_gate_failed" in report["issues"]
