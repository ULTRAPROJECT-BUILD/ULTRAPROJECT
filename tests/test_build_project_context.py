from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "build_project_context.py"


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


def write_ticket(
    path: Path,
    *,
    ticket_id: str,
    title: str,
    project: str,
    status: str,
    updated: str,
    completed: str = "",
    blocked_by: str = "[]",
) -> None:
    write_markdown(
        path,
        [
            "---",
            "type: ticket",
            f"id: {ticket_id}",
            f'title: "{title}"',
            f"status: {status}",
            f'project: "{project}"',
            "created: 2026-01-01T09:00",
            f"updated: {updated}",
            f"completed: {completed}",
            f"blocked_by: {blocked_by}",
            "---",
            "",
            f"# {title}",
            "",
        ],
    )


def write_brief(path: Path, *, project: str, title: str, captured: str, phase: int | None = None) -> None:
    lines = [
        "---",
        "type: snapshot",
        "subtype: creative-brief",
        f'title: "{title}"',
        f'project: "{project}"',
    ]
    if phase is not None:
        lines.extend(["brief_scope: phase", f"phase_number: {phase}"])
    lines.extend(
        [
            f"captured: {captured}",
            f"updated: {captured}",
            "---",
            "",
            f"# {title}",
            "",
        ]
    )
    write_markdown(path, lines)


