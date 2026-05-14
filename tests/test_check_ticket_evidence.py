from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CHECK_TICKET_EVIDENCE_PATH = REPO_ROOT / "scripts" / "check_ticket_evidence.py"


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
    body_lines: list[str],
    title: str | None = None,
) -> None:
    ticket_title = title or f"{ticket_id} Example"
    lines = [
        "---",
        f"id: {ticket_id}",
        f'title: "{ticket_title}"',
        f"status: {status}",
        "created: 2026-01-02T11:00",
        "updated: 2026-01-02T12:00",
        "---",
        "",
        f"# {ticket_id}",
        "",
        *body_lines,
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def test_ticket_evidence_passes_with_real_proof_refs(tmp_path):
    module = load_module("check_ticket_evidence_test_pass", CHECK_TICKET_EVIDENCE_PATH)
    ticket_path = tmp_path / "vault" / "clients" / "demo" / "tickets" / "T-200.md"
    artifacts_root = tmp_path / "deliverable" / "artifacts"
    screenshot_dir = tmp_path / "deliverable" / ".stitch" / "designs" / "qc-screenshots"
    screenshot_dir.mkdir(parents=True)
    (screenshot_dir / "qc-screenshot-dashboard-light.png").write_bytes(b"png")
    results_doc = tmp_path / "vault" / "clients" / "demo" / "snapshots" / "2026-01-02-results.md"
    results_doc.parent.mkdir(parents=True)
    results_doc.write_text("# results", encoding="utf-8")

    write_ticket(
        ticket_path,
        ticket_id="T-200",
        status="closed",
        body_lines=[
            "Saved screenshots to `.stitch/designs/qc-screenshots/`.",
            "Results written to `snapshots/2026-01-02-results.md`.",
        ],
    )

    report = module.build_report(ticket_path, artifacts_root)

    checks = {check["name"]: check for check in report["checks"]}
    assert report["verdict"] == "PASS"
    assert checks["proof_claims_grounded"]["ok"] is True
    assert checks["referenced_proof_paths_resolve"]["ok"] is True
    assert checks["referenced_proof_directories_populated"]["ok"] is True


def test_ticket_evidence_fails_when_cited_proof_path_is_missing(tmp_path):
    module = load_module("check_ticket_evidence_test_missing", CHECK_TICKET_EVIDENCE_PATH)
    ticket_path = tmp_path / "vault" / "clients" / "demo" / "tickets" / "T-201.md"
    artifacts_root = tmp_path / "deliverable" / "artifacts"
    artifacts_root.mkdir(parents=True)

    write_ticket(
        ticket_path,
        ticket_id="T-201",
        status="closed",
        body_lines=[
            "Captured walkthrough video and saved it to `.stitch/designs/qc-screenshots/qc-walkthrough-phase1.mp4`.",
        ],
    )

    report = module.build_report(ticket_path, artifacts_root)

    checks = {check["name"]: check for check in report["checks"]}
    assert report["verdict"] == "FAIL"
    assert checks["referenced_proof_paths_resolve"]["ok"] is False
    assert report["missing_proof_references"][0]["candidate"].endswith("qc-walkthrough-phase1.mp4")


def test_ticket_evidence_fails_when_closed_ticket_claims_proof_without_path(tmp_path):
    module = load_module("check_ticket_evidence_test_ungrounded", CHECK_TICKET_EVIDENCE_PATH)
    ticket_path = tmp_path / "vault" / "clients" / "demo" / "tickets" / "T-202.md"
    artifacts_root = tmp_path / "deliverable" / "artifacts"
    artifacts_root.mkdir(parents=True)

    write_ticket(
        ticket_path,
        ticket_id="T-202",
        status="closed",
        body_lines=[
            "Captured 8 runtime screenshots for the final verification pass.",
            "Recorded a walkthrough video and confirmed the evidence files are on disk.",
        ],
    )

    report = module.build_report(ticket_path, artifacts_root)

    checks = {check["name"]: check for check in report["checks"]}
    assert report["verdict"] == "FAIL"
    assert checks["proof_claims_grounded"]["ok"] is False
    assert report["proof_references"] == []


def test_ticket_evidence_skips_proof_enforcement_for_open_ticket(tmp_path):
    module = load_module("check_ticket_evidence_test_open", CHECK_TICKET_EVIDENCE_PATH)
    ticket_path = tmp_path / "vault" / "clients" / "demo" / "tickets" / "T-203.md"
    artifacts_root = tmp_path / "deliverable" / "artifacts"
    artifacts_root.mkdir(parents=True)

    write_ticket(
        ticket_path,
        ticket_id="T-203",
        status="in-progress",
        body_lines=[
            "Need to capture screenshots and walkthrough video before closeout.",
        ],
    )

    report = module.build_report(ticket_path, artifacts_root)

    checks = {check["name"]: check for check in report["checks"]}
    assert report["verdict"] == "PASS"
    assert checks["proof_claims_grounded"]["ok"] is True
    assert checks["referenced_proof_paths_resolve"]["ok"] is True


def test_ticket_evidence_does_not_treat_generic_bare_docs_as_proof_refs(tmp_path):
    module = load_module("check_ticket_evidence_test_generic_docs", CHECK_TICKET_EVIDENCE_PATH)
    ticket_path = tmp_path / "vault" / "clients" / "demo" / "tickets" / "T-204.md"
    artifacts_root = tmp_path / "deliverable" / "artifacts"
    artifacts_root.mkdir(parents=True)

    write_ticket(
        ticket_path,
        ticket_id="T-204",
        status="closed",
        body_lines=[
            "Implemented the theme tokens in index.css matching DESIGN.md exactly.",
        ],
    )

    report = module.build_report(ticket_path, artifacts_root)

    checks = {check["name"]: check for check in report["checks"]}
    assert report["verdict"] == "PASS"
    assert checks["referenced_proof_paths_resolve"]["ok"] is True
    assert report["proof_references"] == []
