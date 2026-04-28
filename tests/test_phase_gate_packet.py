from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BUILD_PHASE_GATE_PACKET_PATH = REPO_ROOT / "scripts" / "build_phase_gate_packet.py"
CHECK_GATE_PACKET_PATH = REPO_ROOT / "scripts" / "check_gate_packet.py"


def load_module(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def write_markdown(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_project(root: Path, *, project: str = "demo-project", client: str = "acme") -> Path:
    project_path = root / "vault" / "clients" / client / "projects" / f"{project}.md"
    write_markdown(
        project_path,
        [
            "---",
            f'project: "{project}"',
            f'title: "{project}"',
            "---",
            "",
            f"# {project}",
            "",
        ],
    )
    return project_path


def write_plan(root: Path, *, project: str = "demo-project", client: str = "acme") -> Path:
    plan_path = root / "vault" / "clients" / client / "snapshots" / f"2026-01-02-project-plan-{project}.md"
    write_markdown(
        plan_path,
        [
            "---",
            "type: snapshot",
            "subtype: project-plan",
            f'project: "{project}"',
            "---",
            "",
            "### Phase 1: Demo Foundation",
            "**Goal:** Prove the shell and approvals flow.",
            "**Exit criteria:**",
            "- Approvals screenshot evidence complete",
            "- Walkthrough proof complete",
            "**Tickets:**",
            "- T-100: QC approvals proof",
            "- T-101: Artifact polish review",
            "",
        ],
    )
    return plan_path


def write_ticket(
    root: Path,
    *,
    ticket_id: str,
    title: str,
    task_type: str,
    body_lines: list[str],
    project: str = "demo-project",
    client: str = "acme",
    completed: str = "2026-01-02T12:30",
) -> Path:
    ticket_path = root / "vault" / "clients" / client / "tickets" / f"{ticket_id.lower()}-{title.lower().replace(' ', '-')}.md"
    write_markdown(
        ticket_path,
        [
            "---",
            f"id: {ticket_id}",
            f'title: "{title}"',
            f"project: {project}",
            "status: closed",
            f"task_type: {task_type}",
            "created: 2026-01-02T11:00",
            f"updated: {completed}",
            f"completed: {completed}",
            "---",
            "",
            f"# {ticket_id}",
            "",
            *body_lines,
            "",
        ],
    )
    return ticket_path


def write_brief(root: Path, *, project: str = "demo-project", client: str = "acme", mention_screenshot: bool = False) -> Path:
    brief_path = root / "vault" / "clients" / client / "snapshots" / f"2026-01-02-creative-brief-{project}.md"
    requirement_line = "Need `qc-screenshot-demo.png` in QC evidence." if mention_screenshot else ""
    write_markdown(
        brief_path,
        [
            "---",
            "type: snapshot",
            "subtype: creative-brief",
            f'project: "{project}"',
            "captured: 2026-01-02T10:00",
            "---",
            "",
            "Build an interactive dashboard web app with a multi-step approvals flow.",
            requirement_line,
            "",
        ],
    )
    return brief_path


def write_snapshot(path: Path, frontmatter: list[str], body_lines: list[str]) -> None:
    write_markdown(path, ["---", *frontmatter, "---", "", *body_lines, ""])


def build_paths(root: Path, *, project: str = "demo-project", client: str = "acme") -> dict[str, Path]:
    base = root / "vault" / "clients" / client
    deliverables = base / "deliverables"
    (deliverables / "artifacts" / "t100-proof").mkdir(parents=True, exist_ok=True)
    (deliverables / "index.html").write_text("<html><body>demo</body></html>", encoding="utf-8")
    (deliverables / "artifacts" / "t100-proof" / "proof-pack.json").write_text("{}", encoding="utf-8")
    return {
        "base": base,
        "deliverables": deliverables,
        "snapshots": base / "snapshots",
        "tickets": base / "tickets",
        "project": base / "projects" / f"{project}.md",
    }


def test_build_phase_gate_packet_captures_contract(tmp_path):
    build_phase_gate_packet = load_module("build_phase_gate_packet_under_test_packet", BUILD_PHASE_GATE_PACKET_PATH)
    paths = build_paths(tmp_path)
    write_project(tmp_path)
    write_plan(tmp_path)
    write_brief(tmp_path)
    write_ticket(
        tmp_path,
        ticket_id="T-100",
        title="QC approvals proof",
        task_type="quality_check",
        body_lines=["Evidence: `deliverables/artifacts/t100-proof/proof-pack.json`"],
    )
    write_ticket(
        tmp_path,
        ticket_id="T-101",
        title="Artifact polish review",
        task_type="artifact_polish_review",
        body_lines=["Review complete."],
    )
    write_snapshot(
        paths["snapshots"] / "2026-01-02-phase-1-runtime-check-demo-project.md",
        ['type: snapshot', 'project: "demo-project"', "phase: 1", "captured: 2026-01-02T12:45"],
        ["Runtime verification complete."],
    )
    write_snapshot(
        paths["snapshots"] / "2026-01-02-phase-1-regression-demo-project.md",
        ['type: snapshot', 'project: "demo-project"', "phase: 1", "captured: 2026-01-02T12:45"],
        ["Regression verification complete."],
    )
    write_snapshot(
        paths["snapshots"] / "2026-01-02-qc-phase1-demo-project.md",
        ['type: snapshot', 'subtype: quality-check', 'project: "demo-project"', "phase: 1", "captured: 2026-01-02T12:46"],
        ["QC evidence references `qc-walkthrough.webm`."],
    )
    write_snapshot(
        paths["snapshots"] / "2026-01-02-artifact-polish-review-demo-project.md",
        ['type: snapshot', 'subtype: artifact-polish-review', 'project: "demo-project"', "captured: 2026-01-02T12:47"],
        ["Artifact polish review complete."],
    )
    (paths["deliverables"] / "qc-walkthrough.webm").write_bytes(b"video")

    report = build_phase_gate_packet.build_report(paths["project"], explicit_plan=None, phase_number=1)

    assert report["phase"] == 1
    assert report["evidence_docs"]["runtime_check"].endswith("phase-1-runtime-check-demo-project.md")
    assert report["evidence_docs"]["quality_check"][0].endswith("qc-phase1-demo-project.md")
    exit_items = [item for item in report["proof_items"] if item["kind"] == "exit_criterion"]
    assert any("T-100" in item["owner_tickets"] for item in exit_items)
    assert any("proof-pack.json" in path for item in exit_items for path in item["expected_paths"])
    walkthrough_item = next(item for item in report["proof_items"] if item["key"] == "walkthrough-artifact")
    assert walkthrough_item["meta"]["requirement"]["level"] == "required"


def test_build_phase_gate_packet_accepts_quality_check_type_snapshot(tmp_path):
    build_phase_gate_packet = load_module("build_phase_gate_packet_under_test_qc_type", BUILD_PHASE_GATE_PACKET_PATH)
    paths = build_paths(tmp_path)
    write_project(tmp_path)
    write_plan(tmp_path)
    write_brief(tmp_path)
    write_ticket(
        tmp_path,
        ticket_id="T-100",
        title="QC approvals proof",
        task_type="quality_check",
        body_lines=["Evidence: `deliverables/artifacts/t100-proof/proof-pack.json`"],
    )
    write_ticket(
        tmp_path,
        ticket_id="T-101",
        title="Artifact polish review",
        task_type="artifact_polish_review",
        body_lines=["Review complete."],
    )
    write_snapshot(
        paths["snapshots"] / "2026-01-02-phase-1-runtime-check-demo-project.md",
        ['type: snapshot', 'project: "demo-project"', "phase: 1", "captured: 2026-01-02T12:45"],
        ["Runtime verification complete."],
    )
    write_snapshot(
        paths["snapshots"] / "2026-01-02-phase-1-regression-demo-project.md",
        ['type: snapshot', 'project: "demo-project"', "phase: 1", "captured: 2026-01-02T12:45"],
        ["Regression verification complete."],
    )
    write_snapshot(
        paths["snapshots"] / "2026-01-02-qc-phase1-demo-project.md",
        ['type: snapshot', 'subtype: quality-check', 'project: "demo-project"', "phase: 1", "captured: 2026-01-02T12:46"],
        ["Old QC evidence references `qc-walkthrough.webm`."],
    )
    write_snapshot(
        paths["snapshots"] / "2026-01-03-qc-phase1-demo-project.md",
        ['type: quality_check', 'project: "demo-project"', "phase: 1", "updated: 2026-01-03T09:00"],
        ["New QC evidence references `qc-walkthrough.webm`."],
    )
    write_snapshot(
        paths["snapshots"] / "2026-01-02-artifact-polish-review-demo-project.md",
        ['type: snapshot', 'subtype: artifact-polish-review', 'project: "demo-project"', "captured: 2026-01-02T12:47"],
        ["Artifact polish review complete."],
    )
    (paths["deliverables"] / "qc-walkthrough.webm").write_bytes(b"video")

    report = build_phase_gate_packet.build_report(paths["project"], explicit_plan=None, phase_number=1)

    assert report["evidence_docs"]["quality_check"][0].endswith("2026-01-03-qc-phase1-demo-project.md")


def test_derive_search_roots_includes_review_pack_and_docs_children(tmp_path, monkeypatch):
    build_phase_gate_packet = load_module("build_phase_gate_packet_under_test_roots", BUILD_PHASE_GATE_PACKET_PATH)
    snapshots = tmp_path / "snapshots"
    absolute_workspace = tmp_path / "absolute-workspace"
    relative_workspace = tmp_path / "relative-workspace"
    for workspace in (absolute_workspace, relative_workspace):
        (workspace / "review-pack").mkdir(parents=True)
        (workspace / "docs").mkdir()
    snapshots.mkdir()

    monkeypatch.chdir(tmp_path)

    roots = build_phase_gate_packet.derive_search_roots(
        snapshots,
        [],
        [
            {"expected_paths": [str(absolute_workspace)]},
            {"expected_paths": [str(Path("relative-workspace"))]},
        ],
        [],
    )

    assert str(absolute_workspace / "review-pack") in roots
    assert str(absolute_workspace / "docs") in roots
    assert str(relative_workspace.resolve() / "review-pack") in roots
    assert str(relative_workspace.resolve() / "docs") in roots


def test_check_gate_packet_fails_on_phantom_refs_and_bad_mp4(tmp_path):
    build_phase_gate_packet = load_module("build_phase_gate_packet_under_test_fail", BUILD_PHASE_GATE_PACKET_PATH)
    check_gate_packet = load_module("check_gate_packet_under_test_fail", CHECK_GATE_PACKET_PATH)
    paths = build_paths(tmp_path)
    write_project(tmp_path)
    write_plan(tmp_path)
    write_brief(tmp_path)
    write_ticket(
        tmp_path,
        ticket_id="T-100",
        title="QC approvals proof",
        task_type="quality_check",
        body_lines=["Evidence: `deliverables/artifacts/t100-proof/proof-pack.json`"],
    )
    write_ticket(
        tmp_path,
        ticket_id="T-101",
        title="Artifact polish review",
        task_type="artifact_polish_review",
        body_lines=["Review complete."],
    )
    write_snapshot(
        paths["snapshots"] / "2026-01-02-phase-1-runtime-check-demo-project.md",
        ['type: snapshot', 'project: "demo-project"', "phase: 1", "captured: 2026-01-02T12:45"],
        ["Runtime verification references `deliverables/qc/missing-shot.png`."],
    )
    write_snapshot(
        paths["snapshots"] / "2026-01-02-phase-1-regression-demo-project.md",
        ['type: snapshot', 'project: "demo-project"', "phase: 1", "captured: 2026-01-02T12:45"],
        ["Regression verification complete."],
    )
    write_snapshot(
        paths["snapshots"] / "2026-01-02-qc-phase1-demo-project.md",
        ['type: snapshot', 'subtype: quality-check', 'project: "demo-project"', "phase: 1", "captured: 2026-01-02T12:46"],
        ["QC references `qc-walkthrough.mp4`."],
    )
    write_snapshot(
        paths["snapshots"] / "2026-01-02-artifact-polish-review-demo-project.md",
        ['type: snapshot', 'subtype: artifact-polish-review', 'project: "demo-project"', "captured: 2026-01-02T12:47"],
        ["Artifact polish review complete."],
    )
    (paths["deliverables"] / "qc-walkthrough.mp4").write_bytes(b"not-a-real-video")

    packet_path = tmp_path / "gate-packet.yaml"
    packet = build_phase_gate_packet.build_report(paths["project"], explicit_plan=None, phase_number=1)
    build_phase_gate_packet.write_packet(packet, packet_path)

    report = check_gate_packet.build_report(packet_path)

    checks = {check["name"]: check for check in report["checks"]}
    assert report["verdict"] == "FAIL"
    assert checks["evidence_docs_have_no_phantom_refs"]["ok"] is False
    assert checks["walkthrough_media_contract"]["ok"] is False


def test_check_gate_packet_passes_for_clean_packet(tmp_path):
    build_phase_gate_packet = load_module("build_phase_gate_packet_under_test_pass", BUILD_PHASE_GATE_PACKET_PATH)
    check_gate_packet = load_module("check_gate_packet_under_test_pass", CHECK_GATE_PACKET_PATH)
    paths = build_paths(tmp_path)
    write_project(tmp_path)
    write_plan(tmp_path)
    write_brief(tmp_path, mention_screenshot=True)
    write_ticket(
        tmp_path,
        ticket_id="T-100",
        title="QC approvals proof",
        task_type="quality_check",
        body_lines=["Evidence: `deliverables/artifacts/t100-proof/proof-pack.json`"],
    )
    write_ticket(
        tmp_path,
        ticket_id="T-101",
        title="Artifact polish review",
        task_type="artifact_polish_review",
        body_lines=["Review complete."],
    )
    (paths["snapshots"] / "qc-screenshot-demo.png").write_bytes(b"png")
    write_snapshot(
        paths["snapshots"] / "2026-01-02-phase-1-runtime-check-demo-project.md",
        ['type: snapshot', 'project: "demo-project"', "phase: 1", "captured: 2026-01-02T12:45"],
        ["Runtime verification references `qc-screenshot-demo.png`."],
    )
    write_snapshot(
        paths["snapshots"] / "2026-01-02-phase-1-regression-demo-project.md",
        ['type: snapshot', 'project: "demo-project"', "phase: 1", "captured: 2026-01-02T12:45"],
        ["Regression verification references `qc-screenshot-demo.png`."],
    )
    write_snapshot(
        paths["snapshots"] / "2026-01-02-qc-phase1-demo-project.md",
        ['type: snapshot', 'subtype: quality-check', 'project: "demo-project"', "phase: 1", "captured: 2026-01-02T12:46"],
        ["QC references `qc-walkthrough.webm` and `qc-screenshot-demo.png`."],
    )
    write_snapshot(
        paths["snapshots"] / "2026-01-02-artifact-polish-review-demo-project.md",
        ['type: snapshot', 'subtype: artifact-polish-review', 'project: "demo-project"', "captured: 2026-01-02T12:47"],
        ["Artifact polish review complete."],
    )
    (paths["deliverables"] / "qc-walkthrough.webm").write_bytes(b"video")

    packet_path = tmp_path / "gate-packet.yaml"
    packet = build_phase_gate_packet.build_report(paths["project"], explicit_plan=None, phase_number=1)
    build_phase_gate_packet.write_packet(packet, packet_path)

    report = check_gate_packet.build_report(packet_path)
    checks = {check["name"]: check for check in report["checks"]}

    assert report["verdict"] == "PASS"
    assert checks["phase_readiness_passes"]["ok"] is True
    assert checks["proof_item_expected_paths_exist"]["ok"] is True


def test_check_gate_packet_allows_short_supplemental_clips_with_meaningful_walkthrough(tmp_path, monkeypatch):
    check_gate_packet = load_module("check_gate_packet_under_test_short_supplemental", CHECK_GATE_PACKET_PATH)
    short_clip = tmp_path / "tiny-proof-clip.webm"
    walkthrough = tmp_path / "qc-walkthrough.webm"
    short_clip.write_bytes(b"video")
    walkthrough.write_bytes(b"video")

    def fake_probe(path: Path) -> dict:
        return {
            "codec": "vp9",
            "format_name": "matroska,webm",
            "duration_seconds": 3.0 if path == short_clip.resolve() else 12.0,
        }

    monkeypatch.setattr(check_gate_packet, "probe_video_contract", fake_probe)

    checks, findings = check_gate_packet.evaluate_walkthrough_contract(
        {
            "review_surface": {
                "walkthrough_requirement": {"level": "required"},
                "walkthrough_artifacts": [
                    {"path": str(short_clip)},
                    {"path": str(walkthrough)},
                ],
            }
        }
    )

    checks_by_name = {check["name"]: check for check in checks}
    assert checks_by_name["walkthrough_present_when_required"]["ok"] is True
    assert checks_by_name["walkthrough_media_contract"]["ok"] is True
    assert findings == []


def test_check_gate_packet_fails_when_required_walkthroughs_are_only_short(tmp_path, monkeypatch):
    check_gate_packet = load_module("check_gate_packet_under_test_only_short", CHECK_GATE_PACKET_PATH)
    short_clip = tmp_path / "tiny-walkthrough.webm"
    short_clip.write_bytes(b"video")

    monkeypatch.setattr(
        check_gate_packet,
        "probe_video_contract",
        lambda path: {"codec": "vp9", "format_name": "matroska,webm", "duration_seconds": 3.0},
    )

    checks, findings = check_gate_packet.evaluate_walkthrough_contract(
        {
            "review_surface": {
                "walkthrough_requirement": {"level": "required"},
                "walkthrough_artifacts": [{"path": str(short_clip)}],
            }
        }
    )

    checks_by_name = {check["name"]: check for check in checks}
    assert checks_by_name["walkthrough_media_contract"]["ok"] is False
    assert findings[0]["category"] == "media-contract"


def test_check_gate_packet_ignores_multiline_backtick_noise(tmp_path):
    build_phase_gate_packet = load_module("build_phase_gate_packet_under_test_multiline", BUILD_PHASE_GATE_PACKET_PATH)
    check_gate_packet = load_module("check_gate_packet_under_test_multiline", CHECK_GATE_PACKET_PATH)
    paths = build_paths(tmp_path)
    write_project(tmp_path)
    write_plan(tmp_path)
    write_brief(tmp_path)
    write_ticket(
        tmp_path,
        ticket_id="T-100",
        title="QC approvals proof",
        task_type="quality_check",
        body_lines=["Evidence: `deliverables/artifacts/t100-proof/proof-pack.json`"],
    )
    write_ticket(
        tmp_path,
        ticket_id="T-101",
        title="Artifact polish review",
        task_type="artifact_polish_review",
        body_lines=["Review complete."],
    )
    write_snapshot(
        paths["snapshots"] / "2026-01-02-phase-1-runtime-check-demo-project.md",
        ['type: snapshot', 'project: "demo-project"', "phase: 1", "captured: 2026-01-02T12:45"],
        ["Runtime verification references `deliverables/artifacts/t100-proof/proof-pack.json`."],
    )
    write_snapshot(
        paths["snapshots"] / "2026-01-02-phase-1-regression-demo-project.md",
        ['type: snapshot', 'project: "demo-project"', "phase: 1", "captured: 2026-01-02T12:45"],
        ["Regression verification complete."],
    )
    write_snapshot(
        paths["snapshots"] / "2026-01-02-qc-phase1-demo-project.md",
        ['type: snapshot', 'subtype: quality-check', 'project: "demo-project"', "phase: 1", "captured: 2026-01-02T12:46"],
        [
            "QC references `qc-walkthrough.webm`.",
            "Noise block: `README.md",
            "LIMITATIONS.md`",
        ],
    )
    (paths["snapshots"] / "README.md").write_text("note", encoding="utf-8")
    (paths["snapshots"] / "LIMITATIONS.md").write_text("note", encoding="utf-8")
    write_snapshot(
        paths["snapshots"] / "2026-01-02-artifact-polish-review-demo-project.md",
        ['type: snapshot', 'subtype: artifact-polish-review', 'project: "demo-project"', "captured: 2026-01-02T12:47"],
        ["Artifact polish review complete."],
    )
    (paths["deliverables"] / "qc-walkthrough.webm").write_bytes(b"video")

    packet_path = tmp_path / "gate-packet.yaml"
    packet = build_phase_gate_packet.build_report(paths["project"], explicit_plan=None, phase_number=1)
    build_phase_gate_packet.write_packet(packet, packet_path)

    report = check_gate_packet.build_report(packet_path)

    assert report["verdict"] == "PASS"
    assert report["phantom_references"] == []


def test_check_gate_packet_ignores_codey_refs_and_resolves_nested_artifacts(tmp_path):
    build_phase_gate_packet = load_module("build_phase_gate_packet_under_test_contextual", BUILD_PHASE_GATE_PACKET_PATH)
    check_gate_packet = load_module("check_gate_packet_under_test_contextual", CHECK_GATE_PACKET_PATH)
    paths = build_paths(tmp_path)
    write_project(tmp_path)
    write_plan(tmp_path)
    write_brief(tmp_path)
    nested_dir = paths["deliverables"] / ".stitch" / "designs" / "qc-screenshots"
    nested_dir.mkdir(parents=True, exist_ok=True)
    (nested_dir / "qc-v2-approvals-light.png").write_bytes(b"png")
    (paths["deliverables"] / ".stitch" / "DESIGN.md").write_text("design", encoding="utf-8")
    write_ticket(
        tmp_path,
        ticket_id="T-100",
        title="QC approvals proof",
        task_type="quality_check",
        body_lines=[
            "Evidence: `deliverables/.stitch/designs/qc-screenshots/qc-v2-approvals-light.png`",
            "Design file: `deliverables/.stitch/DESIGN.md`",
        ],
    )
    write_ticket(
        tmp_path,
        ticket_id="T-101",
        title="Artifact polish review",
        task_type="artifact_polish_review",
        body_lines=["Review complete."],
    )
    write_snapshot(
        paths["snapshots"] / "2026-01-02-phase-1-runtime-check-demo-project.md",
        ['type: snapshot', 'project: "demo-project"', "phase: 1", "captured: 2026-01-02T12:45"],
        [
            "Screenshot inventory includes `qc-v2-approvals-light.png`.",
            "Error handling mentions `_meta.errors` without treating it as a file.",
            "Source line checked in `src/routes/approvals-page.tsx`.",
        ],
    )
    write_snapshot(
        paths["snapshots"] / "2026-01-02-phase-1-regression-demo-project.md",
        ['type: snapshot', 'project: "demo-project"', "phase: 1", "captured: 2026-01-02T12:45"],
        ["Regression verification complete."],
    )
    write_snapshot(
        paths["snapshots"] / "2026-01-02-qc-phase1-demo-project.md",
        ['type: snapshot', 'subtype: quality-check', 'project: "demo-project"', "phase: 1", "captured: 2026-01-02T12:46"],
        [
            "| File | Content |",
            "|------|---------|",
            "| `qc-v2-approvals-light.png` | Approvals queue, light theme |",
            "Design file: `DESIGN.md`",
            "Property path note: `item.frontmatter.summary`",
        ],
    )
    write_snapshot(
        paths["snapshots"] / "2026-01-02-artifact-polish-review-demo-project.md",
        ['type: snapshot', 'subtype: artifact-polish-review', 'project: "demo-project"', "captured: 2026-01-02T12:47"],
        ["Artifact polish review complete."],
    )
    (paths["deliverables"] / "qc-walkthrough.webm").write_bytes(b"video")

    packet_path = tmp_path / "gate-packet.yaml"
    packet = build_phase_gate_packet.build_report(paths["project"], explicit_plan=None, phase_number=1)
    build_phase_gate_packet.write_packet(packet, packet_path)

    report = check_gate_packet.build_report(packet_path)

    assert report["verdict"] == "PASS"
    assert report["phantom_references"] == []