def test_build_project_context_generates_stable_context_and_index(tmp_path):
    root = tmp_path / "platform"
    project_file = root / "vault" / "clients" / "acme" / "projects" / "sample-project.md"
    snapshots_dir = root / "vault" / "clients" / "acme" / "snapshots"
    tickets_dir = root / "vault" / "clients" / "acme" / "tickets"
    decisions_dir = root / "vault" / "clients" / "acme" / "decisions"
    lessons_dir = root / "vault" / "clients" / "acme" / "lessons"
    framework_repo = tmp_path / "employee-agent"
    framework_repo.mkdir(parents=True, exist_ok=True)
    (framework_repo / "package.json").write_text('{"name":"employee-agent"}\n', encoding="utf-8")
    subprocess.run(["git", "init"], cwd=framework_repo, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=framework_repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=framework_repo, check=True)
    subprocess.run(["git", "add", "package.json"], cwd=framework_repo, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=framework_repo, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    app_workspace = tmp_path / "sample-app"

    write_markdown(
        project_file,
        [
            "---",
            'type: project',
            'title: "Sample Project"',
            'status: active',
            f'goal: "Deliver the project context layer safely at {app_workspace} and verify against framework {framework_repo}."',
            "---",
            "",
            "# Sample Project",
            "",
            "Current wave: Wave 2B — Delivery Hardening",
            "",
            "## Orchestrator Log",
            "",
            "- 2026-01-04T08:15: ORCH-CHECKPOINT: Delivery review held at B. Remediation tickets spawned.",
        ],
    )

    write_markdown(
        snapshots_dir / "2026-01-04-project-plan-sample-project.md",
        [
            "---",
            "type: snapshot",
            "subtype: project-plan",
            'project: "sample-project"',
            "current_phase: 2",
            "total_phases: 4",
            "captured: 2026-01-04T08:00",
            "---",
            "",
            "# Project Plan — Sample Project",
            "",
            "## Goal Contract",
            "",
            "- **Rigor tier:** frontier",
            "- **Mission:** Deliver the project context layer safely.",
            "- **Primary evaluator:** skeptical operator",
            "- **Mission success:** Current context and artifact pointers are always trustworthy.",
            "- **Primary success metrics:** authoritative paths stay current and blockers are visible without vault spelunking.",
            "- **Primary risks:** stale context artifacts and wrongly selected review surfaces.",
            "- **Human-owned decisions:** accept scope descopes or strategic tradeoffs if proofs stay partial.",
            "- **Agent-owned execution:** maintain the context layer, update authoritative pointers, and surface active assumptions.",
            "- **Proof shape:** plan contract + current-context sync + review/gate snapshots.",
            "- **In scope:** project context generation",
            "- **Out of scope:** hosted UI",
            "- **Partial-coverage rule:** partial coverage must be explicit and justified.",
            "",
            "### Goal Workstreams",
            "",
            "| Goal / Workstream | Type | Priority | Success Signal | Evaluator | Scale / Scope |",
            "|-------------------|------|----------|----------------|-----------|---------------|",
            "| WS-1 context trust | quality | critical | Current context points to the right review surface | skeptical operator | platform-wide |",
            "| WS-2 artifact navigation | workflow | high | Artifact index resolves authoritative files | skeptical operator | platform-wide |",
            "",
            "## Assumption Register",
            "",
            "| ID | Assumption | Category | Risk | Validation Method | Owner | Target Phase/Gate | Status | Evidence / Resolution |",
            "|----|------------|----------|------|-------------------|-------|-------------------|--------|-----------------------|",
            "| A-001 | Review artifacts have stable naming | proof | high | Add stricter project matching in context builder | orchestrator | plan QA | validating | Pending patch |",
            "| A-002 | Queued projects can still have useful context shells | workflow | medium | Generate context without plan/tickets | orchestrator | project creation | resolved | Test fixture covers it |",
            "| A-003 | Legacy cleanup can wait until after launch | operational | low | Revisit in maintenance phase | orchestrator | Phase 4 | deferred | Intentionally postponed |",
            "",
            "## Phases",
            "",
            "### Phase 1: Foundation (complete)",
            "**Goal:** Build the baseline.",
            "**Exit criteria:**",
            "- Baseline exists",
            "",
            "### Phase 2: Delivery Hardening (active)",
            "**Goal:** Produce delivery-grade context and proof surfaces.",
            "**Exit criteria:**",
            "- Review surfaces are coherent",
            "- Context pack is stable",
            "",
            "## Artifact Manifest",
            "",
            "| Artifact | Path | Produced by | Date |",
            "|----------|------|-------------|------|",
            "| Review Pack | vault/clients/acme/snapshots/2026-01-04-review-pack-v2-sample-project.md | T-101 | 2026-01-04 |",
            "| Delivery Review | vault/clients/acme/snapshots/2026-01-04-delivery-review-sample-project.md | T-102 | 2026-01-04 |",
            "",
        ],
    )

    write_brief(
        snapshots_dir / "2026-01-03-creative-brief-sample-project.md",
        project="sample-project",
        title="Creative Brief — Sample Project",
        captured="2026-01-03T09:00",
    )
    write_brief(
        snapshots_dir / "2026-01-04-creative-brief-phase2-sample-project.md",
        project="sample-project",
        title="Creative Brief — Phase 2 Sample Project",
        captured="2026-01-04T08:30",
        phase=2,
    )

    write_markdown(
        snapshots_dir / "2026-01-03-phase-2-gate-sample-project.md",
        [
            "---",
            "type: snapshot",
            'title: "Phase 2 Gate — Sample Project"',
            'project: "sample-project"',
            "captured: 2026-01-03T20:00",
            "overall_grade: A",
            "---",
            "",
            "# Phase 2 Gate",
        ],
    )
    write_markdown(
        snapshots_dir / "2026-01-04-review-pack-v2-sample-project.md",
        [
            "---",
            "type: snapshot",
            'title: "Review Pack — Sample Project"',
            'project: "sample-project"',
            "captured: 2026-01-04T08:50",
            "---",
            "",
            "# Review Pack",
        ],
    )
    write_markdown(
        snapshots_dir / "2026-01-04-delivery-review-sample-project.md",
        [
            "---",
            "type: report",
            "review_type: delivery-review",
            'title: "Delivery Review — Sample Project"',
            'project: "sample-project"',
            "captured: 2026-01-04T09:30",
            "grade: B",
            "verdict: CONDITIONAL",
            "---",
            "",
            "# Delivery Review",
        ],
    )
    write_markdown(
        snapshots_dir / "2026-01-04-project-amendment-sample-project-handoff-export.md",
        [
            "---",
            "type: snapshot",
            "subtype: project-amendment",
            'title: "Project Amendment — Sample Project"',
            'project: "sample-project"',
            "captured: 2026-01-04T09:35",
            "status: pending",
            "classification: phase_amendment",
            "apply_mode: phase_brief_delta",
            'request_summary: "Also add a handoff surface and export workflow in this phase."',
            "---",
            "",
            "# Project Amendment",
        ],
    )
    write_markdown(
        snapshots_dir / "2026-01-04-delivery-review-sample-project-extra.md",
        [
            "---",
            "type: report",
            "review_type: delivery-review",
            'title: "Delivery Review — Sample Project Extra"',
            'project: "sample-project-extra"',
            "captured: 2026-01-04T09:40",
            "grade: A",
            "---",
            "",
            "# Delivery Review",
        ],
    )
    write_markdown(
        snapshots_dir / "2026-01-04-review-pack-v9-sample-project-extra.md",
        [
            "---",
            "type: snapshot",
            'title: "Review Pack — Sample Project Extra"',
            'project: "sample-project-extra"',
            "captured: 2026-01-04T09:45",
            "---",
            "",
            "# Review Pack",
        ],
    )

    write_ticket(
        tickets_dir / "T-100-build-context.md",
        ticket_id="T-100",
        title="Build context artifacts",
        project="sample-project",
        status="in-progress",
        updated="2026-01-04T09:10",
    )
    write_ticket(
        tickets_dir / "T-101-fix-review-pack.md",
        ticket_id="T-101",
        title="Fix review pack format",
        project="sample-project",
        status="blocked",
        updated="2026-01-04T09:15",
        blocked_by='["T-100"]',
    )
    write_ticket(
        tickets_dir / "T-099-phase1-closeout.md",
        ticket_id="T-099",
        title="Phase 1 closeout",
        project="sample-project",
        status="closed",
        updated="2026-01-04T08:40",
        completed="2026-01-04T08:40",
    )

    write_markdown(
        decisions_dir / "2026-01-04-context-layer-decision.md",
        [
            "---",
            'type: decision',
            'project: "sample-project"',
            "---",
            "",
            "# Decision",
        ],
    )
    write_markdown(
        lessons_dir / "2026-01-04-context-layer-lesson.md",
        [
            "---",
            'type: lesson',
            'project: "sample-project"',
            "---",
            "",
            "# Lesson",
        ],
    )

    derived_dir = project_file.parent / "sample-project.derived"
    derived_dir.mkdir(parents=True, exist_ok=True)
    image_index_path = derived_dir / "image-evidence-index.yaml"
    video_index_path = derived_dir / "video-evidence-index.yaml"
    image_index_path.write_text(
        yaml.safe_dump(
            {
                "project": "sample-project",
                "client": "acme",
                "image_evidence": {
                    "count": 2,
                    "category_counts": {"qc_screenshot": 1, "stitch_reference": 1},
                    "images": [
                        {
                            "path": "vault/clients/acme/snapshots/qc-screenshot-dashboard-health.png",
                            "category": "qc_screenshot",
                            "source_docs": ["vault/clients/acme/snapshots/2026-01-04-quality-check-sample-project.md"],
                        },
                        {
                            "path": "vault/clients/acme/snapshots/runtime-vs-stitch-home.png",
                            "category": "stitch_reference",
                            "source_docs": ["vault/clients/acme/snapshots/2026-01-04-stitch-gate-sample-project.md"],
                        },
                    ],
                },
                "semantic_image_corpus": [
                    "vault/clients/acme/snapshots/qc-screenshot-dashboard-health.png",
                    "vault/clients/acme/snapshots/runtime-vs-stitch-home.png",
                ],
            },
            sort_keys=False,
            allow_unicode=False,
        ),
        encoding="utf-8",
    )
    video_index_path.write_text(
        yaml.safe_dump(
            {
                "project": "sample-project",
                "client": "acme",
                "video_evidence": {
                    "count": 1,
                    "category_counts": {"walkthrough": 1},
                    "videos": [
                        {
                            "path": "vault/clients/acme/snapshots/qc-walkthrough-dashboard.webm",
                            "category": "walkthrough",
                            "duration_seconds": 9.76,
                            "source_docs": ["vault/clients/acme/snapshots/2026-01-04-quality-check-sample-project.md"],
                        }
                    ],
                },
                "semantic_video_corpus": ["vault/clients/acme/snapshots/qc-walkthrough-dashboard.webm"],
            },
            sort_keys=False,
            allow_unicode=False,
        ),
        encoding="utf-8",
    )

    subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--project-file", str(project_file)],
        cwd=root,
        check=True,
    )

    derived_dir = project_file.parent / "sample-project.derived"
    context_path = derived_dir / "current-context.md"
    index_path = derived_dir / "artifact-index.yaml"

    assert context_path.exists()
    assert index_path.exists()

    context_text = context_path.read_text(encoding="utf-8")
    assert "# Current Context — Sample Project" in context_text
    assert "Phase 2/4 — Delivery Hardening" in context_text
    assert "Current review surface: Delivery Review (B)" in context_text
    assert "## Goal Contract" in context_text
    assert "Rigor tier: frontier" in context_text
    assert "## Active Assumptions" in context_text
    assert "`A-001` [validating]" in context_text
    assert "A-003" not in context_text
    assert "## Pending Amendments" in context_text
    assert "project-amendment-sample-project-handoff-export.md" in context_text
    assert "phase_amendment | pending" in context_text
    assert "## Image Evidence" in context_text
    assert "Indexed images: 2" in context_text
    assert "Categories: qc_screenshot: 1, stitch_reference: 1" in context_text
    assert "`vault/clients/acme/snapshots/qc-screenshot-dashboard-health.png` (qc_screenshot)" in context_text
    assert "## Video Evidence" in context_text
    assert "Indexed videos: 1" in context_text
    assert "`vault/clients/acme/snapshots/qc-walkthrough-dashboard.webm` (walkthrough, 9.76s)" in context_text
    assert "## Code Workspaces" in context_text
    assert f"`{app_workspace}` [primary] (expected | gitnexus-pending)" in context_text
    assert f"`{framework_repo}` [dependency] (exists | git | gitnexus-disabled)" in context_text
    assert "`T-100` [in-progress] Build context artifacts" in context_text
    assert "`T-101` [blocked] Fix review pack format — blocked_by: T-100" in context_text

    report = yaml.safe_load(index_path.read_text(encoding="utf-8"))
    assert report["project"] == "sample-project"
    assert report["current_phase"] == 2
    assert report["current_phase_display"] == 2
    assert report["current_wave"] == "Wave 2B — Delivery Hardening"
    assert report["reviews"]["current_review"]["kind"] == "delivery-review"
    assert report["reviews"]["current_review"]["grade"] == "B"
    assert report["amendments"]["latest"]["classification"] == "phase_amendment"
    assert report["latest_amendment"] == "vault/clients/acme/snapshots/2026-01-04-project-amendment-sample-project-handoff-export.md"
    assert report["amendments"]["pending"][0]["status"] == "pending"
    assert report["goal_contract"]["fields"]["Rigor tier"] == "frontier"
    assert report["assumptions"]["active"][0]["ID"] == "A-001"
    assert all(row["ID"] != "A-003" for row in report["assumptions"]["active"])
    assert report["paths"]["image_evidence_index"] == "vault/clients/acme/projects/sample-project.derived/image-evidence-index.yaml"
    assert report["paths"]["video_evidence_index"] == "vault/clients/acme/projects/sample-project.derived/video-evidence-index.yaml"
    assert report["image_evidence"]["count"] == 2
    assert report["video_evidence"]["count"] == 1
    assert len(report["code_workspaces"]) == 2
    assert report["code_workspaces"][0]["role"] == "primary"
    assert report["code_workspaces"][0]["exists"] is False
    assert report["code_workspaces"][1]["role"] == "dependency"
    assert report["code_workspaces"][1]["git_repo"] is True
    assert report["code_workspaces"][1]["languages"] == ["TypeScript", "JavaScript"]
    assert report["latest_review_pack"] == "vault/clients/acme/snapshots/2026-01-04-review-pack-v2-sample-project.md"
    assert report["tickets"]["active"][0]["id"] == "T-101"
    assert report["tickets"]["blocked"][0]["id"] == "T-101"
    assert report["tickets"]["recent_closed"][0]["id"] == "T-099"
    assert "vault/clients/acme/projects/sample-project.md" in report["authoritative_files"]
    assert "vault/clients/acme/snapshots/2026-01-04-delivery-review-sample-project.md" in report["authoritative_files"]
    assert "vault/clients/acme/decisions/2026-01-04-context-layer-decision.md" in report["semantic_corpus"]
    assert "vault/clients/acme/lessons/2026-01-04-context-layer-lesson.md" in report["semantic_corpus"]
    assert "vault/clients/acme/snapshots/2026-01-04-project-amendment-sample-project-handoff-export.md" in report["semantic_corpus"]


