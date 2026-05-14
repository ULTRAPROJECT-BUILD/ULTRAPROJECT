#!/usr/bin/env python3
"""Extract native_ui design tokens from Figma plugin JSON or Sketch JSON."""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
import zipfile
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from typing import Any

HEX_RE = re.compile(r"#[0-9A-Fa-f]{3,8}\b")
NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?")


def warn(message: str) -> None:
    print(f"warning: {message}", file=sys.stderr)


def slug(value: Any, fallback: str = "token") -> str:
    text = str(value or fallback).strip().lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    if not text or not re.match(r"^[a-z]", text):
        text = f"{fallback}_{text or 'value'}"
    return text


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def read_json(path: Path) -> Any:
    return json.loads(read_text(path))


def walk(value: Any) -> list[Any]:
    items = [value]
    if isinstance(value, dict):
        for child in value.values():
            items.extend(walk(child))
    elif isinstance(value, list):
        for child in value:
            items.extend(walk(child))
    return items


def iter_dicts(value: Any) -> list[dict[str, Any]]:
    return [item for item in walk(value) if isinstance(item, dict)]


def first_number(*values: Any, default: float = 0) -> float:
    for value in values:
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
        if isinstance(value, str):
            match = NUMBER_RE.search(value)
            if match:
                return float(match.group(0))
    return default


def clamp_int(value: float, lo: int, hi: int) -> int:
    return max(lo, min(hi, int(round(value))))


def normalize_hex(value: str | None) -> str | None:
    if not value:
        return None
    value = value.strip()
    match = HEX_RE.search(value)
    if not match:
        return None
    raw = match.group(0).lstrip("#")
    if len(raw) == 3:
        raw = "".join(ch * 2 for ch in raw)
    return f"#{raw[:6].upper()}"


def rgb_to_hex(r: float, g: float, b: float) -> str:
    def channel(v: float) -> int:
        if 0 <= v <= 1:
            return int(round(v * 255))
        return int(round(max(0, min(255, v))))
    return f"#{channel(r):02X}{channel(g):02X}{channel(b):02X}"


def colors_from_any(value: Any) -> list[str]:
    colors: list[str] = []
    if isinstance(value, str):
        found = normalize_hex(value)
        if found:
            colors.append(found)
    if isinstance(value, dict):
        if all(key in value for key in ("r", "g", "b")):
            colors.append(rgb_to_hex(float(value["r"]), float(value["g"]), float(value["b"])))
        if all(key in value for key in ("red", "green", "blue")):
            colors.append(rgb_to_hex(float(value["red"]), float(value["green"]), float(value["blue"])))
        for child in value.values():
            colors.extend(colors_from_any(child))
    elif isinstance(value, list):
        for child in value:
            colors.extend(colors_from_any(child))
    seen: list[str] = []
    for color in colors:
        if color not in seen:
            seen.append(color)
    return seen


def collect_numbers(value: Any, keys: set[str] | None = None) -> list[float]:
    nums: list[float] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if keys is None or slug(key) in keys or str(key).lower() in keys:
                if isinstance(child, (int, float)) and not isinstance(child, bool):
                    nums.append(float(child))
                elif isinstance(child, str):
                    nums.extend(float(m.group(0)) for m in NUMBER_RE.finditer(child))
            nums.extend(collect_numbers(child, keys))
    elif isinstance(value, list):
        for child in value:
            nums.extend(collect_numbers(child, keys))
    elif isinstance(value, str) and keys is None:
        nums.extend(float(m.group(0)) for m in NUMBER_RE.finditer(value))
    return nums


def unique_sorted_numbers(nums: list[float], limit: int = 12) -> list[int]:
    values = sorted({int(round(n)) for n in nums if math.isfinite(n) and n >= 0})
    return values[:limit]


def load_inputs(mockup: Path) -> list[tuple[Path, Any, str]]:
    paths: list[Path]
    if mockup.is_dir():
        paths = [p for p in sorted(mockup.rglob("*")) if p.is_file()]
    else:
        paths = [mockup]
    loaded: list[tuple[Path, Any, str]] = []
    for path in paths:
        suffix = path.suffix.lower()
        try:
            if suffix == ".json":
                loaded.append((path, read_json(path), "json"))
            elif suffix in {".html", ".htm", ".css", ".tex", ".sty", ".svg", ".tscn", ".tres", ".unity", ".prefab", ".uasset.txt", ".xml"}:
                loaded.append((path, read_text(path), "text"))
            elif suffix in {".pptx", ".sketch"}:
                loaded.append((path, load_zip_members(path), "zip"))
            elif suffix in {".blend", ".hip", ".uasset"}:
                raise RuntimeError(f"{path.name} is a binary source. Export JSON metadata first; install the source application CLI if needed.")
        except RuntimeError:
            raise
        except Exception as exc:
            warn(f"skipping {path}: {exc}")
    return loaded


