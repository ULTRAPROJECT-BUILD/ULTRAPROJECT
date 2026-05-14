#!/usr/bin/env python3
"""Lint manifest color tokens for WCAG AA contrast."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SURFACE_RE = re.compile(r"^(surface|bg|background|card|panel)", re.IGNORECASE)
TEXT_RE = re.compile(r"^(text|foreground|fg|body|heading)", re.IGNORECASE)
ACCENT_RE = re.compile(r"^(accent|link|primary)", re.IGNORECASE)
HEX_RE = re.compile(r"^#?([0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")
WCAG_AA_BODY = 4.5


def utc_now() -> str:
    """Return a timezone-aware UTC ISO timestamp."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def expand_hex(value: str) -> tuple[int, int, int] | None:
    """Parse #RGB/#RRGGBB color strings, ignoring alpha when present."""
    match = HEX_RE.match(value.strip())
    if not match:
        return None
    raw = match.group(1)
    if len(raw) in {3, 4}:
        raw = "".join(char * 2 for char in raw[:3])
    elif len(raw) == 8:
        raw = raw[:6]
    return int(raw[0:2], 16), int(raw[2:4], 16), int(raw[4:6], 16)


def srgb_channel_to_linear(channel: int) -> float:
    """Convert an 8-bit sRGB channel to linear light."""
    value = channel / 255
    if value <= 0.03928:
        return value / 12.92
    return ((value + 0.055) / 1.055) ** 2.4


def relative_luminance(hex_color: str) -> float:
    """Compute WCAG relative luminance for a hex color."""
    rgb = expand_hex(hex_color)
    if rgb is None:
        raise ValueError(f"Unsupported color value: {hex_color!r}")
    red, green, blue = (srgb_channel_to_linear(channel) for channel in rgb)
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def contrast_ratio(foreground: str, background: str) -> float:
    """Return the WCAG contrast ratio between two colors."""
    lum_a = relative_luminance(foreground)
    lum_b = relative_luminance(background)
    lighter = max(lum_a, lum_b)
    darker = min(lum_a, lum_b)
    return (lighter + 0.05) / (darker + 0.05)


def extract_color_tokens(tokens: dict[str, Any]) -> dict[str, str]:
    """Return flat token-name to hex-value pairs from a token object."""
    colors: dict[str, str] = {}
    for name, value in tokens.items():
        color_value = value
        if isinstance(value, dict):
            color_value = value.get("value", value.get("$value"))
        if not isinstance(color_value, str):
            continue
        if expand_hex(color_value) is None:
            continue
        colors[str(name)] = color_value
    return colors


def waiver_pairs(manifest: dict[str, Any]) -> set[tuple[str, str]]:
    """Collect waived (text_token, surface_token) pairs from the manifest."""
    contrast_validation = manifest.get("contrast_validation", {})
    waivers = contrast_validation.get("waivers", []) if isinstance(contrast_validation, dict) else []
    pairs: set[tuple[str, str]] = set()
    if not isinstance(waivers, list):
        return pairs
    for waiver in waivers:
        if not isinstance(waiver, dict):
            continue
        text_token = str(waiver.get("text_token", "")).strip()
        surface_token = str(waiver.get("surface_token", "")).strip()
        if text_token and surface_token:
            pairs.add((text_token, surface_token))
    return pairs


def check_manifest_contrast(manifest_path: Path) -> dict[str, Any]:
    """Check candidate token pairs from a visual-spec manifest."""
    resolved = manifest_path.expanduser().resolve()
    manifest = json.loads(resolved.read_text(encoding="utf-8"))
    token_root = manifest.get("tokens", {})
    color_root = token_root.get("color", {}) if isinstance(token_root, dict) else {}
    colors = extract_color_tokens(color_root if isinstance(color_root, dict) else {})

    surfaces = {name: value for name, value in colors.items() if SURFACE_RE.search(name)}
    foregrounds = {name: value for name, value in colors.items() if TEXT_RE.search(name)}
    accents = {name: value for name, value in colors.items() if ACCENT_RE.search(name)}
    waived_pairs = waiver_pairs(manifest)

    failed: list[dict[str, Any]] = []
    pairs_checked = 0
    passed = 0
    waived = 0

    for fg_name, fg_value in {**foregrounds, **accents}.items():
        for surface_name, surface_value in surfaces.items():
            pairs_checked += 1
            ratio = contrast_ratio(fg_value, surface_value)
            if (fg_name, surface_name) in waived_pairs:
                waived += 1
                continue
            if ratio < WCAG_AA_BODY:
                failed.append(
                    {
                        "text_token": fg_name,
                        "surface_token": surface_name,
                        "ratio": round(ratio, 3),
                        "required": WCAG_AA_BODY,
                    }
                )
            else:
                passed += 1

    return {
        "ran_at": utc_now(),
        "pairs_checked": pairs_checked,
        "passed": passed,
        "failed": failed,
        "waived": waived,
        "verdict": "pass" if not failed else "fail",
    }


def write_json(data: dict[str, Any], json_out: str | None = None) -> None:
    """Write JSON to stdout and, optionally, to a file."""
    text = json.dumps(data, indent=2, sort_keys=True) + "\n"
    sys.stdout.write(text)
    if json_out:
        out_path = Path(json_out).expanduser()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text, encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, help="Visual-spec manifest JSON path.")
    parser.add_argument("--json-out", help="Optional path to write the JSON result.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        data = check_manifest_contrast(Path(args.manifest))
    except Exception as exc:
        data = {"ran_at": utc_now(), "error": str(exc), "verdict": "fail"}
        write_json(data, args.json_out)
        return 1
    write_json(data, args.json_out)
    return 0 if data["verdict"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
