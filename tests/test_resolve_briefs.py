from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
RESOLVE_BRIEFS_PATH = REPO_ROOT / "scripts" / "resolve_briefs.py"


def load_module(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def write_brief(
    path: Path,
    *,
    project: str,
    title: str,
    captured: str,
    updated: str | None = None,
    brief_scope: str | None = None,
    phase: int | None = None,
    phase_number: int | None = None,
    ticket: str | None = None,
    applies_to_tickets: str | None = None,
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
    if phase_number is not None:
        lines.append(f"phase_number: {phase_number}")
    if ticket is not None:
        lines.append(f'ticket: "{ticket}"')
    if applies_to_tickets is not None:
        lines.append(f"applies_to_tickets: {applies_to_tickets}")
    lines.extend(
        [
            f"captured: {captured}",
            f"updated: {updated or captured}",
            "---",
            "",
            f"# {title}",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def test_resolve_briefs_prefers_project_then_latest_phase_then_ticket(tmp_path):
    resolve_briefs = load_module("resolve_briefs_under_test_order", RESOLVE_BRIEFS_PATH)
    snapshots = tmp_path / "snapshots"

    write_brief(
        snapshots / "2026-04-01-creative-brief-demo-project.md",
        project="demo-project",
        title="Creative Brief — Demo Project",
        captured="2026-04-01T09:00",
    )
    write_brief(
        snapshots / "2026-04-02-creative-brief-phase5-legacy.md",
        project="demo-project",
        title="Creative Brief — Phase 5 Legacy",
        captured="2026-04-02T09:00",
        phase=5,
    )
    write_brief(
        snapshots / "2026-04-03-creative-brief-phase5-explicit.md",
        project="demo-project",
        title="Creative Brief — Phase 5 Explicit",
        captured="2026-04-03T09:00",
        brief_scope="phase",
        phase_number=5,
    )
    write_brief(
        snapshots / "2026-04-04-creative-brief-ticket-t123.md",
        project="demo-project",
        title="Creative Brief — Ticket T-123",
        captured="2026-04-04T09:00",
        brief_scope="ticket",
        ticket="T-123",
    )

    report = resolve_briefs.build_report(
        argparse.Namespace(
            project="demo-project",
            project_file=None,
            project_plan=None,
            phase=5,
            wave=None,
            ticket_id="T-123",
            ticket_path=None,
            search_root=[str(snapshots)],
            json_out=None,
            markdown_out=None,
        )
    )

    ordered_titles = [entry["title"] for entry in report["ordered_briefs"]]
    phase_titles = [entry["title"] for entry in report["phase_briefs"]]

    assert ordered_titles == [
        "Creative Brief — Demo Project",
        "Creative Brief — Phase 5 Explicit",
        "Creative Brief — Ticket T-123",
    ]
    assert phase_titles == [
        "Creative Brief — Phase 5 Explicit",
        "Creative Brief — Phase 5 Legacy",
    ]


def test_resolve_briefs_matches_ticket_supplement_via_applies_to_list(tmp_path):
    resolve_briefs = load_module("resolve_briefs_under_test_applies", RESOLVE_BRIEFS_PATH)
    snapshots = tmp_path / "snapshots"

    write_brief(
        snapshots / "project.md",
        project="demo-project",
        title="Creative Brief — Demo Project",
        captured="2026-04-01T09:00",
    )
    write_brief(
        snapshots / "phase6.md",
        project="demo-project",
        title="Creative Brief — Phase 6",
        captured="2026-04-02T09:00",
        brief_scope="phase",
        phase_number=6,
    )
    write_brief(
        snapshots / "ticket-supplement.md",
        project="demo-project",
        title="Creative Brief — Stress Test Supplement",
        captured="2026-04-03T09:00",
        brief_scope="ticket",
        applies_to_tickets='["T-415", "T-416"]',
    )

    report = resolve_briefs.build_report(
        argparse.Namespace(
            project="demo-project",
            project_file=None,
            project_plan=None,
            phase=6,
            wave=None,
            ticket_id="T-415",
            ticket_path=None,
            search_root=[str(snapshots)],
            json_out=None,
            markdown_out=None,
        )
    )

    ordered_titles = [entry["title"] for entry in report["ordered_briefs"]]

    assert ordered_titles == [
        "Creative Brief — Demo Project",
        "Creative Brief — Phase 6",
        "Creative Brief — Stress Test Supplement",
    ]


def test_resolve_briefs_flags_phase_brief_without_master_project_brief(tmp_path):
    resolve_briefs = load_module("resolve_briefs_under_test_integrity", RESOLVE_BRIEFS_PATH)
    snapshots = tmp_path / "snapshots"

    write_brief(
        snapshots / "phase0.md",
        project="demo-project",
        title="Creative Brief — Phase 0",
        captured="2026-04-05T09:00",
        brief_scope="phase",
        phase_number=0,
    )

    report = resolve_briefs.build_report(
        argparse.Namespace(
            project="demo-project",
            project_file=None,
            project_plan=None,
            phase=0,
            wave=None,
            ticket_id=None,
            ticket_path=None,
            search_root=[str(snapshots)],
            json_out=None,
            markdown_out=None,
        )
    )

    assert report["ordered_briefs"][0]["title"] == "Creative Brief — Phase 0"
    assert report["integrity_checks"]["missing_project_brief"] is True
    assert report["integrity_checks"]["phase_brief_without_project_brief"] is True
    assert "missing_project_brief" in report["issues"]


def test_resolve_briefs_filters_phase_brief_by_wave_coverage(tmp_path):
    resolve_briefs = load_module("resolve_briefs_under_test_wave_filter", RESOLVE_BRIEFS_PATH)
    snapshots = tmp_path / "snapshots"

    write_brief(
        snapshots / "project.md",
        project="demo-project",
        title="Creative Brief — Demo Project",
        captured="2026-04-01T09:00",
    )
    write_brief(
        snapshots / "phase2-wave2a.md",
        project="demo-project",
        title="Creative Brief — Phase 2 Wave 2A",
        captured="2026-04-02T09:00",
        brief_scope="phase",
        phase_number=2,
    )
    write_brief(
        snapshots / "phase2-wave2b.md",
        project="demo-project",
        title="Creative Brief — Phase 2 Enterprise Hardening",
        captured="2026-04-03T09:00",
        brief_scope="phase",
        phase_number=2,
        applies_to_tickets='[]',
    )
    wave2b_path = snapshots / "phase2-wave2b.md"
    wave2b_path.write_text(
        wave2b_path.read_text(encoding="utf-8") + "This supplement covers Wave 2B only.\n",
        encoding="utf-8",
    )

    report = resolve_briefs.build_report(
        argparse.Namespace(
            project="demo-project",
            project_file=None,
            project_plan=None,
            phase=2,
            wave="Wave 2B",
            ticket_id=None,
            ticket_path=None,
            search_root=[str(snapshots)],
            json_out=None,
            markdown_out=None,
        )
    )

    phase_titles = [entry["title"] for entry in report["phase_briefs"]]
    ordered_titles = [entry["title"] for entry in report["ordered_briefs"]]

    assert phase_titles == ["Creative Brief — Phase 2 Enterprise Hardening"]
    assert ordered_titles == [
        "Creative Brief — Demo Project",
        "Creative Brief — Phase 2 Enterprise Hardening",
    ]