def test_summarize_code_workspaces_marks_stale_gitnexus_when_head_mismatches(tmp_path):
    module = load_module("build_project_context_stale_gitnexus_under_test", SCRIPT_PATH)
    platform_root = tmp_path / "platform"
    platform_root.mkdir(parents=True, exist_ok=True)
    app_workspace = tmp_path / "sample-app"
    app_workspace.mkdir(parents=True, exist_ok=True)
    (app_workspace / "package.json").write_text('{"name":"sample-app"}\n', encoding="utf-8")
    (app_workspace / ".gitnexus").mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init"], cwd=app_workspace, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=app_workspace, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=app_workspace, check=True)
    subprocess.run(["git", "add", "package.json"], cwd=app_workspace, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=app_workspace, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=app_workspace, text=True).strip()
    (app_workspace / "package.json").write_text('{"name":"sample-app","version":"2"}\n', encoding="utf-8")
    subprocess.run(["git", "add", "package.json"], cwd=app_workspace, check=True)
    subprocess.run(["git", "commit", "-m", "update"], cwd=app_workspace, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    new_head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=app_workspace, text=True).strip()

    workspaces = module.summarize_code_workspaces(
        {"goal": f"Build app at {app_workspace}"},
        "",
        "",
        None,
        platform_root,
        {
            "workspaces": {
                str(app_workspace): {
                    "last_status": "refreshed",
                    "head": head,
                    "updated_at": "2026-04-15T00:00:00 EDT -0400",
                }
            }
        },
    )

    assert workspaces[0]["head"] == new_head
    assert workspaces[0]["gitnexus_ready"] is False
    assert workspaces[0]["gitnexus_stale"] is True


