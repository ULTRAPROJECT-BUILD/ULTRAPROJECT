#!/usr/bin/env python3
"""Run semantic-layout adversarial checks for locked visual-spec mockups.

Production usage expects ``--vs-path`` to point at a visual-spec markdown file
with frontmatter ``mockups[].final_html`` / ``mockups[].final_png`` entries. For
Batch 7 smoke tests this script also accepts a direct HTML file as ``--vs-path``.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from statistics import median
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
MANIFEST_SCHEMA = REPO_ROOT / "schemas" / "visual-spec-manifest.schema.json"

LAYOUT_MEDIUMS = {"web_ui", "native_ui", "presentation", "document_typography", "game_ui", "data_visualization"}
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}
NOISE_FLOOR_PHASH_DISTANCE = 8
VIEWPORT_WIDTH = 1440.0
VIEWPORT_HEIGHT = 900.0

COMPONENT_PATTERNS = (
    "button",
    "card",
    "panel",
    "chip",
    "tab",
    "alert",
    "modal",
    "nav",
    "header",
    "footer",
    "list-item",
    "input",
    "link",
)
COMPONENT_TAGS = {
    "button": "button",
    "input": "input",
    "select": "select",
    "textarea": "input",
    "table": "table",
    "dialog": "modal",
    "details": "details",
    "nav": "nav",
    "header": "header",
    "footer": "footer",
    "a": "link",
}
TEXT_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6", "p", "span", "a", "button", "li", "td", "th", "label", "strong", "em"}
PANE_CLASS_RE = re.compile(r"(?:^|[-_])(pane|content|detail|list|main|sidebar|aside|region)(?:$|[-_])", re.I)
HEX_RE = re.compile(r"#(?:[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})\b")
RGB_RE = re.compile(r"rgba?\(([^)]+)\)", re.I)

NAMED_COLORS = {
    "black": "#000000",
    "white": "#ffffff",
    "transparent": "#00000000",
    "red": "#ff0000",
    "green": "#008000",
    "blue": "#0000ff",
    "gray": "#808080",
    "grey": "#808080",
}


class DependencyError(RuntimeError):
    """Raised when a required runtime dependency is missing."""


@dataclass
class CssRule:
    selectors: list[str]
    declarations: dict[str, str]
    order: int


@dataclass
class MockupAsset:
    html: Path | None
    png: Path | None
    screen: str
    metadata: dict[str, Any]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vs-path", required=True, help="Visual-spec markdown path, manifest JSON, or direct HTML mockup.")
    parser.add_argument("--references-dir", required=True, help="Visual references directory containing manifest/mockups.")
    parser.add_argument("--medium", required=True, help="Visual medium to evaluate.")
    parser.add_argument("--json-out", help="Optional path to write the JSON result.")
    return parser.parse_args()


def checked_at() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def write_json(data: dict[str, Any], json_out: str | None = None) -> None:
    text = json.dumps(data, indent=2, sort_keys=True) + "\n"
    sys.stdout.write(text)
    if json_out:
        out_path = Path(json_out).expanduser()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text, encoding="utf-8")


def split_frontmatter(text: str) -> tuple[str, str]:
    if not text.startswith("---\n"):
        return "", text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return "", text
    return parts[1].strip(), parts[2].lstrip("\n")


def load_yaml_map(text: str) -> dict[str, Any]:
    try:
        import yaml
    except ImportError as exc:
        raise DependencyError("check_semantic_layout.py requires PyYAML for VS frontmatter parsing.") from exc
    data = yaml.safe_load(text) if text.strip() else {}
    return data if isinstance(data, dict) else {}


def resolve_path(value: Any, *, vs_path: Path, references_dir: Path) -> Path | None:
    if not isinstance(value, str) or not value.strip():
        return None
    raw = Path(value).expanduser()
    if raw.is_absolute():
        return raw
    candidates = [
        REPO_ROOT / raw,
        references_dir / raw,
        vs_path.parent / raw,
        references_dir / raw.name,
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    return candidates[0].resolve()


def natural_key(path: Path) -> list[Any]:
    parts = re.split(r"(\d+)", path.name.lower())
    return [int(part) if part.isdigit() else part for part in parts]


def load_manifest_assets(references_dir: Path, vs_path: Path) -> list[MockupAsset]:
    manifest = references_dir / "manifest.json"
    if not manifest.exists():
        return []
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    assets = []
    for item in data.get("assets", []):
        if not isinstance(item, dict) or item.get("role") != "mockup":
            continue
        path = resolve_path(item.get("path"), vs_path=vs_path, references_dir=references_dir)
        if not path:
            continue
        assets.append(
            MockupAsset(
                html=path if path.suffix.lower() in {".html", ".htm"} else None,
                png=path if path.suffix.lower() in IMAGE_SUFFIXES else None,
                screen=str(item.get("screen") or path.stem),
                metadata=item,
            )
        )
    return assets


def load_vs(vs_path: Path, references_dir: Path) -> tuple[dict[str, Any], list[MockupAsset]]:
    resolved = vs_path.expanduser().resolve()
    if resolved.suffix.lower() in {".html", ".htm"}:
        return {}, [MockupAsset(html=resolved, png=None, screen=resolved.stem, metadata={"source": "direct_html"})]
    if resolved.suffix.lower() == ".json":
        data = json.loads(resolved.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}, load_manifest_assets(references_dir, resolved)

    text = resolved.read_text(encoding="utf-8")
    frontmatter_text, _ = split_frontmatter(text)
    frontmatter = load_yaml_map(frontmatter_text)
    mockups: list[MockupAsset] = []
    for item in frontmatter.get("mockups", []) if isinstance(frontmatter.get("mockups"), list) else []:
        if not isinstance(item, dict):
            continue
        html = resolve_path(item.get("final_html"), vs_path=resolved, references_dir=references_dir)
        png = resolve_path(item.get("final_png"), vs_path=resolved, references_dir=references_dir)
        mockups.append(
            MockupAsset(
                html=html if html and html.suffix.lower() in {".html", ".htm"} else None,
                png=png if png and png.suffix.lower() in IMAGE_SUFFIXES else None,
                screen=str(item.get("screen") or (html or png or resolved).stem),
                metadata=item,
            )
        )
    if not mockups:
        mockups = load_manifest_assets(references_dir, resolved)
    return frontmatter, mockups


def require_html_deps() -> tuple[Any, Any]:
    try:
        from bs4 import BeautifulSoup, NavigableString
    except ImportError as exc:
        raise DependencyError("check_semantic_layout.py requires beautifulsoup4. Install with: python3 -m pip install beautifulsoup4") from exc
    return BeautifulSoup, NavigableString


def parse_declarations(style_text: str) -> dict[str, str]:
    declarations: dict[str, str] = {}
    try:
        import tinycss2
    except ImportError:
        tinycss2 = None
    if tinycss2 is not None:
        for decl in tinycss2.parse_declaration_list(style_text, skip_comments=True, skip_whitespace=True):
            if getattr(decl, "type", None) == "declaration":
                declarations[decl.lower_name] = tinycss2.serialize(decl.value).strip()
        return declarations
    for name, value in re.findall(r"([A-Za-z-]+)\s*:\s*([^;]+)", style_text):
        declarations[name.strip().lower()] = value.strip()
    return declarations


def parse_css_rules(css_text: str) -> list[CssRule]:
    rules: list[CssRule] = []
    try:
        import cssutils  # type: ignore
    except ImportError:
        cssutils = None
    if cssutils is not None:
        sheet = cssutils.parseString(css_text)
        for rule in sheet:
            if getattr(rule, "type", None) != rule.STYLE_RULE:
                continue
            declarations = {prop.name.lower(): prop.value.strip() for prop in rule.style}
            selectors = [selector.selectorText.strip() for selector in rule.selectorList]
            rules.append(CssRule(selectors=selectors, declarations=declarations, order=len(rules)))
        return rules

    try:
        import tinycss2
    except ImportError:
        tinycss2 = None
    if tinycss2 is not None:
        parsed = tinycss2.parse_stylesheet(css_text, skip_comments=True, skip_whitespace=True)
        for rule in parsed:
            if getattr(rule, "type", None) != "qualified-rule":
                continue
            selectors = [s.strip() for s in tinycss2.serialize(rule.prelude).split(",") if s.strip()]
            declarations = parse_declarations(tinycss2.serialize(rule.content))
            rules.append(CssRule(selectors=selectors, declarations=declarations, order=len(rules)))
        return rules

    cleaned = re.sub(r"/\*.*?\*/", "", css_text, flags=re.S)
    for selector_text, body in re.findall(r"([^{}]+)\{([^{}]+)\}", cleaned):
        selectors = [s.strip() for s in selector_text.split(",") if s.strip()]
        rules.append(CssRule(selectors=selectors, declarations=parse_declarations(body), order=len(rules)))
    return rules


def selector_specificity(selector: str) -> tuple[int, int, int]:
    return (selector.count("#"), selector.count("."), 1 if re.match(r"^[A-Za-z][\w-]*", selector.strip()) else 0)


def matches_simple_selector(element: Any, token: str) -> bool:
    token = re.sub(r":[A-Za-z0-9_-]+(?:\([^)]*\))?", "", token.strip())
    if not token or token == "*":
        return True
    if "[" in token:
        token = token.split("[", 1)[0]
    tag_match = re.match(r"^[A-Za-z][\w-]*", token)
    tag = tag_match.group(0).lower() if tag_match else None
    if tag and getattr(element, "name", "").lower() != tag:
        return False
    for ident in re.findall(r"#([A-Za-z0-9_-]+)", token):
        if element.get("id") != ident:
            return False
    classes = set(element.get("class") or [])
    for cls in re.findall(r"\.([A-Za-z0-9_-]+)", token):
        if cls not in classes:
            return False
    return bool(tag or "#" in token or "." in token or token == "*")


def selector_matches(element: Any, selector: str) -> bool:
    selector = selector.strip()
    if not selector or any(part in selector for part in ("+", "~")):
        return False
    selector = selector.replace(">", " ")
    tokens = [token for token in selector.split() if token]
    if not tokens:
        return False
    if not matches_simple_selector(element, tokens[-1]):
        return False
    ancestor = element.parent
    for token in reversed(tokens[:-1]):
        found = False
        while ancestor is not None and getattr(ancestor, "name", None):
            if matches_simple_selector(ancestor, token):
                found = True
                ancestor = ancestor.parent
                break
            ancestor = ancestor.parent
        if not found:
            return False
    return True


def extract_css_text(soup: Any) -> str:
    style_blocks = [style.get_text("\n") for style in soup.find_all("style")]
    inline = [tag.get("style", "") for tag in soup.find_all(True) if tag.get("style")]
    return "\n".join(style_blocks + inline)


def normalize_color(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip().lower()
    if not text:
        return None
    if text in NAMED_COLORS:
        return NAMED_COLORS[text]
    hex_match = HEX_RE.search(text)
    if hex_match:
        raw = hex_match.group(0).lower()
        body = raw[1:]
        if len(body) in {3, 4}:
            expanded = "".join(ch * 2 for ch in body)
            body = expanded[:6]
        elif len(body) == 8:
            body = body[:6]
        return f"#{body}"
    rgb_match = RGB_RE.search(text)
    if rgb_match:
        nums = re.findall(r"[-+]?\d*\.?\d+", rgb_match.group(1))
        if len(nums) >= 3:
            channels = [max(0, min(255, int(float(num)))) for num in nums[:3]]
            return "#{:02x}{:02x}{:02x}".format(*channels)
    return None


def color_luminance(hex_color: str) -> float:
    color = normalize_color(hex_color) or "#000000"
    channels = [int(color[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast_ratio(foreground: str | None, background: str | None) -> float:
    fg = foreground or "#111111"
    bg = background or "#ffffff"
    lum_a = color_luminance(fg)
    lum_b = color_luminance(bg)
    light, dark = max(lum_a, lum_b), min(lum_a, lum_b)
    return (light + 0.05) / (dark + 0.05)


def to_px(value: Any, *, base: float = 16.0, axis: str = "x") -> float | None:
    if value is None:
        return None
    text = str(value).strip().lower()
    if not text or text in {"auto", "none", "normal"}:
        return None
    match = re.search(r"(-?\d+(?:\.\d+)?)\s*(px|pt|rem|em|vh|vw|%)?", text)
    if not match:
        return None
    number = float(match.group(1))
    unit = match.group(2) or "px"
    if unit == "px":
        return number
    if unit == "pt":
        return number * 96.0 / 72.0
    if unit in {"rem", "em"}:
        return number * base
    if unit == "vw":
        return VIEWPORT_WIDTH * number / 100.0
    if unit == "vh":
        return VIEWPORT_HEIGHT * number / 100.0
    if unit == "%":
        return (VIEWPORT_WIDTH if axis == "x" else VIEWPORT_HEIGHT) * number / 100.0
    return None


def parse_spacing(value: Any, *, font_size: float) -> tuple[float, float, float, float]:
    if value is None:
        return (0.0, 0.0, 0.0, 0.0)
    parts = str(value).split()
    px = [to_px(part, base=font_size) or 0.0 for part in parts[:4]]
    if len(px) == 1:
        return (px[0], px[0], px[0], px[0])
    if len(px) == 2:
        return (px[0], px[1], px[0], px[1])
    if len(px) == 3:
        return (px[0], px[1], px[2], px[1])
    if len(px) >= 4:
        return (px[0], px[1], px[2], px[3])
    return (0.0, 0.0, 0.0, 0.0)


def normalize_font_weight(value: Any) -> str:
    text = str(value or "400").strip().lower()
    if text == "normal":
        return "400"
    if text == "bold":
        return "700"
    match = re.search(r"\d+", text)
    return match.group(0) if match else "400"


def expand_font_shorthand(style: dict[str, str]) -> None:
    shorthand = style.get("font")
    if not shorthand:
        return
    size_match = re.search(r"(\d+(?:\.\d+)?(?:px|pt|rem|em))(?:\s*/\s*([0-9.]+(?:px|pt|rem|em)?))?", shorthand)
    if size_match and "font-size" not in style:
        style["font-size"] = size_match.group(1)
    if size_match and size_match.group(2) and "line-height" not in style:
        style["line-height"] = size_match.group(2)
    if "font-weight" not in style:
        weight_match = re.search(r"\b([1-9]00|bold|normal)\b", shorthand)
        if weight_match:
            style["font-weight"] = weight_match.group(1)
    if size_match and "font-family" not in style:
        family = shorthand[size_match.end() :].strip()
        if family:
            style["font-family"] = family


def compute_styles(soup: Any, rules: list[CssRule]) -> dict[int, dict[str, str]]:
    inherited = {"color", "font-family", "font-size", "font-weight", "line-height"}
    defaults = {
        "color": "#111111",
        "font-family": "system-ui",
        "font-size": "16px",
        "font-weight": "400",
        "line-height": "1.4",
        "background-color": "#ffffff",
    }
    style_by_id: dict[int, dict[str, str]] = {}
    ordered_rules = sorted(
        rules,
        key=lambda rule: (max((selector_specificity(s) for s in rule.selectors), default=(0, 0, 0)), rule.order),
    )

    def walk(element: Any, parent_style: dict[str, str]) -> None:
        style = {key: parent_style[key] for key in inherited if key in parent_style}
        if getattr(element, "name", "").lower() in {"html", "body"}:
            style.update(defaults)
        for rule in ordered_rules:
            if any(selector_matches(element, selector) for selector in rule.selectors):
                style.update(rule.declarations)
        if element.get("style"):
            style.update(parse_declarations(element.get("style")))
        expand_font_shorthand(style)
        style_by_id[id(element)] = style
        for child in element.find_all(recursive=False):
            walk(child, style)

    root = soup.find("html") or soup
    walk(root, defaults)
    return style_by_id


def nearest_background(element: Any, styles: dict[int, dict[str, str]]) -> str:
    current = element
    while current is not None and getattr(current, "name", None):
        style = styles.get(id(current), {})
        color = normalize_color(style.get("background-color") or style.get("background"))
        if color and not color.endswith("00"):
            return color
        current = current.parent
    return "#ffffff"


def direct_text(element: Any) -> str:
    return " ".join(str(child).strip() for child in element.children if isinstance(child, str) and str(child).strip())


def visible_text(element: Any) -> str:
    if element.name == "input":
        return str(element.get("value") or element.get("placeholder") or "")
    own = direct_text(element)
    if own:
        return own
    if element.name in {"button", "a", "li", "td", "th"}:
        return element.get_text(" ", strip=True)
    return ""


def is_visible(element: Any, styles: dict[int, dict[str, str]]) -> bool:
    if element.name in {"script", "style", "head", "meta", "link", "title"}:
        return False
    if element.get("hidden") is not None or element.get("aria-hidden") == "true":
        return False
    style = styles.get(id(element), {})
    return style.get("display") != "none" and style.get("visibility") != "hidden"


def font_size_px(element: Any, styles: dict[int, dict[str, str]]) -> float:
    style = styles.get(id(element), {})
    parent_size = 16.0
    return to_px(style.get("font-size"), base=parent_size, axis="y") or 16.0


def text_area(element: Any, styles: dict[int, dict[str, str]]) -> float:
    style = styles.get(id(element), {})
    size = font_size_px(element, styles)
    text = visible_text(element)
    padding = parse_spacing(style.get("padding"), font_size=size)
    padding_top = to_px(style.get("padding-top"), base=size, axis="y")
    padding_right = to_px(style.get("padding-right"), base=size, axis="x")
    padding_bottom = to_px(style.get("padding-bottom"), base=size, axis="y")
    padding_left = to_px(style.get("padding-left"), base=size, axis="x")
    top, right, bottom, left = padding
    top = padding_top if padding_top is not None else top
    right = padding_right if padding_right is not None else right
    bottom = padding_bottom if padding_bottom is not None else bottom
    left = padding_left if padding_left is not None else left
    width = to_px(style.get("width"), base=size, axis="x")
    height = to_px(style.get("height"), base=size, axis="y")
    if width is None:
        width = max(size * max(len(text), 1) * 0.56 + left + right, size * 2)
    if height is None:
        line_height_raw = style.get("line-height")
        line_height = to_px(line_height_raw, base=size, axis="y") if line_height_raw else None
        if line_height is None:
            try:
                line_height = size * float(line_height_raw) if line_height_raw else size * 1.35
            except (TypeError, ValueError):
                line_height = size * 1.35
        height = line_height + top + bottom
    return max(width * height, 1.0)


def parse_grid_columns(value: Any, parent_width: float = VIEWPORT_WIDTH) -> list[float]:
    if not value:
        return []
    tracks = str(value).replace(",", " ").split()
    fixed_total = 0.0
    fr_total = 0.0
    parsed: list[tuple[str, float]] = []
    for track in tracks:
        if track.endswith("fr"):
            amount = float(track[:-2] or 1)
            fr_total += amount
            parsed.append(("fr", amount))
        else:
            px = to_px(track, axis="x")
            if px is None:
                px = parent_width / max(len(tracks), 1)
            fixed_total += px
            parsed.append(("px", px))
    remaining = max(parent_width - fixed_total, parent_width * 0.1)
    return [value if kind == "px" else remaining * value / max(fr_total, 1.0) for kind, value in parsed]


def element_area(element: Any, styles: dict[int, dict[str, str]]) -> float:
    style = styles.get(id(element), {})
    size = font_size_px(element, styles)
    width = to_px(style.get("width"), base=size, axis="x")
    height = to_px(style.get("height"), base=size, axis="y")
    parent = element.parent
    if (width is None or height is None) and parent is not None and getattr(parent, "name", None):
        parent_style = styles.get(id(parent), {})
        parent_display = str(parent_style.get("display", "")).lower()
        if "grid" in parent_display:
            siblings = [child for child in parent.find_all(recursive=False) if getattr(child, "name", None)]
            index = siblings.index(element) if element in siblings else 0
            columns = parse_grid_columns(parent_style.get("grid-template-columns"))
            if columns:
                width = columns[index % len(columns)]
                height = height or to_px(parent_style.get("height"), axis="y") or VIEWPORT_HEIGHT
        elif "flex" in parent_display:
            siblings = [child for child in parent.find_all(recursive=False) if getattr(child, "name", None)]
            width = width or VIEWPORT_WIDTH / max(len(siblings), 1)
            height = height or to_px(parent_style.get("height"), axis="y") or VIEWPORT_HEIGHT
    if width is None or height is None:
        return text_area(element, styles)
    return max(width * height, 1.0)


def text_candidates(soup: Any, styles: dict[int, dict[str, str]]) -> list[Any]:
    candidates = []
    for element in soup.find_all(True):
        if not is_visible(element, styles):
            continue
        if element.name in TEXT_TAGS or direct_text(element) or element.name in {"input", "select", "textarea"}:
            if visible_text(element) or element.name in {"input", "select", "textarea"}:
                candidates.append(element)
    return candidates


def check_equal_weight_grid(html_docs: list[tuple[Any, dict[int, dict[str, str]], str]]) -> dict[str, Any]:
    offenders = []
    for soup, styles, source in html_docs:
        for parent in soup.find_all(True):
            parent_style = styles.get(id(parent), {})
            display = str(parent_style.get("display", "")).lower()
            if "grid" not in display and "flex" not in display:
                continue
            children = [child for child in parent.find_all(recursive=False) if getattr(child, "name", None) and is_visible(child, styles)]
            groups: dict[tuple[Any, ...], list[Any]] = {}
            for child in children:
                style = styles.get(id(child), {})
                classes = tuple(sorted(child.get("class") or []))
                class_key = classes[:2] if classes else ("no-class",)
                key = (
                    child.name,
                    class_key,
                    round(font_size_px(child, styles), 1),
                    normalize_color(style.get("background-color") or style.get("background")),
                    normalize_color(style.get("color")),
                )
                groups.setdefault(key, []).append(child)
            for key, group in groups.items():
                if len(group) < 4:
                    continue
                areas = [element_area(child, styles) for child in group]
                avg = sum(areas) / len(areas)
                within = all(abs(area - avg) / max(avg, 1.0) <= 0.10 for area in areas)
                fallback_same_class = key[1] != ("no-class",)
                if within or fallback_same_class:
                    offenders.append(
                        {
                            "source": source,
                            "parent": parent.name,
                            "display": display,
                            "sibling_count": len(group),
                            "tag": key[0],
                            "class_signature": list(key[1]),
                            "area_avg": round(avg, 2),
                            "area_within_10_pct": within,
                        }
                    )
    verdict = "fail" if offenders else "pass"
    return {
        "verdict": verdict,
        "details": "Detected equal-weight sibling groups in grid/flex layout." if offenders else "No equal-weight grid sibling group detected.",
        "offenders": offenders,
    }


def check_hierarchy_contrast(html_docs: list[tuple[Any, dict[int, dict[str, str]], str]]) -> dict[str, Any]:
    weights = []
    for soup, styles, source in html_docs:
        candidates = text_candidates(soup, styles)
        total = max(len(candidates) - 1, 1)
        for index, element in enumerate(candidates):
            style = styles.get(id(element), {})
            top_factor = 1.5 if (index / total) <= 0.30 else 1.0
            foreground = normalize_color(style.get("color")) or "#111111"
            background = nearest_background(element, styles)
            weight = font_size_px(element, styles) * text_area(element, styles) * contrast_ratio(foreground, background) * top_factor
            weights.append({"source": source, "tag": element.name, "text": visible_text(element)[:80], "weight": weight})
    if not weights:
        return {"verdict": "fail", "details": "No visible text candidates found.", "max_weight": 0, "median_weight": 0, "ratio": 0}
    values = [item["weight"] for item in weights]
    max_weight = max(values)
    median_weight = median(values)
    ratio = max_weight / max(median_weight, 1.0)
    return {
        "verdict": "pass" if ratio >= 1.8 else "fail",
        "max_weight": round(max_weight, 2),
        "median_weight": round(median_weight, 2),
        "ratio": round(ratio, 3),
        "details": "Hierarchy contrast meets minimum ratio." if ratio >= 1.8 else "Visible elements have a flat weight distribution.",
        "top_weighted_elements": sorted(weights, key=lambda item: item["weight"], reverse=True)[:5],
    }


def normalize_topology(value: Any) -> str:
    return str(value or "").strip().lower().replace("-", "_")


def check_pane_dominance(
    html_docs: list[tuple[Any, dict[int, dict[str, str]], str]],
    frontmatter: dict[str, Any],
) -> dict[str, Any]:
    topology = normalize_topology((frontmatter.get("visual_axes") or {}).get("topology"))
    if topology not in {"list_detail", "multi_region"}:
        return {"verdict": "not_applicable", "details": "Pane dominance only applies to list-detail or multi-region topology.", "topology": topology or None}
    panes = []
    for soup, styles, source in html_docs:
        for element in soup.find_all(True):
            classes = " ".join(element.get("class") or [])
            if element.name in {"main", "section", "aside"} or PANE_CLASS_RE.search(classes):
                panes.append({"source": source, "tag": element.name, "classes": classes, "area": element_area(element, styles)})
    if len(panes) < 2:
        return {"verdict": "fail", "details": "Topology requires dominant panes, but fewer than two panes were detected.", "pane_count": len(panes)}
    sorted_panes = sorted(panes, key=lambda pane: pane["area"], reverse=True)
    largest = sorted_panes[0]["area"]
    second = sorted_panes[1]["area"]
    ratio = largest / max(second, 1.0)
    return {
        "verdict": "pass" if ratio >= 1.5 else "fail",
        "largest_area": round(largest, 2),
        "second_largest": round(second, 2),
        "ratio": round(ratio, 3),
        "details": "Primary pane dominates secondary pane." if ratio >= 1.5 else "Primary panes are too equal in visual weight.",
        "panes": sorted_panes[:6],
    }


def class_matches_component(class_name: str) -> str | None:
    normalized = class_name.lower().replace("_", "-")
    for pattern in COMPONENT_PATTERNS:
        if normalized == pattern or normalized.startswith(f"{pattern}-") or normalized.endswith(f"-{pattern}") or f"-{pattern}-" in normalized:
            return pattern
    return None


def check_component_role_mix(html_docs: list[tuple[Any, dict[int, dict[str, str]], str]]) -> dict[str, Any]:
    roles: set[str] = set()
    for soup, styles, _source in html_docs:
        for element in soup.find_all(True):
            if not is_visible(element, styles):
                continue
            tag_role = COMPONENT_TAGS.get(element.name)
            if tag_role:
                roles.add(tag_role)
            for cls in element.get("class") or []:
                role = class_matches_component(cls)
                if role:
                    roles.add(role)
    return {
        "verdict": "pass" if len(roles) >= 4 else "fail",
        "component_role_count": len(roles),
        "component_roles": sorted(roles),
        "details": "Component role mix meets minimum diversity." if len(roles) >= 4 else "Fewer than four distinct component roles detected.",
    }


def extract_color_tokens(css_text: str) -> set[str]:
    colors = set()
    for raw in HEX_RE.findall(css_text):
        color = normalize_color(raw)
        if color and not color.endswith("00"):
            colors.add(color)
    for raw in RGB_RE.findall(css_text):
        color = normalize_color(f"rgb({raw})")
        if color:
            colors.add(color)
    for name in NAMED_COLORS:
        if re.search(rf"\b{name}\b", css_text, re.I):
            color = normalize_color(name)
            if color and not color.endswith("00"):
                colors.add(color)
    return colors


def check_visible_token_instances(html_docs: list[tuple[Any, dict[int, dict[str, str]], str]], css_texts: list[str]) -> dict[str, Any]:
    colors: set[str] = set()
    type_styles: set[tuple[str, str, str]] = set()
    for css_text in css_texts:
        colors.update(extract_color_tokens(css_text))
    for soup, styles, _source in html_docs:
        for element in text_candidates(soup, styles):
            style = styles.get(id(element), {})
            family = str(style.get("font-family") or "system-ui").strip()
            size = f"{round(font_size_px(element, styles), 2)}px"
            weight = normalize_font_weight(style.get("font-weight"))
            type_styles.add((family, size, weight))
    verdict = "pass" if len(colors) >= 8 and len(type_styles) >= 4 else "fail"
    return {
        "verdict": verdict,
        "color_token_count": len(colors),
        "type_style_count": len(type_styles),
        "colors": sorted(colors),
        "type_styles": [" | ".join(style) for style in sorted(type_styles)],
        "details": "Visible color and type token diversity meets thresholds." if verdict == "pass" else "Color or type token diversity is below threshold.",
    }


def check_density_target(
    html_docs: list[tuple[Any, dict[int, dict[str, str]], str]],
    frontmatter: dict[str, Any],
) -> dict[str, Any]:
    density = str((frontmatter.get("visual_axes") or {}).get("density") or "").strip().lower()
    if density not in {"dense", "ultra_dense"}:
        return {"verdict": "not_applicable", "details": "Density target is not dense.", "density": density or None}
    parity = frontmatter.get("parity_targets") if isinstance(frontmatter.get("parity_targets"), dict) else {}
    target = parity.get("density_rows_visible_at_800pt")
    if target is None:
        return {"verdict": "not_applicable", "details": "No parity_targets.density_rows_visible_at_800pt value declared.", "density": density}
    observed = []
    for soup, _styles, source in html_docs:
        count = len(soup.find_all("tr")) + len(soup.find_all("li"))
        observed.append({"source": source, "rows": count})
    max_observed = max((item["rows"] for item in observed), default=0)
    return {
        "verdict": "pass" if max_observed >= int(target) else "fail",
        "density": density,
        "target_rows_visible_at_800pt": int(target),
        "observed_max_rows": max_observed,
        "observed": observed,
        "details": "Dense mockup row count meets target." if max_observed >= int(target) else "Dense target is claimed but observed row count is below target.",
    }


def check_brand_context_diversity(mockups: list[MockupAsset], references_dir: Path) -> dict[str, Any]:
    context_keywords = {
        "white_bg": ("white", "light"),
        "dark_bg": ("dark", "black"),
        "photo_bg": ("photo", "image"),
        "signage": ("signage", "sign"),
        "packaging": ("packaging", "package", "box"),
        "web_header": ("web-header", "web_header", "header"),
        "social": ("social", "instagram", "linkedin", "x-post", "twitter"),
    }
    names = [asset.screen for asset in mockups]
    names.extend(path.stem for path in references_dir.rglob("*") if path.suffix.lower() in IMAGE_SUFFIXES)
    contexts: set[str] = set()
    for asset in mockups:
        for key in ("context", "application_context", "background", "surface"):
            if asset.metadata.get(key):
                contexts.add(str(asset.metadata[key]).strip().lower())
    for name in names:
        lowered = name.lower()
        for context, needles in context_keywords.items():
            if any(needle in lowered for needle in needles):
                contexts.add(context)
    return {
        "verdict": "pass" if len(contexts) >= 5 else "fail",
        "context_count": len(contexts),
        "contexts": sorted(contexts),
        "details": "Brand identity is shown across enough application contexts." if len(contexts) >= 5 else "Brand identity lacks application-context diversity.",
    }


def collect_image_paths(mockups: list[MockupAsset], references_dir: Path) -> list[Path]:
    paths = [asset.png for asset in mockups if asset.png and asset.png.exists()]
    if not paths and references_dir.exists():
        paths = [path for path in references_dir.rglob("*") if path.suffix.lower() in IMAGE_SUFFIXES]
    unique = {path.resolve(): path.resolve() for path in paths}
    return sorted(unique.values(), key=natural_key)


def check_video_frame_change(mockups: list[MockupAsset], references_dir: Path) -> dict[str, Any]:
    try:
        from compute_phash import compute_phash, compute_phash_distance
    except ImportError as exc:
        raise DependencyError("check_semantic_layout.py could not import scripts/compute_phash.py.") from exc
    frames = collect_image_paths(mockups, references_dir)
    if len(frames) < 2:
        return {"verdict": "fail", "details": "Video frame-change check requires at least two frame PNGs.", "frame_count": len(frames)}
    hashes = [compute_phash(path) for path in frames]
    pairs = []
    failures = []
    for previous, current in zip(hashes, hashes[1:]):
        distance = compute_phash_distance(previous["phash"], current["phash"])
        item = {"frame_a": previous["path"], "frame_b": current["path"], "phash_distance": distance}
        pairs.append(item)
        if distance < NOISE_FLOOR_PHASH_DISTANCE:
            failures.append(item)
    return {
        "verdict": "fail" if failures else "pass",
        "frame_count": len(frames),
        "noise_floor": NOISE_FLOOR_PHASH_DISTANCE,
        "pairs": pairs,
        "details": "Consecutive frames change beyond the pHash noise floor." if not failures else "One or more consecutive frame pairs are effectively static.",
    }


def count_light_sources(image_path: Path) -> dict[str, Any]:
    try:
        import numpy as np
        from PIL import Image
    except ImportError as exc:
        raise DependencyError("check_semantic_layout.py requires Pillow and numpy for 3D render checks.") from exc

    with Image.open(image_path) as image:
        gray = image.convert("L").resize((64, 64))
    arr = np.asarray(gray, dtype=np.float32)
    mean = float(arr.mean())
    threshold = min(255.0, mean * 1.5)
    histogram, _bins = np.histogram(arr, bins=16, range=(0, 255))
    candidates = []
    h, w = arr.shape
    for y in range(1, h - 1):
        for x in range(1, w - 1):
            value = arr[y, x]
            if value < threshold:
                continue
            window = arr[y - 1 : y + 2, x - 1 : x + 2]
            if value >= float(window.max()):
                candidates.append((float(value), x, y))
    selected: list[tuple[float, int, int]] = []
    min_sep = w / 4.0
    for value, x, y in sorted(candidates, reverse=True):
        if all(math.hypot(x - sx, y - sy) >= min_sep for _sv, sx, sy in selected):
            selected.append((value, x, y))
    return {
        "path": str(image_path),
        "mean_brightness": round(mean, 2),
        "threshold": round(threshold, 2),
        "histogram": [int(v) for v in histogram.tolist()],
        "light_source_count": len(selected),
        "light_sources": [{"brightness": round(v, 2), "x": x, "y": y} for v, x, y in selected[:8]],
    }


def check_3d_lighting(mockups: list[MockupAsset], references_dir: Path) -> dict[str, Any]:
    images = collect_image_paths(mockups, references_dir)
    if not images:
        return {"verdict": "fail", "details": "No render PNGs found for 3D lighting-source check.", "renders": []}
    renders = [count_light_sources(path) for path in images]
    failures = [render for render in renders if render["light_source_count"] < 3]
    return {
        "verdict": "fail" if failures else "pass",
        "renders": renders,
        "details": "All renders expose at least three distinct bright light-source regions." if not failures else "One or more renders expose fewer than three distinct light-source regions.",
    }


def load_html_docs(mockups: list[MockupAsset]) -> tuple[list[tuple[Any, dict[int, dict[str, str]], str]], list[str]]:
    BeautifulSoup, _NavigableString = require_html_deps()
    docs = []
    css_texts = []
    for asset in mockups:
        if not asset.html or not asset.html.exists():
            continue
        text = asset.html.read_text(encoding="utf-8")
        soup = BeautifulSoup(text, "html.parser")
        css_text = extract_css_text(soup)
        css_texts.append(css_text)
        rules = parse_css_rules(css_text)
        styles = compute_styles(soup, rules)
        docs.append((soup, styles, str(asset.html)))
    return docs, css_texts


def validation_for_manifest_block(block_name: str, block: dict[str, Any]) -> dict[str, Any]:
    try:
        import jsonschema
    except ImportError:
        return {"valid": False, "errors": ["jsonschema is not installed."]}
    try:
        schema = json.loads(MANIFEST_SCHEMA.read_text(encoding="utf-8"))
        validator = jsonschema.Draft202012Validator(schema).evolve(schema=schema["properties"][block_name])
        errors = sorted(validator.iter_errors(block), key=lambda error: list(error.path))
    except Exception as exc:  # pragma: no cover - defensive schema loader path
        return {"valid": False, "errors": [str(exc)]}
    return {
        "valid": not errors,
        "errors": [
            {"path": "/" + "/".join(str(part) for part in error.path), "message": error.message}
            for error in errors
        ],
    }


def semantic_manifest_block(checks: dict[str, dict[str, Any]]) -> dict[str, Any]:
    failures = [f"{name}: {data.get('details', data.get('verdict'))}" for name, data in checks.items() if data.get("verdict") == "fail"]
    return {
        "pass": not failures,
        "checks": [name for name, data in checks.items() if data.get("verdict") != "not_applicable"],
        "failures": failures,
    }


def build_not_applicable(reason: str) -> dict[str, Any]:
    return {"verdict": "not_applicable", "details": reason}


def run(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    vs_path = Path(args.vs_path)
    references_dir = Path(args.references_dir).expanduser().resolve()
    frontmatter, mockups = load_vs(vs_path, references_dir)
    medium = args.medium
    checks: dict[str, dict[str, Any]] = {}
    applicable: list[int] = []
    html_docs: list[tuple[Any, dict[int, dict[str, str]], str]] = []
    css_texts: list[str] = []

    if medium in LAYOUT_MEDIUMS:
        applicable.extend([35, 36, 37, 38, 39, 40])
        html_docs, css_texts = load_html_docs(mockups)
        if medium == "web_ui" and html_docs:
            checks["35_equal_weight_grid"] = check_equal_weight_grid(html_docs)
        elif medium == "web_ui":
            checks["35_equal_weight_grid"] = {"verdict": "fail", "details": "No locked HTML mockups found for web_ui equal-weight grid check."}
        else:
            checks["35_equal_weight_grid"] = build_not_applicable("Equal-weight grid detection is implemented for web_ui HTML; this medium needs its plugin batch.")

        if html_docs:
            checks["36_hierarchy_contrast"] = check_hierarchy_contrast(html_docs)
            checks["37_pane_dominance"] = check_pane_dominance(html_docs, frontmatter)
            checks["38_component_role_mix"] = check_component_role_mix(html_docs)
            checks["39_visible_token_instances"] = check_visible_token_instances(html_docs, css_texts)
            checks["40_density_target"] = check_density_target(html_docs, frontmatter)
        else:
            for name in (
                "36_hierarchy_contrast",
                "37_pane_dominance",
                "38_component_role_mix",
                "39_visible_token_instances",
                "40_density_target",
            ):
                checks[name] = build_not_applicable("No parseable locked HTML mockups found.")

    if medium == "brand_identity":
        applicable.append(41)
        checks["41_brand_identity_application_diversity"] = check_brand_context_diversity(mockups, references_dir)
    if medium == "video_animation":
        applicable.append(42)
        checks["42_video_sequential_frame_change"] = check_video_frame_change(mockups, references_dir)
    if medium == "3d_render":
        applicable.append(43)
        checks["43_3d_lighting_source_detection"] = check_3d_lighting(mockups, references_dir)

    block = semantic_manifest_block(checks)
    validation = validation_for_manifest_block("semantic_layout_validation", block)
    all_passed = not any(check.get("verdict") == "fail" for check in checks.values()) and validation["valid"]
    result = {
        "vs_path": str(Path(args.vs_path).expanduser().resolve()),
        "medium": medium,
        "checked_at": checked_at(),
        "applicable_checks": applicable,
        "checks": checks,
        "semantic_layout_validation": block,
        "schema_validation": validation,
        "all_passed": all_passed,
        "verdict": "pass" if all_passed else "fail",
    }
    return (0 if all_passed else 1), result


def main() -> int:
    args = parse_args()
    try:
        code, data = run(args)
    except DependencyError as exc:
        data = {"error": str(exc), "verdict": "error"}
        write_json(data, args.json_out)
        print(str(exc), file=sys.stderr)
        return 2
    except Exception as exc:
        data = {"error": str(exc), "verdict": "error"}
        write_json(data, args.json_out)
        return 1
    write_json(data, args.json_out)
    return code


if __name__ == "__main__":
    sys.exit(main())
