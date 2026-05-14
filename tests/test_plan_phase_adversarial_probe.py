from __future__ import annotations

import importlib.util
import sys
import textwrap
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "scripts" / "plan_phase_adversarial_probe.py"


def load_module(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(text).strip() + "\n", encoding="utf-8")


def test_explicit_phase_probe_contract_requires_probe(tmp_path):
    planner = load_module("plan_phase_probe_explicit", MODULE_PATH)
    plan_path = tmp_path / "plan.md"
    brief_path = tmp_path / "phase-brief.md"
    resolution_path = tmp_path / "brief-resolution.md"

    write_text(
        plan_path,
        """
        ---
        project: demo-project
        ---

        # Project Plan

        ### Phase 1: Native Runtime + Security Foundation (active)
        **Goal:** Ship Tauri runtime, permissions, and credential vault.
        """,
    )
    write_text(
        brief_path,
        """
        ---
        phase_adversarial_probe_required: true
        adversarial_probe_risk_families:
          - auth_security
          - runtime_permissions
        ---

        # Phase Brief

        ## Phase-Level Adversarial Probe Pack

        Trigger rationale: native runtime and security boundaries are new in this phase.
        """,
    )
    write_text(
        resolution_path,
        f"""
        # Brief Resolution

        ## Ordered Brief Stack

        - `phase` — `Phase Brief` → `{brief_path}`
        """,
    )

    report = planner.build_report(plan_path, 1, resolution_path)

    assert report["required"] is True
    assert report["trigger_mode"] == "explicit"
    assert "auth_security" in report["risk_families"]
    assert "runtime_permissions" in report["risk_families"]
    assert report["recommended_task_type"] == "adversarial_probe"


def test_heuristic_risky_build_phase_requires_probe_without_explicit_brief(tmp_path):
    planner = load_module("plan_phase_probe_heuristic", MODULE_PATH)
    plan_path = tmp_path / "plan.md"
    write_text(
        plan_path,
        """
        ---
        project: demo-project
        ---

        # Project Plan

        ### Phase 2: Retrieval + Integrations Foundation (planned)
        **Goal:** Add semantic retrieval, memory sync, tool access adapters, and external API integrations.
        **Exit criteria:**
        - retrieval and sync are healthy
        - integrations handle missing credentials safely
        """,
    )

    report = planner.build_report(plan_path, 2)

    assert report["required"] is True
    assert report["trigger_mode"] == "heuristic"
    assert "retrieval_memory_sync" in report["risk_families"]
    assert "integrations_external_io" in report["risk_families"]
    assert report["recommended_complexity"] == "normal" or report["recommended_complexity"] == "deep"


def test_review_phase_skips_phase_level_probe_by_default(tmp_path):
    planner = load_module("plan_phase_probe_review_skip", MODULE_PATH)
    plan_path = tmp_path / "plan.md"
    write_text(
        plan_path,
        """
        ---
        project: demo-project
        ---

        # Project Plan

        ### Phase 6: Artifact Polish Review (planned)
        **Goal:** Clean-room review of the finished artifact pack.
        """,
    )

    report = planner.build_report(plan_path, 6)

    assert report["required"] is False
    assert report["trigger_mode"] == "phase_kind_skip"
    assert report["phase_kind"] == "review"


def test_low_risk_phase_without_risk_surface_skips_probe(tmp_path):
    planner = load_module("plan_phase_probe_none", MODULE_PATH)
    plan_path = tmp_path / "plan.md"
    write_text(
        plan_path,
        """
        ---
        project: demo-project
        ---

        # Project Plan

        ### Phase 3: Content Structure Refinement (planned)
        **Goal:** Tighten copy, labels, and information hierarchy without changing runtime behavior.
        """,
    )

    report = planner.build_report(plan_path, 3)

    assert report["required"] is False
    assert report["trigger_mode"] == "none"
    assert report["risk_families"] == []
