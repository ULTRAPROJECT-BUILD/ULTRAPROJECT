from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CHECK_VISUAL_GATE_PATH = REPO_ROOT / "scripts" / "check_visual_gate.py"


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
    public_surface: bool = False,
    page_contract_required: bool = False,
    route_family_required: bool = False,
    existing_surface_redesign: bool = False,
) -> None:
    path.write_text(
        "\n".join(
            [
                "---",
                "type: ticket",
                "id: T-673",
                'title: "Pending Review route family alignment"',
                "status: closed",
                "task_type: visual_review",
                'project: "employee-platform"',
                "created: 2026-04-14T09:00",
                "updated: 2026-04-14T09:00",
                "ui_work: true",
                'design_mode: "stitch_required"',
                f"public_surface: {'true' if public_surface else 'false'}",
                f"page_contract_required: {'true' if page_contract_required else 'false'}",
                f"route_family_required: {'true' if route_family_required else 'false'}",
                f"existing_surface_redesign: {'true' if existing_surface_redesign else 'false'}",
                "---",
                "",
                "# Visual gate ticket",
            ]
        ),
        encoding="utf-8",
    )


def write_brief(path: Path, *, public_surface: bool = False, route_family_required: bool = False) -> None:
    lines = [
        "# Creative Brief",
        "",
        "## Visual Quality Bar",
        "- Calm operator workbench, not a generic admin template.",
        "",
        "## Composition Anchors",
        "- One dominant work area with subordinate support zones",
        "- No equal-weight card soup or filler metric rail",
        "",
    ]
    if public_surface:
        lines.extend(
            [
                "## Narrative Structure",
                "- Strong first impression and trust layer",
                "",
            ]
        )
    if route_family_required:
        lines.extend(
            [
                "## Route Family",
                "- Family: Operator Workbench",
                "- Siblings: Feedback, Approvals",
                "",
            ]
        )
    path.write_text("\n".join(lines), encoding="utf-8")


def write_qc_report(path: Path, *, screenshot_name: str) -> None:
    path.write_text(
        "\n".join(
            [
                "# QC Report",
                "",
                f"Compared runtime screenshot `{screenshot_name}` against the approved route family expectations.",
                "Route family parity clears and the page avoids generic admin template drift.",
            ]
        ),
        encoding="utf-8",
    )


def write_visual_review(
    path: Path,
    *,
    screenshot_name: str,
    verdict: str = "PASS",
    inspected_images: bool = True,
    composition_anchor_parity: str = "pass",
    route_family_parity: str = "pass",
    page_contract_parity: str = "not_applicable",
    visual_quality_bar: str = "not_applicable",
    generic_admin_drift: str = "no",
    duplicate_shell_chrome: str = "no",
    stitch_runtime_parity: str = "pass",
    stitch_surface_traceability: str = "pass",
    token_only_basis: str = "no",
) -> None:
    path.write_text(
        "\n".join(
            [
                "---",
                f"verdict: {verdict}",
                f"inspected_images: {'true' if inspected_images else 'false'}",
                "screenshot_files:",
                f"  - {screenshot_name}",
                f"composition_anchor_parity: {composition_anchor_parity}",
                f"route_family_parity: {route_family_parity}",
                f"page_contract_parity: {page_contract_parity}",
                f"visual_quality_bar: {visual_quality_bar}",
                f"generic_admin_drift: {generic_admin_drift}",
                f"duplicate_shell_chrome: {duplicate_shell_chrome}",
                f"stitch_runtime_parity: {stitch_runtime_parity}",
                f"stitch_surface_traceability: {stitch_surface_traceability}",
                f"token_only_basis: {token_only_basis}",
                "---",
                "",
                "## Visual Verdict",
                "",
                "PASS",
                "",
                "## Evidence Reviewed",
                "",
                f"- {screenshot_name}",
                "",
                "## Stitch Fidelity",
                "",
                "- Runtime matches the governed Stitch target at the surface level, not just tokens.",
                "- Reviewer mapped the runtime surface back to the approved Stitch target family.",
                "",
                "## Findings",
                "",
                "- Dominant work area survives.",
                "",
                "## Required Fixes",
                "",
                "- None.",
                "",
            ]
        ),
        encoding="utf-8",
    )


def build_args(tmp_path: Path) -> argparse.Namespace:
    return argparse.Namespace(
        brief=[str(tmp_path / "brief.md")],
        qc_report=[str(tmp_path / "qc.md")],
        ticket_path=str(tmp_path / "T-673.md"),
        visual_review_report=str(tmp_path / "visual-review.md"),
        deliverables_root=str(tmp_path / "deliverable"),
        json_out=str(tmp_path / "out.json"),
        markdown_out=str(tmp_path / "out.md"),
    )