def test_build_project_context_handles_project_shell_without_plan(tmp_path):
    root = tmp_path / "platform"
    project_file = root / "vault" / "clients" / "acme" / "projects" / "queued-project.md"

    write_markdown(
        project_file,
        [
            "---",
            'type: project',
            'title: "Queued Project"',
            'status: planning',
            'goal: "Wait for activation."',
            "---",
            "",
            "# Queued Project",
            "",
            "## Notes",
            "",
            "- Queued behind another project.",
        ],
    )

    subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--project-file", str(project_file)],
        cwd=root,
        check=True,
    )

    derived_dir = project_file.parent / "queued-project.derived"
    context_path = derived_dir / "current-context.md"
    index_path = derived_dir / "artifact-index.yaml"

    assert context_path.exists()
    assert index_path.exists()

    context_text = context_path.read_text(encoding="utf-8")
    assert "- Status: `planning`" in context_text
    assert "## Active Tickets" in context_text
    assert "- No active tickets." in context_text
    assert "## Image Evidence" in context_text
    assert "- No indexed image evidence yet." in context_text
    assert "## Video Evidence" in context_text
    assert "- No indexed video evidence yet." in context_text

    report = yaml.safe_load(index_path.read_text(encoding="utf-8"))
    assert report["status"] == "planning"
    assert report["current_phase"] is None
    assert report["reviews"]["current_review"] is None
    assert report["authoritative_files"] == ["vault/clients/acme/projects/queued-project.md"]
    assert report["image_evidence"]["count"] == 0
    assert report["video_evidence"]["count"] == 0


