from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CHECK_WAVE_BRIEF_COVERAGE_PATH = REPO_ROOT / "scripts" / "check_wave_brief_coverage.py"


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
    brief_scope: str | None = None,
    phase: int | None = None,
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
    if covered_waves is not None:
        lines.append(f"covered_waves: {covered_waves}")
    lines.extend([f"captured: {captured}", f"updated: {captured}", "---", "", f"# {title}", ""])
    if body_lines:
        lines.extend(body_lines)
        lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def build_args(tmp_path: Path, *, wave: str) -> argparse.Namespace:
    return argparse.Namespace(
        project="ship-it",
        project_file=None,
        project_plan=None,
        phase=2,
        wave=wave,
        search_root=[str(tmp_path / "snapshots")],
        json_out=None,
        markdown_out=None,
    )


def test_wave_brief_coverage_passes_when_no_phase_brief_exists(tmp_path):
    check_wave_brief_coverage = load_module(
        "check_wave_brief_coverage_under_test_project_default",
        CHECK_WAVE_BRIEF_COVERAGE_PATH,
    )
    snapshots = tmp_path / "snapshots"
    write_brief(
        snapshots / "project.md",
        project="ship-it",
        title="Creative Brief — Ship It",
        captured="2026-04-08T21:00",
    )

    report = check_wave_brief_coverage.build_report(build_args(tmp_path, wave="Wave 2B"))

    assert report["verdict"] == "PASS"
    assert report["coverage_mode"] == "project_default"


def test_wave_brief_coverage_fails_when_phase_brief_exists_for_other_wave(tmp_path):
    check_wave_brief_coverage = load_module(
        "check_wave_brief_coverage_under_test_missing_supplement",
        CHECK_WAVE_BRIEF_COVERAGE_PATH,
    )
    snapshots = tmp_path / "snapshots"
    write_brief(
        snapshots / "project.md",
        project="ship-it",
        title="Creative Brief — Ship It",
        captured="2026-04-08T21:00",
    )
    write_brief(
        snapshots / "phase2-wave2a.md",
        project="ship-it",
        title="Creative Brief — Phase 2 Enterprise Hardening",
        captured="2026-04-08T21:08",
        brief_scope="phase",
        phase=2,
        body_lines=["This supplement covers Wave 2A only."],
    )

    report = check_wave_brief_coverage.build_report(build_args(tmp_path, wave="Wave 2B"))

    checks = {check["name"]: check for check in report["checks"]}
    assert report["verdict"] == "FAIL"
    assert report["coverage_mode"] == "missing_wave_supplement"
    assert checks["phase_brief_coverage"]["ok"] is False


def test_wave_brief_coverage_passes_when_phase_brief_explicitly_lists_wave(tmp_path):
    check_wave_brief_coverage = load_module(
        "check_wave_brief_coverage_under_test_covered_waves",
        CHECK_WAVE_BRIEF_COVERAGE_PATH,
    )
    snapshots = tmp_path / "snapshots"
    write_brief(
        snapshots / "project.md",
        project="ship-it",
        title="Creative Brief — Ship It",
        captured="2026-04-08T21:00",
    )
    write_brief(
        snapshots / "phase2-wave2b.md",
        project="ship-it",
        title="Creative Brief — Phase 2 Wave Supplement",
        captured="2026-04-08T21:18",
        brief_scope="phase",
        phase=2,
        covered_waves='["Wave 2B"]',
    )

    report = check_wave_brief_coverage.build_report(build_args(tmp_path, wave="Wave 2B"))

    assert report["verdict"] == "PASS"
    assert report["coverage_mode"] == "phase_scoped"
    assert report["applicable_phase_briefs"][0]["covered_waves"] == ["Wave 2B"]


def test_wave_brief_coverage_fails_without_project_master_brief(tmp_path):
    check_wave_brief_coverage = load_module(
        "check_wave_brief_coverage_under_test_missing_project",
        CHECK_WAVE_BRIEF_COVERAGE_PATH,
    )
    snapshots = tmp_path / "snapshots"
    write_brief(
        snapshots / "phase2-wave2b.md",
        project="ship-it",
        title="Creative Brief — Phase 2 Wave Supplement",
        captured="2026-04-08T21:18",
        brief_scope="phase",
        phase=2,
        covered_waves='["Wave 2B"]',
    )

    report = check_wave_brief_coverage.build_report(build_args(tmp_path, wave="Wave 2B"))

    assert report["verdict"] == "FAIL"
    assert "missing_project_brief" in report["issues"]
