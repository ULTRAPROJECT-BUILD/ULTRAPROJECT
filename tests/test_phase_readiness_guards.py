from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CHECK_TICKET_EVIDENCE_PATH = REPO_ROOT / "scripts" / "check_ticket_evidence.py"
CHECK_PHASE_READINESS_PATH = REPO_ROOT / "scripts" / "check_phase_readiness.py"


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
    status: str,
    completed: str = "2026-01-02T12:30",
    title: str | None = None,
    body_lines: list[str] | None = None,
    task_type: str | None = None,
    project: str | None = None,
    phase: int | None = None,
    remediation_for: str | None = None,
    tags: list[str] | None = None,
    blocked_by: list[str] | None = None,
) -> None:
    ticket_title = title or f"{ticket_id} Example"
    lines = [
        "---",
        f"id: {ticket_id}",
        f'title: "{ticket_title}"',
        f"status: {status}",
    ]
    if task_type:
        lines.append(f"task_type: {task_type}")
    if project:
        lines.append(f"project: {project}")
    if phase is not None:
        lines.append(f"phase: {phase}")
    if remediation_for is not None:
        lines.append(f'remediation_for: "{remediation_for}"')
    if tags is not None:
        lines.append(f"tags: [{', '.join(tags)}]")
    if blocked_by is not None:
        lines.append(f"blocked_by: [{', '.join(blocked_by)}]")
    lines.extend(
        [
        "created: 2026-01-02T11:00",
        f"updated: {completed}",
        f"completed: {completed}",
        "---",
        "",
        f"# {ticket_id}",
        "",
        ]
    )
    if body_lines:
        lines.extend(body_lines)
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def write_plan(
    path: Path,
    *,
    phase_number: int = 2,
    tickets: list[str] | None = None,
    exit_criteria: list[str] | None = None,
    runtime_verification: str | None = None,
) -> None:
    ticket_lines = "\n".join(f"  - {ticket_id}: Example" for ticket_id in (tickets or []))
    lines = [
        "---",
        "type: snapshot",
        "subtype: project-plan",
        'project: "demo-project"',
        "---",
        "",
        f"### Phase {phase_number}: Demo Phase",
        "**Exit criteria:**",
    ]
    for criterion in exit_criteria or ["Demo criteria"]:
        lines.append(f"- {criterion}")
    if runtime_verification:
        lines.append(f"**Runtime verification:** {runtime_verification}")
    lines.extend(["**Tickets:**", ticket_lines, ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def write_artifact(path: Path, *, content: str = "{}") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def readiness_args(
    tmp_path: Path,
    *,
    brief: Path | None,
    runtime_doc: Path,
    regression_doc: Path,
    project_file: Path | None = None,
    search_roots: list[Path] | None = None,
) -> argparse.Namespace:
    return argparse.Namespace(
        project_file=str(project_file) if project_file else None,
        project_plan=str(tmp_path / "snapshots" / "project-plan.md"),
        phase=2,
        tickets_dir=str(tmp_path / "tickets"),
        artifacts_root=str(tmp_path / "deliverables" / "artifacts"),
        deliverables_root=str(tmp_path / "deliverables"),
        search_root=[str(path) for path in (search_roots or [tmp_path / "snapshots", tmp_path / "deliverables"])],
        brief=[str(brief)] if brief else [],
        evidence_doc=[str(runtime_doc), str(regression_doc)],
        json_out=str(tmp_path / "out.json"),
        markdown_out=str(tmp_path / "out.md"),
    )


def write_gate_review_and_packet(tmp_path: Path, *, project: str = "demo-project", phase: int = 2) -> str:
    snapshots = tmp_path / "snapshots"
    gate_review = snapshots / f"2026-01-02-phase-{phase}-gate-{project}.md"
    gate_review.write_text(
        "\n".join(
            [
                "---",
                "grade: B",
                "advance_allowed: no",
                "---",
                "",
                "# Gate Review",
                "",
            ]
        ),
        encoding="utf-8",
    )
    gate_packet = snapshots / f"2026-01-02-phase-{phase}-gate-packet-{project}.yaml"
    gate_packet.write_text(f"project: {project}\n", encoding="utf-8")
    return gate_review.name


def write_readiness_keychain_fixture(
    tmp_path: Path,
    *,
    tickets: list[str],
    runtime_captured: str,
    regression_captured: str,
) -> tuple[Path, Path]:
    (tmp_path / "snapshots").mkdir()
    (tmp_path / "tickets").mkdir()
    (tmp_path / "deliverables" / "artifacts" / "t100-keychain-proof").mkdir(parents=True)
    write_plan(
        tmp_path / "snapshots" / "project-plan.md",
        tickets=tickets,
        exit_criteria=["Keychain spike executed with pass/fail documented"],
    )
    write_artifact(tmp_path / "deliverables" / "artifacts" / "t100-keychain-proof" / "proof-pack.json")
    write_ticket(
        tmp_path / "tickets" / "T-100-keychain.md",
        ticket_id="T-100",
        status="closed",
        title="Keychain spike proof",
        completed="2026-01-02T12:30",
        body_lines=[
            "Keychain spike executed with pass/fail documented.",
            "Evidence: `deliverables/artifacts/t100-keychain-proof/proof-pack.json`",
        ],
    )
    runtime_doc = tmp_path / "snapshots" / "runtime.md"
    runtime_doc.write_text(
        f"---\ncaptured: {runtime_captured}\n---\n\nRuntime evidence.\n",
        encoding="utf-8",
    )
    regression_doc = tmp_path / "snapshots" / "regression.md"
    regression_doc.write_text(
        f"---\ncaptured: {regression_captured}\n---\n\nRegression evidence.\n",
        encoding="utf-8",
    )
    return runtime_doc, regression_doc


def test_find_ticket_artifacts_uses_ticket_boundaries(tmp_path):
    check_ticket_evidence = load_module("check_ticket_evidence_under_test", CHECK_TICKET_EVIDENCE_PATH)
    artifacts_root = tmp_path / "artifacts"
    artifacts_root.mkdir()
    (artifacts_root / "input2.py").write_text("noop", encoding="utf-8")
    (artifacts_root / "_dist2.py").write_text("noop", encoding="utf-8")
    (artifacts_root / "T-2-ticket-handoff.md").write_text("keep `status: blocked`", encoding="utf-8")

    matches = check_ticket_evidence.find_ticket_artifacts(artifacts_root, "T-2")

    assert [path.name for path in matches] == ["T-2-ticket-handoff.md"]


def test_phase_readiness_fails_for_stale_evidence_and_missing_screenshots(tmp_path):
    check_phase_readiness = load_module("check_phase_readiness_under_test_fail", CHECK_PHASE_READINESS_PATH)
    (tmp_path / "snapshots").mkdir()
    (tmp_path / "tickets").mkdir()
    (tmp_path / "deliverables" / "artifacts").mkdir(parents=True)

    write_plan(tmp_path / "snapshots" / "project-plan.md", tickets=["T-100"], exit_criteria=["Demo pipeline proof complete"])
    write_artifact(tmp_path / "deliverables" / "artifacts" / "t100-proof" / "proof-pack.json")
    write_ticket(
        tmp_path / "tickets" / "T-100-example.md",
        ticket_id="T-100",
        status="closed",
        completed="2026-01-02T12:30",
        body_lines=["Evidence: `deliverables/artifacts/t100-proof/proof-pack.json`"],
    )

    brief = tmp_path / "snapshots" / "brief.md"
    brief.write_text("Need `qc-screenshot-dashboard-health.png` in the QC evidence.", encoding="utf-8")
    runtime_doc = tmp_path / "snapshots" / "runtime.md"
    runtime_doc.write_text("---\ncaptured: 2026-01-02T12:00\n---\n\nNo screenshot refs.\n", encoding="utf-8")
    regression_doc = tmp_path / "snapshots" / "regression.md"
    regression_doc.write_text("---\ncaptured: 2026-01-02T12:00\n---\n\nStill no screenshot refs.\n", encoding="utf-8")

    report = check_phase_readiness.build_report(
        readiness_args(tmp_path, brief=brief, runtime_doc=runtime_doc, regression_doc=regression_doc)
    )

    checks = {check["name"]: check for check in report["checks"]}
    assert report["verdict"] == "FAIL"
    assert checks["evidence_docs_fresh"]["ok"] is False
    assert checks["required_screenshot_files_present"]["ok"] is False
    assert checks["required_screenshots_cited_in_evidence"]["ok"] is False


def test_phase_readiness_passes_when_evidence_is_fresh_and_cited(tmp_path):
    check_phase_readiness = load_module("check_phase_readiness_under_test_pass", CHECK_PHASE_READINESS_PATH)
    (tmp_path / "snapshots").mkdir()
    (tmp_path / "tickets").mkdir()
    (tmp_path / "deliverables" / "artifacts").mkdir(parents=True)

    write_plan(tmp_path / "snapshots" / "project-plan.md", tickets=["T-100"], exit_criteria=["Demo pipeline proof complete"])
    write_artifact(tmp_path / "deliverables" / "artifacts" / "t100-proof" / "proof-pack.json")
    write_ticket(
        tmp_path / "tickets" / "T-100-example.md",
        ticket_id="T-100",
        status="closed",
        completed="2026-01-02T12:30",
        body_lines=["Evidence: `deliverables/artifacts/t100-proof/proof-pack.json`"],
    )

    brief = tmp_path / "snapshots" / "brief.md"
    brief.write_text("Need `qc-screenshot-dashboard-health.png` in the QC evidence.", encoding="utf-8")
    screenshot = tmp_path / "snapshots" / "qc-screenshot-dashboard-health.png"
    screenshot.write_bytes(b"png")
    runtime_doc = tmp_path / "snapshots" / "runtime.md"
    runtime_doc.write_text(
        "---\ncaptured: 2026-01-02T12:45\n---\n\nReferenced `qc-screenshot-dashboard-health.png`.\n",
        encoding="utf-8",
    )
    regression_doc = tmp_path / "snapshots" / "regression.md"
    regression_doc.write_text(
        "---\ncaptured: 2026-01-02T12:45\n---\n\nAlso referenced `qc-screenshot-dashboard-health.png`.\n",
        encoding="utf-8",
    )

    report = check_phase_readiness.build_report(
        readiness_args(tmp_path, brief=brief, runtime_doc=runtime_doc, regression_doc=regression_doc)
    )

    checks = {check["name"]: check for check in report["checks"]}
    assert report["verdict"] == "PASS"
    assert checks["evidence_docs_fresh"]["ok"] is True
    assert checks["required_screenshot_files_present"]["ok"] is True
    assert checks["required_screenshots_cited_in_evidence"]["ok"] is True


def test_phase_readiness_counts_unrelated_gate_packet_rebuild_ticket(tmp_path):
    check_phase_readiness = load_module("check_phase_readiness_under_test_unrelated_regen", CHECK_PHASE_READINESS_PATH)
    runtime_doc, regression_doc = write_readiness_keychain_fixture(
        tmp_path,
        tickets=["T-100", "T-201"],
        runtime_captured="2026-01-02T13:00",
        regression_captured="2026-01-02T13:00",
    )
    write_gate_review_and_packet(tmp_path)
    write_ticket(
        tmp_path / "tickets" / "T-201-foreign-regeneration.md",
        ticket_id="T-201",
        status="in-progress",
        title="Phase 3 gate packet audit regeneration",
        task_type="gate_remediation",
        project="other-project",
        phase=3,
        remediation_for="2026-01-01-phase-3-gate-other-project.md",
        tags=["phase-3-gate", "gate-remediation", "gate-packet-rebuild"],
        completed="2026-01-02T13:30",
    )

    report = check_phase_readiness.build_report(
        readiness_args(tmp_path, brief=None, runtime_doc=runtime_doc, regression_doc=regression_doc)
    )

    checks = {check["name"]: check for check in report["checks"]}
    assert report["verdict"] == "FAIL"
    assert checks["all_phase_tickets_closed"]["ok"] is False
    assert "T-201" in checks["all_phase_tickets_closed"]["details"]
    assert report["latest_phase_ticket_activity"] == "2026-01-02T13:30:00"
    decision = next(item for item in report["gate_packet_regeneration_decisions"] if item["ticket_id"] == "T-201")
    assert decision["exempted_from_open_tickets"] is False
    assert decision["control_plane_match"] is False
    assert decision["excluded_from_latest_activity"] is False
    assert decision["checks"]["project"] is False
    assert decision["checks"]["phase"] is False
    assert decision["checks"]["remediation_for_matches_expected"] is False


def test_open_ticket_exemption_requires_strict_match(tmp_path):
    check_phase_readiness = load_module("check_phase_readiness_under_test_open_strict_gate", CHECK_PHASE_READINESS_PATH)
    runtime_doc, regression_doc = write_readiness_keychain_fixture(
        tmp_path,
        tickets=["T-100", "T-201"],
        runtime_captured="2026-01-02T13:00",
        regression_captured="2026-01-02T13:00",
    )
    write_gate_review_and_packet(tmp_path)
    write_ticket(
        tmp_path / "tickets" / "T-201-gate-packet-audit-rebuild-shaped.md",
        ticket_id="T-201",
        status="in-progress",
        title="Phase 2 gate packet audit rebuild",
        task_type="gate_remediation",
        project="demo-project",
        phase=2,
        remediation_for="missing-gate-review.md",
        tags=["phase-2-gate", "gate-remediation", "gate-packet-rebuild"],
        blocked_by=["T-999"],
        completed="2026-01-02T13:30",
    )

    report = check_phase_readiness.build_report(
        readiness_args(tmp_path, brief=None, runtime_doc=runtime_doc, regression_doc=regression_doc)
    )

    checks = {check["name"]: check for check in report["checks"]}
    decision = next(item for item in report["gate_packet_regeneration_decisions"] if item["ticket_id"] == "T-201")
    assert report["verdict"] == "FAIL"
    assert checks["all_phase_tickets_closed"]["ok"] is False
    assert "T-201" in checks["all_phase_tickets_closed"]["details"]
    assert checks["evidence_docs_fresh"]["ok"] is False
    assert report["latest_phase_ticket_activity"] == "2026-01-02T13:30:00"
    assert decision["strict_match"] is False
    assert decision["control_plane_match"] is True
    assert decision["exempted_from_open_tickets"] is False
    assert decision["excluded_from_latest_activity"] is False
    assert decision["latest_ticket_activity_policy"] == "included_not_strict_regeneration_ticket"
    assert decision["checks"]["remediation_for_present"] is False
    assert decision["checks"]["remediation_for_matches_expected"] is False
    assert decision["checks"]["dependencies_cleared"] is False


def test_closed_gate_control_ticket_excluded_from_latest_activity(tmp_path):
    check_phase_readiness = load_module("check_phase_readiness_under_test_closed_gate_control", CHECK_PHASE_READINESS_PATH)
    runtime_doc, regression_doc = write_readiness_keychain_fixture(
        tmp_path,
        tickets=["T-100", "T-201"],
        runtime_captured="2026-01-02T13:00",
        regression_captured="2026-01-02T13:00",
    )
    remediation_for = write_gate_review_and_packet(tmp_path)
    (tmp_path / "snapshots" / "2026-01-02-phase-2-gate-packet-demo-project.yaml").unlink()
    write_ticket(
        tmp_path / "tickets" / "T-201-gate-packet-regeneration.md",
        ticket_id="T-201",
        status="closed",
        title="Phase 2 gate packet audit rebuild",
        task_type="gate_remediation",
        project="demo-project",
        phase=2,
        remediation_for=remediation_for,
        tags=["phase-2-gate", "gate-remediation", "gate-packet-rebuild"],
        blocked_by=[],
        completed="2026-01-02T13:30",
    )

    report = check_phase_readiness.build_report(
        readiness_args(tmp_path, brief=None, runtime_doc=runtime_doc, regression_doc=regression_doc)
    )

    checks = {check["name"]: check for check in report["checks"]}
    decision = next(item for item in report["gate_packet_regeneration_decisions"] if item["ticket_id"] == "T-201")
    assert report["verdict"] == "PASS"
    assert report["latest_phase_ticket_activity"] == "2026-01-02T12:30:00"
    assert checks["all_phase_tickets_closed"]["ok"] is True
    assert checks["evidence_docs_fresh"]["ok"] is True
    assert decision["strict_match"] is False
    assert decision["control_plane_match"] is True
    assert decision["exempted_from_open_tickets"] is False
    assert decision["excluded_from_latest_activity"] is True
    assert decision["latest_ticket_activity_policy"] == "excluded_gate_control_activity"
    assert decision["checks"]["owner_gate_packet_artifact_exists"] is False


def test_phase_readiness_excludes_closed_regeneration_ticket_activity(tmp_path):
    check_phase_readiness = load_module("check_phase_readiness_under_test_closed_regen", CHECK_PHASE_READINESS_PATH)
    runtime_doc, regression_doc = write_readiness_keychain_fixture(
        tmp_path,
        tickets=["T-100", "T-201"],
        runtime_captured="2026-01-02T13:00",
        regression_captured="2026-01-02T13:00",
    )
    remediation_for = write_gate_review_and_packet(tmp_path)
    write_ticket(
        tmp_path / "tickets" / "T-201-gate-packet-regeneration.md",
        ticket_id="T-201",
        status="closed",
        title="Phase 2 gate packet audit regeneration",
        task_type="gate_remediation",
        project="demo-project",
        phase=2,
        remediation_for=remediation_for,
        tags=["phase-2-gate", "gate-remediation", "gate-packet-rebuild"],
        blocked_by=[],
        completed="2026-01-02T13:30",
    )

    report = check_phase_readiness.build_report(
        readiness_args(tmp_path, brief=None, runtime_doc=runtime_doc, regression_doc=regression_doc)
    )

    checks = {check["name"]: check for check in report["checks"]}
    assert report["verdict"] == "PASS"
    assert report["latest_phase_ticket_activity"] == "2026-01-02T12:30:00"
    assert checks["all_phase_tickets_closed"]["ok"] is True
    assert checks["evidence_docs_fresh"]["ok"] is True
    decision = next(item for item in report["gate_packet_regeneration_decisions"] if item["ticket_id"] == "T-201")
    assert decision["exempted_from_open_tickets"] is False
    assert decision["control_plane_match"] is True
    assert decision["excluded_from_latest_activity"] is True
    assert decision["latest_ticket_activity_policy"] == "excluded_gate_control_activity"
    assert all(decision["checks"].values())


def test_phase_readiness_excludes_gate_control_ticket_with_stale_remediation_pointer(tmp_path):
    check_phase_readiness = load_module("check_phase_readiness_under_test_stale_regen_pointer", CHECK_PHASE_READINESS_PATH)
    runtime_doc, regression_doc = write_readiness_keychain_fixture(
        tmp_path,
        tickets=["T-100", "T-201"],
        runtime_captured="2026-01-02T13:00",
        regression_captured="2026-01-02T13:00",
    )
    write_gate_review_and_packet(tmp_path)
    write_ticket(
        tmp_path / "tickets" / "T-201-gate-packet-regeneration.md",
        ticket_id="T-201",
        status="closed",
        title="Phase 2 gate packet audit regeneration",
        task_type="gate_remediation",
        project="demo-project",
        phase=2,
        remediation_for="2026-01-01-phase-2-gate-demo-project.md",
        tags=["phase-2-gate", "gate-remediation", "gate-packet-rebuild"],
        blocked_by=[],
        completed="2026-01-02T13:30",
    )

    report = check_phase_readiness.build_report(
        readiness_args(tmp_path, brief=None, runtime_doc=runtime_doc, regression_doc=regression_doc)
    )

    checks = {check["name"]: check for check in report["checks"]}
    decision = next(item for item in report["gate_packet_regeneration_decisions"] if item["ticket_id"] == "T-201")
    assert report["verdict"] == "PASS"
    assert report["latest_phase_ticket_activity"] == "2026-01-02T12:30:00"
    assert checks["all_phase_tickets_closed"]["ok"] is True
    assert checks["evidence_docs_fresh"]["ok"] is True
    assert decision["strict_match"] is False
    assert decision["control_plane_match"] is True
    assert decision["excluded_from_latest_activity"] is True
    assert decision["checks"]["remediation_for_matches_expected"] is False
    assert decision["latest_ticket_activity_policy"] == "excluded_gate_control_activity"


def test_phase_readiness_counts_closed_product_ticket_activity(tmp_path):
    check_phase_readiness = load_module("check_phase_readiness_under_test_closed_product", CHECK_PHASE_READINESS_PATH)
    runtime_doc, regression_doc = write_readiness_keychain_fixture(
        tmp_path,
        tickets=["T-100", "T-202"],
        runtime_captured="2026-01-02T13:00",
        regression_captured="2026-01-02T13:00",
    )
    write_ticket(
        tmp_path / "tickets" / "T-202-product-fix.md",
        ticket_id="T-202",
        status="closed",
        title="Runtime proof product fix",
        task_type="code_fix",
        completed="2026-01-02T13:30",
        body_lines=["Product fix landed after the evidence docs were captured."],
    )

    report = check_phase_readiness.build_report(
        readiness_args(tmp_path, brief=None, runtime_doc=runtime_doc, regression_doc=regression_doc)
    )

    checks = {check["name"]: check for check in report["checks"]}
    assert report["verdict"] == "FAIL"
    assert report["latest_phase_ticket_activity"] == "2026-01-02T13:30:00"
    assert checks["all_phase_tickets_closed"]["ok"] is True
    assert checks["evidence_docs_fresh"]["ok"] is False


def test_phase_readiness_exempts_current_in_progress_regeneration_ticket_only(tmp_path):
    check_phase_readiness = load_module("check_phase_readiness_under_test_allowed_regen", CHECK_PHASE_READINESS_PATH)
    runtime_doc, regression_doc = write_readiness_keychain_fixture(
        tmp_path,
        tickets=["T-100", "T-201"],
        runtime_captured="2026-01-02T13:00",
        regression_captured="2026-01-02T13:00",
    )
    remediation_for = write_gate_review_and_packet(tmp_path)
    write_ticket(
        tmp_path / "tickets" / "T-201-gate-packet-regeneration.md",
        ticket_id="T-201",
        status="in-progress",
        title="Phase 2 gate packet audit regeneration",
        task_type="gate_remediation",
        project="demo-project",
        phase=2,
        remediation_for=remediation_for,
        tags=["phase-2-gate", "gate-remediation", "gate-packet-rebuild"],
        blocked_by=[],
        completed="2026-01-02T13:30",
    )

    report = check_phase_readiness.build_report(
        readiness_args(tmp_path, brief=None, runtime_doc=runtime_doc, regression_doc=regression_doc)
    )

    checks = {check["name"]: check for check in report["checks"]}
    assert report["verdict"] == "PASS"
    assert checks["all_phase_tickets_closed"]["ok"] is True
    assert checks["evidence_docs_fresh"]["ok"] is True
    assert report["latest_phase_ticket_activity"] == "2026-01-02T12:30:00"
    decision = next(item for item in report["gate_packet_regeneration_decisions"] if item["ticket_id"] == "T-201")
    assert decision["exempted_from_open_tickets"] is True
    assert decision["control_plane_match"] is True
    assert decision["excluded_from_latest_activity"] is True
    assert decision["latest_ticket_activity_policy"] == "excluded_gate_control_activity"
    assert all(decision["checks"].values())


def test_phase_readiness_matches_quality_check_tickets_for_visual_proof(tmp_path):
    check_phase_readiness = load_module("check_phase_readiness_under_test_quality_lane", CHECK_PHASE_READINESS_PATH)
    (tmp_path / "snapshots").mkdir()
    (tmp_path / "tickets").mkdir()
    (tmp_path / "deliverables" / "artifacts").mkdir(parents=True)
    (tmp_path / "deliverables" / "qc").mkdir(parents=True)

    write_plan(
        tmp_path / "snapshots" / "project-plan.md",
        tickets=["T-100"],
        exit_criteria=["Approvals screenshot evidence complete", "Walkthrough proof complete"],
    )
    write_artifact(tmp_path / "deliverables" / "artifacts" / "t100-proof" / "proof-pack.json")
    (tmp_path / "deliverables" / "qc" / "qc-screenshot-approvals.png").write_bytes(b"png")
    (tmp_path / "deliverables" / "qc" / "qc-walkthrough.webm").write_bytes(b"webm")
    write_ticket(
        tmp_path / "tickets" / "T-100-qc-approvals-proof.md",
        ticket_id="T-100",
        title="QC approvals proof",
        task_type="quality_check",
        status="closed",
        completed="2026-01-02T12:30",
        body_lines=[
            "Screenshot: `deliverables/qc/qc-screenshot-approvals.png`",
            "Walkthrough: `deliverables/qc/qc-walkthrough.webm`",
        ],
    )

    runtime_doc = tmp_path / "snapshots" / "runtime.md"
    runtime_doc.write_text(
        "---\ncaptured: 2026-01-02T12:45\n---\n\nReferenced `deliverables/qc/qc-screenshot-approvals.png` and `deliverables/qc/qc-walkthrough.webm`.\n",
        encoding="utf-8",
    )
    regression_doc = tmp_path / "snapshots" / "regression.md"
    regression_doc.write_text(
        "---\ncaptured: 2026-01-02T12:45\n---\n\nRegression verification complete.\n",
        encoding="utf-8",
    )

    report = check_phase_readiness.build_report(
        readiness_args(tmp_path, brief=None, runtime_doc=runtime_doc, regression_doc=regression_doc)
    )

    exit_criteria = {entry["index"]: entry for entry in report["exit_criteria"]}
    assert report["verdict"] == "PASS"
    assert exit_criteria[1]["matched_tickets"] == ["T-100"]
    assert exit_criteria[2]["matched_tickets"] == ["T-100"]


def test_phase_readiness_auto_resolves_project_and_phase_briefs(tmp_path):
    check_phase_readiness = load_module("check_phase_readiness_under_test_resolve", CHECK_PHASE_READINESS_PATH)
    (tmp_path / "snapshots").mkdir()
    (tmp_path / "tickets").mkdir()
    (tmp_path / "deliverables" / "artifacts").mkdir(parents=True)

    project_file = tmp_path / "projects" / "demo-project.md"
    project_file.parent.mkdir()
    project_file.write_text(
        "\n".join(
            [
                "---",
                'project: "demo-project"',
                "---",
                "",
                "# Demo Project",
                "",
            ]
        ),
        encoding="utf-8",
    )
    write_plan(tmp_path / "snapshots" / "project-plan.md", tickets=["T-100"], exit_criteria=["Demo pipeline proof complete"])
    write_artifact(tmp_path / "deliverables" / "artifacts" / "t100-proof" / "proof-pack.json")
    write_ticket(
        tmp_path / "tickets" / "T-100-example.md",
        ticket_id="T-100",
        status="closed",
        completed="2026-01-02T12:30",
        body_lines=["Evidence: `deliverables/artifacts/t100-proof/proof-pack.json`"],
    )

    (tmp_path / "snapshots" / "2026-01-01-creative-brief-demo-project.md").write_text(
        "\n".join(
            [
                "---",
                "type: snapshot",
                "subtype: creative-brief",
                'title: "Creative Brief — Demo Project"',
                'project: "demo-project"',
                "captured: 2026-01-01T10:00",
                "---",
                "",
                "# Demo Project Brief",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (tmp_path / "snapshots" / "2026-01-02-creative-brief-phase2-demo-project.md").write_text(
        "\n".join(
            [
                "---",
                "type: snapshot",
                "subtype: creative-brief",
                'title: "Creative Brief — Phase 2"',
                'project: "demo-project"',
                "brief_scope: phase",
                "phase_number: 2",
                "captured: 2026-01-02T11:00",
                "---",
                "",
                "Need `qc-screenshot-phase-2-proof.png` in the QC evidence.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    screenshot = tmp_path / "snapshots" / "qc-screenshot-phase-2-proof.png"
    screenshot.write_bytes(b"png")
    runtime_doc = tmp_path / "snapshots" / "runtime.md"
    runtime_doc.write_text(
        "---\ncaptured: 2026-01-02T12:45\n---\n\nReferenced `qc-screenshot-phase-2-proof.png`.\n",
        encoding="utf-8",
    )
    regression_doc = tmp_path / "snapshots" / "regression.md"
    regression_doc.write_text(
        "---\ncaptured: 2026-01-02T12:45\n---\n\nAlso referenced `qc-screenshot-phase-2-proof.png`.\n",
        encoding="utf-8",
    )
    (tmp_path / "deliverables" / "real-world-validation" / "repos" / "llvm-project" / "libcxx" / "test" / "std" / "time" / "time.cal" / "time.cal.md").mkdir(parents=True)

    report = check_phase_readiness.build_report(
        readiness_args(
            tmp_path,
            brief=None,
            runtime_doc=runtime_doc,
            regression_doc=regression_doc,
            project_file=project_file,
        )
    )

    checks = {check["name"]: check for check in report["checks"]}
    assert report["verdict"] == "PASS"
    assert len(report["brief_paths"]) == 2
    assert any("creative-brief-demo-project" in path for path in report["brief_paths"])
    assert any("creative-brief-phase2-demo-project" in path for path in report["brief_paths"])
    assert checks["required_screenshot_files_present"]["ok"] is True
    assert checks["required_screenshots_cited_in_evidence"]["ok"] is True


def test_phase_readiness_resolves_deliverable_relative_ticket_paths(tmp_path):
    check_phase_readiness = load_module("check_phase_readiness_under_test_deliverables", CHECK_PHASE_READINESS_PATH)
    (tmp_path / "snapshots").mkdir()
    (tmp_path / "tickets").mkdir()
    (tmp_path / "deliverables" / "src" / "refactor_platform" / "dashboard").mkdir(parents=True)
    (tmp_path / "deliverables" / "tests" / "dashboard").mkdir(parents=True)
    (tmp_path / "deliverables" / "docs").mkdir(parents=True)
    (tmp_path / "deliverables" / "qc-evidence").mkdir(parents=True)

    write_plan(
        tmp_path / "snapshots" / "project-plan.md",
        tickets=["T-100"],
        exit_criteria=["Approval workflow tests proof complete"],
    )
    write_ticket(
        tmp_path / "tickets" / "T-100-example.md",
        ticket_id="T-100",
        status="closed",
        completed="2026-01-02T12:30",
        body_lines=[
            "Artifacts:",
            "- `src/refactor_platform/dashboard/approval_routes.py`",
            "- `tests/dashboard/test_approval_workflow.py`",
            "- `docs/approval-workflow-concept.md`",
            "- `qc-evidence/qc-approval-plan-queue.png`",
        ],
    )
    write_artifact(
        tmp_path / "deliverables" / "src" / "refactor_platform" / "dashboard" / "approval_routes.py",
        content="print('ok')\n",
    )
    write_artifact(
        tmp_path / "deliverables" / "tests" / "dashboard" / "test_approval_workflow.py",
        content="def test_ok():\n    assert True\n",
    )
    write_artifact(tmp_path / "deliverables" / "docs" / "approval-workflow-concept.md", content="# Concept\n")
    write_artifact(tmp_path / "deliverables" / "qc-evidence" / "qc-approval-plan-queue.png", content="png")

    runtime_doc = tmp_path / "snapshots" / "runtime.md"
    runtime_doc.write_text("---\ncaptured: 2026-01-02T12:45\n---\n\nRuntime evidence.\n", encoding="utf-8")
    regression_doc = tmp_path / "snapshots" / "regression.md"
    regression_doc.write_text("---\ncaptured: 2026-01-02T12:45\n---\n\nRegression evidence.\n", encoding="utf-8")

    report = check_phase_readiness.build_report(
        readiness_args(tmp_path, brief=None, runtime_doc=runtime_doc, regression_doc=regression_doc)
    )

    checks = {check["name"]: check for check in report["checks"]}
    assert report["verdict"] == "PASS"
    assert checks["exit_criteria_evidenced"]["ok"] is True
    assert report["exit_criteria"][0]["verdict"] == "PASS"
    assert any(path.endswith("approval_routes.py") for path in report["exit_criteria"][0]["evidence_paths"])
    assert any(path.endswith("qc-approval-plan-queue.png") for path in report["exit_criteria"][0]["evidence_paths"])


def test_phase_readiness_resolves_ticket_paths_from_packet_search_roots(tmp_path):
    check_phase_readiness = load_module("check_phase_readiness_under_test_search_roots", CHECK_PHASE_READINESS_PATH)
    (tmp_path / "snapshots").mkdir()
    (tmp_path / "tickets").mkdir()
    (tmp_path / "deliverables" / "artifacts").mkdir(parents=True)
    workspace = tmp_path / "workspace"
    (workspace / "review-pack").mkdir(parents=True)
    (workspace / "docs").mkdir(parents=True)

    write_plan(
        tmp_path / "snapshots" / "project-plan.md",
        tickets=["T-400", "T-401"],
        exit_criteria=[
            "Keychain spike executed with pass/fail documented",
            "Auth foundation: login screen, session management, operator identity stored",
        ],
    )
    write_artifact(workspace / "review-pack" / "keychain-spike-report.md", content="# Keychain\n")
    write_artifact(workspace / "docs" / "auth-foundation.md", content="# Auth\n")
    write_ticket(
        tmp_path / "tickets" / "T-400-keychain.md",
        ticket_id="T-400",
        status="closed",
        title="Keychain spike",
        body_lines=[
            "Keychain spike executed with pass/fail documented.",
            "Evidence: `review-pack/keychain-spike-report.md`",
        ],
    )
    write_ticket(
        tmp_path / "tickets" / "T-401-auth.md",
        ticket_id="T-401",
        status="closed",
        title="Auth foundation",
        body_lines=[
            "Auth foundation covers login screen, session management, and operator identity.",
            "Evidence: `docs/auth-foundation.md`",
        ],
    )

    runtime_doc = tmp_path / "snapshots" / "runtime.md"
    runtime_doc.write_text("---\ncaptured: 2026-01-02T12:45\n---\n\nRuntime evidence.\n", encoding="utf-8")
    regression_doc = tmp_path / "snapshots" / "regression.md"
    regression_doc.write_text("---\ncaptured: 2026-01-02T12:45\n---\n\nRegression evidence.\n", encoding="utf-8")

    report = check_phase_readiness.build_report(
        readiness_args(
            tmp_path,
            brief=None,
            runtime_doc=runtime_doc,
            regression_doc=regression_doc,
            search_roots=[tmp_path / "snapshots", workspace / "review-pack", workspace / "docs"],
        )
    )

    checks = {check["name"]: check for check in report["checks"]}
    assert report["verdict"] == "PASS"
    assert checks["exit_criteria_evidenced"]["ok"] is True
    evidence_paths = [path for item in report["exit_criteria"] for path in item["evidence_paths"]]
    assert str(workspace / "review-pack" / "keychain-spike-report.md") in evidence_paths
    assert str(workspace / "docs" / "auth-foundation.md") in evidence_paths


def test_phase_readiness_fails_for_unaccepted_partial_coverage_and_missing_dashboard_screenshot(tmp_path):
    check_phase_readiness = load_module("check_phase_readiness_under_test_partial", CHECK_PHASE_READINESS_PATH)
    (tmp_path / "snapshots").mkdir()
    (tmp_path / "tickets").mkdir()
    (tmp_path / "deliverables" / "artifacts").mkdir(parents=True)

    write_plan(
        tmp_path / "snapshots" / "project-plan.md",
        tickets=["T-200"],
        exit_criteria=[
            "LLVM extended-shard peak RSS under 600 MiB [PARTIAL-COVERAGE: escalate to admin for descope decision]"
        ],
        runtime_verification="Screenshot evidence of dashboard showing proving-ground results.",
    )
    write_artifact(tmp_path / "deliverables" / "artifacts" / "t200-proof" / "proof-pack.json")
    write_ticket(
        tmp_path / "tickets" / "T-200-example.md",
        ticket_id="T-200",
        status="closed",
        title="LLVM memory fix",
        body_lines=[
            "Closed conditionally [PARTIAL-COVERAGE].",
            "Evidence: `deliverables/artifacts/t200-proof/proof-pack.json`",
        ],
    )

    runtime_doc = tmp_path / "snapshots" / "runtime.md"
    runtime_doc.write_text("---\ncaptured: 2026-01-02T12:45\n---\n\nRuntime check complete.\n", encoding="utf-8")
    regression_doc = tmp_path / "snapshots" / "regression.md"
    regression_doc.write_text("---\ncaptured: 2026-01-02T12:45\n---\n\nRegression check complete.\n", encoding="utf-8")

    report = check_phase_readiness.build_report(
        readiness_args(tmp_path, brief=None, runtime_doc=runtime_doc, regression_doc=regression_doc)
    )

    checks = {check["name"]: check for check in report["checks"]}
    assert report["verdict"] == "FAIL"
    assert checks["exit_criteria_evidenced"]["ok"] is False
    assert checks["dashboard_screenshot_files_present"]["ok"] is False
    assert checks["ticket_partial_coverage_flags"]["ok"] is True
    assert any(warning["ticket_id"] == "T-200" for warning in report["warnings"])
    assert report["exit_criteria"][0]["verdict"] == "FAIL"


def test_phase_readiness_uses_benchmark_artifact_for_exit_criterion_failure(tmp_path):
    check_phase_readiness = load_module("check_phase_readiness_under_test_benchmark", CHECK_PHASE_READINESS_PATH)
    (tmp_path / "snapshots").mkdir()
    (tmp_path / "tickets").mkdir()
    (tmp_path / "deliverables" / "artifacts").mkdir(parents=True)

    write_plan(
        tmp_path / "snapshots" / "project-plan.md",
        tickets=["T-300"],
        exit_criteria=["Index throughput >= 50K LOC/sec on reference hardware"],
    )
    benchmark_path = tmp_path / "deliverables" / "artifacts" / "t300-performance-benchmarks" / "benchmark-measurements.json"
    write_artifact(
        benchmark_path,
        content="""
{
  "criteria": [
    {
      "criterion": "Index throughput >= 50K LOC/sec on reference hardware",
      "verdict": "fail",
      "reason": "Measured throughput below target."
    }
  ]
}
""".strip(),
    )
    write_ticket(
        tmp_path / "tickets" / "T-300-example.md",
        ticket_id="T-300",
        status="closed",
        title="Performance benchmarks — throughput, analysis speed, Docker overhead",
        body_lines=[f"Evidence: `{benchmark_path}`"],
    )

    runtime_doc = tmp_path / "snapshots" / "runtime.md"
    runtime_doc.write_text("---\ncaptured: 2026-01-02T12:45\n---\n\nRuntime check complete.\n", encoding="utf-8")
    regression_doc = tmp_path / "snapshots" / "regression.md"
    regression_doc.write_text("---\ncaptured: 2026-01-02T12:45\n---\n\nRegression check complete.\n", encoding="utf-8")

    report = check_phase_readiness.build_report(
        readiness_args(tmp_path, brief=None, runtime_doc=runtime_doc, regression_doc=regression_doc)
    )

    checks = {check["name"]: check for check in report["checks"]}
    assert report["verdict"] == "FAIL"
    assert checks["exit_criteria_evidenced"]["ok"] is False
    assert report["exit_criteria"][0]["verdict"] == "FAIL"
    assert "Measured throughput below target." in report["exit_criteria"][0]["details"]
