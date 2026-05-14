#!/usr/bin/env python3
"""Extract document_typography tokens from CSS Paged Media or LaTeX preambles."""

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


def extract_tokens(mockup: Path) -> dict[str, Any]:
    inputs = load_inputs(mockup)
    text = "\n".join(data for _, data, kind in inputs if isinstance(data, str))
    colors = colors_from_any(text)
    sizes = [float(m.group(1)) for m in re.finditer(r"font-size\s*:\s*([0-9.]+)", text, re.I)]
    sizes.extend(float(m.group(1)) for m in re.finditer(r"\\(?:Huge|huge|LARGE|Large|large|normalsize|small).*?([0-9.]+)pt", text))
    if not sizes:
        sizes = [10, 12, 14, 18, 24, 36]
    sizes = sorted(set(sizes), reverse=True)
    for fallback in [36, 24, 18, 14, 12, 10]:
        if len(sizes) >= 6:
            break
        if fallback not in sizes:
            sizes.append(fallback)
    names = ["display", "h1", "h2", "body", "caption", "footnote"]
    type_scale: dict[str, Any] = {}
    for idx, size in enumerate(sizes[:6]):
        type_scale[names[idx] if idx < len(names) else f"style_{idx+1}"] = {"family": "serif" if "serif" in text.lower() else "system", "size": size, "weight": "regular", "leading": round(size * 1.28, 2), "tracking": 0}
    page_width = first_number(re.search(r"size\s*:\s*([0-9.]+)", text, re.I).group(1) if re.search(r"size\s*:\s*([0-9.]+)", text, re.I) else None, default=612)
    page_height = 792
    geom = re.search(r"\\usepackage\[(.*?)\]\{geometry\}", text, re.S)
    margins = {"top": 72, "right": 72, "bottom": 72, "left": 72}
    if geom:
        opts = geom.group(1)
        for key in ["top", "right", "bottom", "left"]:
            m = re.search(key + r"\s*=\s*([0-9.]+)", opts)
            if m:
                margins[key] = float(m.group(1))
    css_margin = re.search(r"margin\s*:\s*([0-9.]+)", text, re.I)
    if css_margin:
        value = float(css_margin.group(1))
        margins = {"top": value, "right": value, "bottom": value, "left": value}
    palette = list(dict.fromkeys(colors + ["#FFFFFF", "#111111", "#0066FF", "#D8DCE2"]))
    return {
        "type_scale": type_scale,
        "page_grid": {"page_width": page_width, "page_height": page_height, "columns": 12, "gutter": 18},
        "margin_system": margins,
        "leading_rules": {"body_ratio": 1.35, "heading_ratio": 1.12},
        "widow_orphan_rules": {"widow_lines": 2, "orphan_lines": 2},
        "chart_styling": {"palette": palette[:6], "gridline_color": palette[-1]},
        "color_narrative": {"background": palette[0], "text": palette[1], "accent": palette[2]},
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