def test_build_project_context_preserves_zero_based_phase_display_when_phase_zero_is_active(tmp_path):
    root = tmp_path / "platform"
    project_file = root / "vault" / "projects" / "zero-based.md"
    snapshots_dir = root / "vault" / "snapshots"

    write_markdown(
        project_file,
        [
            "---",
            'type: project',
            'title: "Zero Based"',
            'status: active',
            'goal: "Verify phase zero display."',
            "---",
            "",
            "# Zero Based",
            "",
        ],
    )

    write_markdown(
        snapshots_dir / "2026-04-13-project-plan-zero-based.md",
        [
            "---",
            "type: snapshot",
            "subtype: project-plan",
            'project: "zero-based"',
            "current_phase: 0",
            "total_phases: 3",
            "captured: 2026-04-13T12:00",
            "---",
            "",
            "# Project Plan — Zero Based",
            "",
            "## Goal Contract",
            "",
            "- **Rigor tier:** standard",
            "- **Mission:** verify phase zero display.",
            "- **Primary evaluator:** admin",
            "- **Mission success:** phase labels stay human-readable.",
            "- **Primary success metrics:** phase zero renders as 1/3.",
            "- **Primary risks:** off-by-one display bugs.",
            "- **Human-owned decisions:** accept UI wording.",
            "- **Agent-owned execution:** render project context correctly.",
            "- **Proof shape:** local parser checks.",
            "- **In scope:** phase labeling",
            "- **Out of scope:** unrelated UI work",
            "- **Partial-coverage rule:** none.",
            "",
            "### Goal Workstreams",
            "",
            "| Goal / Workstream | Type | Priority | Success Signal | Evaluator | Scale / Scope |",
            "|-------------------|------|----------|----------------|-----------|---------------|",
            "| WS-1 phase display | quality | critical | zero-based phase renders correctly | admin | parser |",
            "",
            "## Assumption Register",
            "",
            "| ID | Assumption | Category | Risk | Validation Method | Owner | Target Phase/Gate | Status | Evidence / Resolution |",
            "|----|------------|----------|------|-------------------|-------|-------------------|--------|-----------------------|",
            "| A-001 | phase zero is intentional | workflow | low | parser test | orchestrator | Phase 0 | validating | covered by fixture |",
            "",
            "## Phases",
            "",
            "### Phase 0: Runtime Preflight (active)",
            "**Goal:** preflight",
            "**Exit criteria:**",
            "- parser renders phase zero correctly",
            "",
            "### Phase 1: Foundation (planned)",
            "**Goal:** foundation",
            "**Exit criteria:**",
            "- foundation starts next",
            "",
        ],
    )

    subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--project-file", str(project_file)],
        cwd=root,
        check=True,
    )

    derived_dir = project_file.parent / "zero-based.derived"
    index = yaml.safe_load((derived_dir / "artifact-index.yaml").read_text(encoding="utf-8"))
    assert index["current_phase"] == 0
    assert index["current_phase_display"] == 1

    context_text = (derived_dir / "current-context.md").read_text(encoding="utf-8")
    assert "- Current phase: Phase 1/3 — Runtime Preflight (active)" in context_text
