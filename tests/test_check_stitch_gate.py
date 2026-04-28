from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CHECK_STITCH_GATE_PATH = REPO_ROOT / "scripts" / "check_stitch_gate.py"


def load_module(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def write_ticket(path: Path, *, route_family_required: bool) -> None:
    path.write_text(
        "\n".join(
            [
                "---",
                "type: ticket",
                "id: T-673",
                'title: "Pending Review route family alignment"',
                "status: closed",
                "task_type: code_build",
                'project: "employee-platform"',
                "created: 2026-04-10T12:00",
                "updated: 2026-04-10T12:00",
                "ui_work: true",
                'design_mode: "stitch_required"',
                "existing_surface_redesign: false",
                f"route_family_required: {'true' if route_family_required else 'false'}",
                "---",
                "",
                "# Pending Review route family alignment",
            ]
        ),
        encoding="utf-8",
    )


def write_brief(path: Path, *, include_route_family: bool) -> None:
    lines = [
        "# Creative Brief",
        "",
        "## Visual Quality Bar",
        "- Calm operator workbench, not a generic admin template.",
        "",
        "## Visual Targets (Stitch)",
        "",
        "| Screen Name | Stitch ID | State | QC Comparison |",
        "|------------|-----------|-------|---------------|",
        "| PendingReview-default | screens/pending-review-v1 | default | Compare runtime review queue state |",
        "",
        "## Composition Anchors",
        "- Primary list-detail workbench with one dominant review pane and one supporting context rail",
        "- Dense operator shell with calm hierarchy, not a pile of equally weighted cards",
        "",
    ]
    if include_route_family:
        lines.extend(
            [
                "## Route Family",
                "- Family name: `Operator Workbench`",
                "- Reuse from: `Feedback`, `Approvals`",
                "- Shared invariants: one dominant work area, subordinate context rail, no filler metric rail",
                "",
            ]
        )
    path.write_text("\n".join(lines), encoding="utf-8")


def write_qc_report(path: Path, *, mention_route_family: bool) -> None:
    lines = [
        "# QC Report",
        "",
        "Compared Stitch target `screens/pending-review-v1` against runtime screenshot `qc-pending-review-runtime.png`.",
        "Comparison verdict: layout parity holds.",
        "Primary list-detail workbench with one dominant review pane and one supporting context rail is preserved.",
        "Dense operator shell with calm hierarchy, not a pile of equally weighted cards is preserved.",
    ]
    if mention_route_family:
        lines.append(
            "Route family parity clears: same-product-family audit passed, and the page avoids generic admin layout drift."
        )
    path.write_text("\n".join(lines), encoding="utf-8")


def build_args(tmp_path: Path) -> argparse.Namespace:
    return argparse.Namespace(
        brief=[str(tmp_path / "brief.md")],
        qc_report=[str(tmp_path / "qc.md")],
        ticket_path=str(tmp_path / "T-673.md"),
        deliverables_root=str(tmp_path / "deliverable"),
        stitch_root=None,
        min_screen_targets=1,
        json_out=str(tmp_path / "out.json"),
        markdown_out=str(tmp_path / "out.md"),
    )


def create_stitch_files(tmp_path: Path) -> None:
    stitch_root = tmp_path / "deliverable" / ".stitch"
    designs_root = stitch_root / "designs" / "benchmarks"
    designs_root.mkdir(parents=True)
    (stitch_root / "DESIGN.md").write_text("# design", encoding="utf-8")
    (designs_root / "pending-review.html").write_text("<html></html>", encoding="utf-8")
    (designs_root / "pending-review.png").write_bytes(b"png")
    (tmp_path / "deliverable" / "qc-pending-review-runtime.png").write_bytes(b"png")


def test_stitch_gate_passes_route_family_surface_with_parity_evidence(tmp_path):
    check_stitch_gate = load_module("check_stitch_gate_route_family_pass", CHECK_STITCH_GATE_PATH)
    create_stitch_files(tmp_path)
    write_ticket(tmp_path / "T-673.md", route_family_required=True)
    write_brief(tmp_path / "brief.md", include_route_family=True)
    write_qc_report(tmp_path / "qc.md", mention_route_family=True)

    report = check_stitch_gate.build_report(build_args(tmp_path))
    checks = {check["name"]: check for check in report["checks"]}

    assert report["verdict"] == "PASS"
    assert report["brief_analysis"]["route_family_required"] is True
    assert checks["brief_has_route_family"]["ok"] is True
    assert checks["brief_has_composition_anchors_for_route_family"]["ok"] is True
    assert checks["qc_mentions_route_family_parity"]["ok"] is True
    assert checks["qc_references_route_family_composition_anchors"]["ok"] is True


def test_stitch_gate_fails_route_family_surface_without_route_family_section(tmp_path):
    check_stitch_gate = load_module("check_stitch_gate_route_family_fail", CHECK_STITCH_GATE_PATH)
    create_stitch_files(tmp_path)
    write_ticket(tmp_path / "T-673.md", route_family_required=True)
    write_brief(tmp_path / "brief.md", include_route_family=False)
    write_qc_report(tmp_path / "qc.md", mention_route_family=True)

    report = check_stitch_gate.build_report(build_args(tmp_path))
    checks = {check["name"]: check for check in report["checks"]}

    assert report["verdict"] == "FAIL"
    assert checks["brief_has_route_family"]["ok"] is False
