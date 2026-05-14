#!/usr/bin/env python3
"""Extract presentation tokens from PPTX slide-master XML or HTML deck source."""

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


def parse_pptx_xml(members: dict[str, str]) -> tuple[dict[str, Any], list[str], list[dict[str, Any]]]:
    grid = {"page_width": 1280, "page_height": 720, "margin": 72, "columns": 12, "rows": 6, "gutter": 24}
    colors: list[str] = []
    text_styles: list[dict[str, Any]] = []
    for name, text in members.items():
        colors.extend(colors_from_any(text))
        if name.endswith("presentation.xml"):
            cx = re.search(r'cx="(\d+)"', text)
            cy = re.search(r'cy="(\d+)"', text)
            if cx and cy:
                grid["page_width"] = round(int(cx.group(1)) / 9525, 2)
                grid["page_height"] = round(int(cy.group(1)) / 9525, 2)
        if "sldMaster" in name or "slideLayout" in name or "theme" in name:
            for size in re.findall(r'sz="(\d+)"', text):
                pt = int(size) / 100
                text_styles.append({"family": "theme", "size": pt, "weight": "regular", "leading": round(pt * 1.12, 2), "tracking": 0})
    return grid, colors, text_styles


def parse_html_deck(text: str) -> tuple[list[str], list[dict[str, Any]], list[str]]:
    colors = colors_from_any(text)
    sizes = [float(m.group(1)) for m in re.finditer(r"font-size\s*:\s*([0-9.]+)", text, re.I)]
    transitions = re.findall(r"data-transition=[\"']([^\"']+)", text)
    styles = [{"family": "deck", "size": s, "weight": "regular", "leading": round(s * 1.12, 2), "tracking": 0} for s in sizes]
    return colors, styles, transitions


def extract_tokens(mockup: Path) -> dict[str, Any]:
    inputs = load_inputs(mockup)
    grid = {"page_width": 1280, "page_height": 720, "margin": 72, "columns": 12, "rows": 6, "gutter": 24}
    colors: list[str] = []
    styles: list[dict[str, Any]] = []
    transition_names: list[str] = []
    for _, data, kind in inputs:
        if kind == "zip" and isinstance(data, dict):
            parsed_grid, parsed_colors, parsed_styles = parse_pptx_xml(data)
            grid.update(parsed_grid)
            colors.extend(parsed_colors)
            styles.extend(parsed_styles)
        elif isinstance(data, str):
            parsed_colors, parsed_styles, parsed_transitions = parse_html_deck(data)
            colors.extend(parsed_colors)
            styles.extend(parsed_styles)
            transition_names.extend(parsed_transitions)
        elif isinstance(data, dict):
            colors.extend(colors_from_any(data))
            for node in iter_dicts(data):
                if any(k in node for k in ("fontSize", "size", "font_size")):
                    s = first_number(node.get("fontSize"), node.get("font_size"), node.get("size"), default=24)
                    styles.append({"family": str(node.get("fontFamily") or "deck"), "size": s, "weight": node.get("fontWeight") or "regular", "leading": first_number(node.get("lineHeight"), default=s * 1.15), "tracking": first_number(node.get("tracking"), default=0)})
                if "transition" in node:
                    transition_names.append(str(node.get("transition")))
    defaults = [("display", 72, "bold"), ("title", 48, "semibold"), ("subtitle", 32, "regular"), ("body", 24, "regular"), ("caption", 16, "regular")]
    type_payload: dict[str, Any] = {}
    for index, style in enumerate(styles[:8]):
        type_payload.setdefault(f"style_{index+1}", style)
    for name, size, weight in defaults:
        type_payload.setdefault(name, {"family": "Inter", "size": size, "weight": weight, "leading": round(size * 1.12, 2), "tracking": 0})
    palette = list(dict.fromkeys(colors + ["#FFFFFF", "#F7F7F8", "#111111", "#5F6368", "#0066FF", "#D8DCE2"]))
    transitions: dict[str, Any] = {}
    normalized = transition_names or ["none", "fade", "push"]
    allowed = {"none", "cut", "fade", "push", "wipe", "zoom", "morph"}
    for name in normalized[:5]:
        t = slug(name)
        typ = t if t in allowed else "fade"
        transitions.setdefault(t, {"type": typ, "duration_ms": 350 if typ != "none" else 0, "easing": "ease-in-out"})
    for name in ["none", "fade", "push"]:
        transitions.setdefault(name, {"type": name, "duration_ms": 300 if name != "none" else 0, "easing": "ease-in-out"})
    return {
        "slide_grid": grid,
        "stage_spotlight": {"x": grid["page_width"] * 0.12, "y": grid["page_height"] * 0.16, "width": grid["page_width"] * 0.72, "height": grid["page_height"] * 0.56, "safe_zone_pct": 8},
        "type_on_stage": type_payload,
        "slide_color": {"background": palette[0], "background_alt": palette[1], "text_primary": palette[2], "text_secondary": palette[3], "accent": palette[4], "rule": palette[5]},
        "transition": transitions,
        "build_pacing": {"entry_delay_ms": 0, "stagger_ms": 120, "max_simultaneous_elements": 3, "rules": [{"selector": "title", "timing": "with_previous", "delay_ms": 0}, {"selector": "body", "timing": "after_previous", "delay_ms": 120}]},
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