def load_zip_members(path: Path) -> dict[str, str]:
    members: dict[str, str] = {}
    with zipfile.ZipFile(path) as archive:
        for name in archive.namelist():
            lower = name.lower()
            if lower.endswith((".xml", ".json", ".rels")):
                try:
                    members[name] = archive.read(name).decode("utf-8", errors="ignore")
                except Exception as exc:
                    warn(f"could not read {name} in {path}: {exc}")
    return members


def write_payload(payload: dict[str, Any], out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def palette_with_defaults(colors: list[str], defaults: list[str], limit: int = 8) -> list[str]:
    merged: list[str] = []
    for color in colors + defaults:
        normalized = normalize_hex(color)
        if normalized and normalized not in merged:
            merged.append(normalized)
    return merged[:limit]


def fail_with_install_instructions(message: str) -> RuntimeError:
    return RuntimeError(message + " Export a supported JSON/XML/CSS source or install the source application's CLI and rerun extraction.")


def ensure_family(payload: dict[str, Any], family: str) -> None:
    if family not in payload:
        raise ValueError(f"token family missing from extractor payload: {family}")
    value = payload[family]
    if value in ({}, [], None, ""):
        raise ValueError(f"token family is empty in extractor payload: {family}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mockup", required=True, help="Locked mockup source file or directory.")
    parser.add_argument("--out", required=True, help="Output JSON path.")
    return parser.parse_args()


def text_style_from_node(node: dict[str, Any], fallback: str) -> tuple[str, dict[str, Any]] | None:
    style = node.get("style") or node.get("textStyle") or node.get("text") or {}
    if not isinstance(style, dict):
        return None
    size = first_number(style.get("fontSize"), style.get("size"), node.get("fontSize"), default=0)
    if not size:
        return None
    name = slug(node.get("name") or style.get("name") or fallback)
    family = str(style.get("fontFamily") or style.get("fontPostScriptName") or style.get("family") or ".system")
    line_height = first_number(style.get("lineHeightPx"), style.get("lineHeight"), style.get("line_height"), default=size * 1.2)
    return name, {
        "family": family,
        "size": size,
        "weight": style.get("fontWeight") or style.get("weight") or "regular",
        "line_height": line_height,
        "platform_text_style": str(style.get("textStyle") or style.get("platformTextStyle") or name),
    }


def extract_tokens(mockup: Path) -> dict[str, Any]:
    data_items = load_inputs(mockup)
    roots = [data for _, data, _ in data_items]
    dynamic: dict[str, Any] = {}
    colors: list[str] = []
    spacing_nums: list[float] = []
    radii: list[float] = []
    elevations: dict[str, Any] = {}
    motions: dict[str, Any] = {}
    materials: dict[str, Any] = {}
    safe = {"top": 0, "bottom": 0, "leading": 0, "trailing": 0}
    focus = {"ring_width": 2, "color_alpha_pct": 80, "corner_radius": 6}
    for root in roots:
        colors.extend(colors_from_any(root))
        spacing_nums.extend(collect_numbers(root, {"padding", "spacing", "gap", "itemspacing", "margin"}))
        radii.extend(collect_numbers(root, {"cornerradius", "borderradius", "radius"}))
        for node in iter_dicts(root):
            style = text_style_from_node(node, f"style_{len(dynamic)+1}")
            if style:
                dynamic.setdefault(style[0], style[1])
            name = slug(node.get("name") or node.get("id") or f"token_{len(elevations)+1}")
            effects = node.get("effects") or node.get("shadows") or []
            if isinstance(effects, list) and effects:
                elevations.setdefault(name, {"effects": effects})
                for effect in effects:
                    if isinstance(effect, dict) and "blur" in str(effect).lower():
                        materials.setdefault(name, {
                            "blur_radius": first_number(effect.get("radius"), effect.get("blurRadius"), effect.get("blur"), default=12),
                            "alpha_pct": clamp_int(first_number(effect.get("opacity"), effect.get("alpha"), default=0.72) * 100 if first_number(effect.get("opacity"), effect.get("alpha"), default=0.72) <= 1 else first_number(effect.get("opacity"), effect.get("alpha"), default=72), 0, 100),
                            "tint": (colors_from_any(effect) or ["#FFFFFF"])[0],
                        })
            if any(k in node for k in ("duration", "durationMs", "easing", "curve")):
                motions.setdefault(name, {
                    "duration_ms": clamp_int(first_number(node.get("durationMs"), node.get("duration"), default=180) * (1000 if first_number(node.get("duration"), default=0) <= 10 and "durationMs" not in node else 1), 0, 5000),
                    "curve": str(node.get("curve") or node.get("easing") or "easeInOut"),
                })
            inset = node.get("safeAreaInsets") or node.get("safe_area_insets")
            if isinstance(inset, dict):
                safe = {
                    "top": clamp_int(first_number(inset.get("top"), default=safe["top"]), 0, 200),
                    "bottom": clamp_int(first_number(inset.get("bottom"), default=safe["bottom"]), 0, 200),
                    "leading": clamp_int(first_number(inset.get("leading"), inset.get("left"), default=safe["leading"]), 0, 200),
                    "trailing": clamp_int(first_number(inset.get("trailing"), inset.get("right"), default=safe["trailing"]), 0, 200),
                }
            if "focus" in str(node.get("name", "")).lower() or "focus" in str(node).lower():
                focus["ring_width"] = clamp_int(first_number(node.get("ringWidth"), node.get("strokeWeight"), default=focus["ring_width"]), 0, 16)
                focus["corner_radius"] = clamp_int(first_number(node.get("cornerRadius"), default=focus["corner_radius"]), 0, 80)
    defaults = [
        ("large_title", 34, "bold"), ("title", 28, "semibold"), ("headline", 17, "semibold"),
        ("body", 17, "regular"), ("caption", 12, "regular"),
    ]
    for name, size, weight in defaults:
        dynamic.setdefault(name, {"family": ".system", "size": size, "weight": weight, "line_height": round(size * 1.22, 2), "platform_text_style": name})
    palette = list(dict.fromkeys(colors + ["#111111", "#666666", "#8A8A8E", "#FFFFFF", "#F5F5F7", "#D1D1D6", "#007AFF", "#34C759", "#FFCC00", "#FF3B30"]))
    color_keys = ["label", "secondary_label", "tertiary_label", "system_background", "secondary_system_background", "separator", "tint", "success", "warning", "destructive"]
    color_payload = {key: palette[i % len(palette)] for i, key in enumerate(color_keys)}
    scale = unique_sorted_numbers(spacing_nums, 10) or [0, 4, 8, 12, 16, 20, 24, 32]
    while len(scale) < 6:
        scale.append(scale[-1] + 4 if scale else 4)
    radius_values = unique_sorted_numbers(radii, 6) or [0, 6, 10, 16]
    corner = {f"r{i}": int(v) for i, v in enumerate(radius_values[:6])}
    while len(corner) < 4:
        corner[f"r{len(corner)}"] = len(corner) * 4
    elevations.setdefault("level_1", "shadow-sm")
    for name, dur, curve in [("state_change", 160, "easeInOut"), ("sheet", 260, "spring"), ("focus", 120, "easeOut")]:
        motions.setdefault(name, {"duration_ms": dur, "curve": curve})
    materials.setdefault("system_material", {"blur_radius": 18, "alpha_pct": 82, "tint": "#FFFFFF"})
    return {
        "dynamic_type_scale": dict(list(dynamic.items())[:12]),
        "color": color_payload,
        "spacing": {"base": 4, "scale": scale[:10]},
        "corner_radius": corner,
        "elevation": elevations,
        "motion": motions,
        "safe_area_insets": safe,
        "focus": focus,
        "materials": materials,
    }


def main() -> int:
    args = parse_args()
    mockup = Path(args.mockup)
    if not mockup.exists():
        print(f"mockup path not found: {mockup}", file=sys.stderr)
        return 2
    try:
        payload = extract_tokens(mockup)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    write_payload(payload, Path(args.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
