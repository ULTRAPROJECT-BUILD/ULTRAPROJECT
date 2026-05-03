from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PLATFORM_CONFIG = REPO_ROOT / "vault" / "config" / "platform.md"


def read_platform_config() -> str:
    return PLATFORM_CONFIG.read_text(encoding="utf-8")


def test_runtime_screenshot_preservation_policy_is_semantic():
    text = read_platform_config()

    required_fragments = [
        "runtime_screenshot_hashes_are_copy_integrity_only: true",
        "dynamic_ui_preservation_requires_semantic_gate: true",
        "runtime_ui_screenshots_must_not_require_byte_identity_across_captures: true",
        "screenshot_laundering_for_gate_pass_prohibited: true",
        "Runtime screenshots and walkthroughs are dynamic proof artifacts.",
        "Their file hashes prove mirror/copy integrity for the same captured artifact",
        "semantic preservation gate instead of byte-identical runtime PNGs",
        "Do not copy old screenshots into a current evidence bundle just to force matching hashes.",
    ]

    for fragment in required_fragments:
        assert fragment in text


def test_default_worker_routing_conserves_claude_tokens():
    text = read_platform_config()

    codex_worker_routes = [
        "creative_brief: codex",
        "self_review: codex",
        "quality_check: codex",
        "artifact_polish_review: codex",
        "credibility_gate: codex",
        "code_build: codex",
        "code_review: codex",
        "code_fix: codex",
        "evidence_cleanup: codex",
        "general: codex",
    ]

    for route in codex_worker_routes:
        assert route in text

    assert "visual_review: claude" in text
    assert "routing_override_tags: []" in text
