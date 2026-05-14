#!/usr/bin/env python3
"""Detect visual ambition signals in a creative brief."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
PLATFORM_PATH = REPO_ROOT / "vault" / "config" / "platform.md"
DEFAULT_KEYWORDS = ["beautiful", "gorgeous", "premium UI", "crafted UI", "pixel-perfect", "polished UI"]
DEFAULT_BRANDS = ["Apple", "Linear", "Stripe", "Vercel", "Things", "Notion", "Mercury", "Brex"]
DEFAULT_SURFACES = ["dashboard", "landing", "marketing site", "operator console", "brand identity", "animation", "reel"]
MEDIUM_KEYWORDS: dict[str, list[str]] = {
    "3d_render": ["3d", "3d render", "3d model", "blender", "glb", "gltf", "product render", "rendered scene"],
    "brand_identity": ["brand identity", "brand system", "logo", "visual identity", "identity system", "brand package"],
    "data_visualization": ["data visualization", "chart", "charts", "graph", "graphs", "plot", "map visualization", "infographic"],
    "document_typography": ["document", "pdf", "report", "whitepaper", "typography", "proposal doc", "one-pager"],
    "game_ui": ["game ui", "game interface", "hud", "heads-up display", "inventory screen", "game menu"],
    "native_ui": ["native ui", "native app", "ios", "android", "macos", "desktop app", "mobile app", "system settings"],
    "none": ["no visual deliverable", "no visual medium", "text only", "backend only", "cli only"],
    "presentation": ["presentation", "slide deck", "slides", "deck", "powerpoint", "keynote", "pitch deck"],
    "video_animation": ["video", "animation", "motion", "motion graphics", "reel", "explainer", "animated"],
    "web_ui": ["web ui", "web app", "website", "landing page", "marketing site", "dashboard", "operator console", "saas"],
}


def utc_now() -> str:
    """Return a UTC ISO-8601 timestamp with timezone."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def strip_frontmatter(text: str) -> str:
    """Remove leading YAML frontmatter from markdown."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return text
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return "\n".join(lines[index + 1 :]).strip()
    return text


def parse_platform_list(key: str, default: list[str]) -> list[str]:
    """Read a YAML inline list from platform.md."""
    if not PLATFORM_PATH.exists():
        return default
    text = PLATFORM_PATH.read_text(encoding="utf-8")
    match = re.search(rf"^\s*{re.escape(key)}:\s*(\[.*\])\s*$", text, flags=re.M)
    if not match:
        return default
    try:
        import yaml
    except ImportError:
        return default
    loaded = yaml.safe_load(match.group(1))
    if not isinstance(loaded, list):
        return default
    return [str(item) for item in loaded if str(item).strip()]


def phrase_matches(text: str, phrases: list[str]) -> list[str]:
    """Return configured phrases found in text, preserving configured casing."""
    matches: list[str] = []
    for phrase in phrases:
        escaped = re.escape(phrase)
        pattern = rf"(?<![A-Za-z0-9]){escaped}(?![A-Za-z0-9])"
        if re.search(pattern, text, flags=re.I):
            matches.append(phrase)
    return matches


def explicit_target_mentions(text: str) -> list[str]:
    """Detect explicit visual_quality_target_* mentions."""
    matches = re.findall(r"\bvisual_quality_target_[a-z0-9_]+\b", text, flags=re.I)
    seen: set[str] = set()
    result: list[str] = []
    for match in matches:
        key = match.lower()
        if key not in seen:
            seen.add(key)
            result.append(match)
    return result


def ambition_score(signals: dict[str, list[str]]) -> str:
    """Classify the visual ambition score."""
    quality = len(signals["quality_adjectives"])
    branded = len(signals["branded_signals"])
    surfaces = len(signals["surface_keywords"])
    explicit = len(signals["explicit_target_mentions"])
    total = quality + branded + surfaces + explicit
    if (quality >= 1 and surfaces >= 1) or branded >= 2:
        return "high"
    if quality or branded or surfaces:
        return "moderate"
    if explicit:
        return "low"
    if total == 0:
        return "none"
    return "low"


def infer_medium(text: str) -> dict[str, Any]:
    """Infer the visual medium from deterministic keyword matches."""
    matches: dict[str, list[str]] = {}
    for medium, phrases in MEDIUM_KEYWORDS.items():
        found = phrase_matches(text, phrases)
        if found:
            matches[medium] = found
    explicit = re.findall(r"\bvisual_quality_target_medium\s*[:=]\s*([A-Za-z0-9_:-]+)", text, flags=re.I)
    for value in explicit:
        medium = value.strip().lower().replace("-", "_")
        if medium in MEDIUM_KEYWORDS:
            matches.setdefault(medium, []).append(f"visual_quality_target_medium:{medium}")
    if not matches:
        return {"inferred_medium": "ambiguous", "medium_confidence": 0, "medium_signals": {}}
    scored = {medium: len(set(found)) for medium, found in matches.items()}
    inferred = sorted(scored, key=lambda medium: (-scored[medium], medium))[0]
    return {
        "inferred_medium": inferred,
        "medium_confidence": scored[inferred],
        "medium_signals": {medium: sorted(set(found)) for medium, found in sorted(matches.items())},
    }


def detect_ambition(brief_path: Path) -> dict[str, Any]:
    """Scan a brief for configured visual ambition signals."""
    raw_text = brief_path.read_text(encoding="utf-8")
    text = strip_frontmatter(raw_text)
    keywords = parse_platform_list("visual_ambition_keywords", DEFAULT_KEYWORDS)
    brands = parse_platform_list("visual_ambition_branded_signals", DEFAULT_BRANDS)
    surfaces = parse_platform_list("visual_ambition_surface_keywords", DEFAULT_SURFACES)
    signals = {
        "quality_adjectives": phrase_matches(text, keywords),
        "branded_signals": phrase_matches(text, brands),
        "surface_keywords": phrase_matches(text, surfaces),
        "explicit_target_mentions": explicit_target_mentions(text),
    }
    score = ambition_score(signals)
    medium = infer_medium(raw_text)
    return {
        "brief_path": str(brief_path),
        "scanned_at": utc_now(),
        "signals": signals,
        "ambition_detected": score != "none",
        "ambition_score": score,
        **medium,
    }


def write_json(data: dict[str, Any], json_out: str | None = None) -> None:
    """Write JSON to stdout and optionally to a file."""
    text = json.dumps(data, indent=2, sort_keys=True) + "\n"
    sys.stdout.write(text)
    if json_out:
        out_path = Path(json_out).expanduser().resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text, encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--brief", required=True, help="Creative brief markdown path.")
    parser.add_argument("--json-out", help="Optional JSON output path.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        result = detect_ambition(Path(args.brief).expanduser().resolve())
        write_json(result, args.json_out)
        return 0
    except Exception as exc:
        result = {
            "brief_path": args.brief,
            "scanned_at": utc_now(),
            "error": str(exc),
            "ambition_detected": False,
            "ambition_score": "none",
            "inferred_medium": "none",
            "medium_confidence": 0,
            "medium_signals": {},
        }
        write_json(result, args.json_out)
        return 1


if __name__ == "__main__":
    sys.exit(main())