def test_visual_gate_passes_route_family_surface_with_structured_review(tmp_path):
    check_visual_gate = load_module("check_visual_gate_route_family_pass", CHECK_VISUAL_GATE_PATH)
    deliverable = tmp_path / "deliverable"
    deliverable.mkdir()
    screenshot_name = "qc-pending-review-runtime.png"
    (deliverable / screenshot_name).write_bytes(b"png")
    write_ticket(tmp_path / "T-673.md", route_family_required=True, existing_surface_redesign=True)
    write_brief(tmp_path / "brief.md", route_family_required=True)
    write_qc_report(tmp_path / "qc.md", screenshot_name=screenshot_name)
    write_visual_review(tmp_path / "visual-review.md", screenshot_name=screenshot_name)

    report = check_visual_gate.build_report(build_args(tmp_path))
    checks = {check["name"]: check for check in report["checks"]}

    assert report["verdict"] == "PASS"
    assert checks["visual_review_pass"]["ok"] is True
    assert checks["visual_review_clears_stitch_runtime_parity"]["ok"] is True
    assert checks["visual_review_clears_stitch_surface_traceability"]["ok"] is True
    assert checks["visual_review_rejects_token_only_stitch_basis"]["ok"] is True
    assert checks["visual_review_clears_route_family_parity"]["ok"] is True
    assert checks["visual_review_rejects_generic_admin_drift"]["ok"] is True
    assert checks["visual_review_rejects_duplicate_shell_chrome"]["ok"] is True


def test_visual_gate_fails_route_family_surface_on_generic_admin_drift(tmp_path):
    check_visual_gate = load_module("check_visual_gate_route_family_fail", CHECK_VISUAL_GATE_PATH)
    deliverable = tmp_path / "deliverable"
    deliverable.mkdir()
    screenshot_name = "qc-pending-review-runtime.png"
    (deliverable / screenshot_name).write_bytes(b"png")
    write_ticket(tmp_path / "T-673.md", route_family_required=True)
    write_brief(tmp_path / "brief.md", route_family_required=True)
    write_qc_report(tmp_path / "qc.md", screenshot_name=screenshot_name)
    write_visual_review(
        tmp_path / "visual-review.md",
        screenshot_name=screenshot_name,
        generic_admin_drift="yes",
        route_family_parity="fail",
    )

    report = check_visual_gate.build_report(build_args(tmp_path))
    checks = {check["name"]: check for check in report["checks"]}

    assert report["verdict"] == "FAIL"
    assert checks["visual_review_clears_route_family_parity"]["ok"] is False
    assert checks["visual_review_rejects_generic_admin_drift"]["ok"] is False


def test_visual_gate_fails_stitch_required_review_when_traceability_is_token_only(tmp_path):
    check_visual_gate = load_module("check_visual_gate_stitch_traceability_fail", CHECK_VISUAL_GATE_PATH)
    deliverable = tmp_path / "deliverable"
    deliverable.mkdir()
    screenshot_name = "qc-memory-browser-runtime.png"
    (deliverable / screenshot_name).write_bytes(b"png")
    write_ticket(tmp_path / "T-673.md", route_family_required=True, existing_surface_redesign=True)
    write_brief(tmp_path / "brief.md", route_family_required=True)
    write_qc_report(tmp_path / "qc.md", screenshot_name=screenshot_name)
    write_visual_review(
        tmp_path / "visual-review.md",
        screenshot_name=screenshot_name,
        stitch_runtime_parity="fail",
        stitch_surface_traceability="fail",
        token_only_basis="yes",
    )

    report = check_visual_gate.build_report(build_args(tmp_path))
    checks = {check["name"]: check for check in report["checks"]}

    assert report["verdict"] == "FAIL"
    assert checks["visual_review_clears_stitch_runtime_parity"]["ok"] is False
    assert checks["visual_review_clears_stitch_surface_traceability"]["ok"] is False
    assert checks["visual_review_rejects_token_only_stitch_basis"]["ok"] is False


def test_visual_gate_fails_public_surface_without_visual_quality_bar_clearance(tmp_path):
    check_visual_gate = load_module("check_visual_gate_public_surface_fail", CHECK_VISUAL_GATE_PATH)
    deliverable = tmp_path / "deliverable"
    deliverable.mkdir()
    screenshot_name = "qc-landing-runtime.png"
    (deliverable / screenshot_name).write_bytes(b"png")
    write_ticket(tmp_path / "T-673.md", public_surface=True, existing_surface_redesign=True)
    write_brief(tmp_path / "brief.md", public_surface=True)
    write_qc_report(tmp_path / "qc.md", screenshot_name=screenshot_name)
    write_visual_review(
        tmp_path / "visual-review.md",
        screenshot_name=screenshot_name,
        visual_quality_bar="fail",
        composition_anchor_parity="fail",
    )

    report = check_visual_gate.build_report(build_args(tmp_path))
    checks = {check["name"]: check for check in report["checks"]}

    assert report["verdict"] == "FAIL"
    assert checks["visual_review_clears_visual_quality_bar"]["ok"] is False
    assert checks["visual_review_clears_composition_anchor_parity"]["ok"] is False
