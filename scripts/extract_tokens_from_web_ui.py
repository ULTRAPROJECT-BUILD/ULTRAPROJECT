#!/usr/bin/env python3
"""Extract web_ui design tokens from locked HTML/CSS mockups."""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

try:
    import tinycss2
except ImportError as exc:  # pragma: no cover - exercised only in missing envs
    raise SystemExit("tinycss2 is required. Install with: python3 -m pip install tinycss2") from exc

try:
    from bs4 import BeautifulSoup
except ImportError as exc:  # pragma: no cover - exercised only in missing envs
    raise SystemExit("beautifulsoup4 is required to parse HTML mockups.") from exc

NAMED_COLORS = {
    "black": "#000000",
    "silver": "#C0C0C0",
    "gray": "#808080",
    "grey": "#808080",
    "white": "#FFFFFF",
    "maroon": "#800000",
    "red": "#FF0000",
    "purple": "#800080",
    "fuchsia": "#FF00FF",
    "magenta": "#FF00FF",
    "green": "#008000",
    "lime": "#00FF00",
    "olive": "#808000",
    "yellow": "#FFFF00",
    "navy": "#000080",
    "blue": "#0000FF",
    "teal": "#008080",
    "aqua": "#00FFFF",
    "cyan": "#00FFFF",
    "orange": "#FFA500",
    "brown": "#A52A2A",
    "pink": "#FFC0CB",
    "gold": "#FFD700",
    "transparent": None,
    "currentcolor": None,
}

COLOR_PROPS = {
    "color",
    "background",
    "background-color",
    "border",
    "border-color",
    "border-top-color",
    "border-right-color",
    "border-bottom-color",
    "border-left-color",
    "outline",
    "outline-color",
    "box-shadow",
    "text-shadow",
    "fill",
    "stroke",
}

SPACING_PROPS = {
    "padding",
    "padding-top",
    "padding-right",
    "padding-bottom",
    "padding-left",
    "margin",
    "margin-top",
    "margin-right",
    "margin-bottom",
    "margin-left",
    "gap",
    "row-gap",
    "column-gap",
    "inset",
    "top",
    "right",
    "bottom",
    "left",
}

RADIUS_PROPS = {
    "border-radius",
    "border-top-left-radius",
    "border-top-right-radius",
    "border-bottom-left-radius",
    "border-bottom-right-radius",
}

TYPE_PROPS = {"font", "font-family", "font-size", "font-weight", "line-height", "letter-spacing"}
MOTION_PROPS = {"transition", "transition-duration", "transition-timing-function", "animation", "animation-duration", "animation-timing-function"}


@dataclass(frozen=True)
class Declaration:
    selector: str
    property: str
    value: str
    source: str


@dataclass(frozen=True)
class ColorOccurrence:
    value: str
    alpha: float
    selector: str
    property: str
    raw_value: str
    source: str

    @property
    def context(self) -> str:
        return f"{self.selector} {self.property} {self.raw_value}".lower()


def warn(message: str) -> None:
    print(f"warning: {message}", file=sys.stderr)


def serialize(tokens: Any) -> str:
    return tinycss2.serialize(tokens).strip()


def read_mockup(mockup_path: Path) -> tuple[str, BeautifulSoup]:
    html = mockup_path.read_text(encoding="utf-8")
    return html, BeautifulSoup(html, "html.parser")


def linked_stylesheet_path(html_path: Path, href: str) -> Path | None:
    parsed = urlparse(href)
    if parsed.scheme in {"http", "https"}:
        warn(f"skipping remote stylesheet {href!r}; mockups should be self-contained")
        return None
    local = parsed.path or href
    if not local:
        return None
    return (html_path.parent / local).resolve()


def selector_for_element(element: Any) -> str:
    tag = element.name or "element"
    element_id = element.get("id")
    classes = element.get("class") or []
    if element_id:
        return f"{tag}#{element_id}"
    if classes:
        return tag + "".join(f".{name}" for name in classes)
    return f"{tag}[style]"


def parse_declaration_list(css_text: str, selector: str, source: str) -> list[Declaration]:
    declarations: list[Declaration] = []
    for item in tinycss2.parse_declaration_list(css_text, skip_comments=True, skip_whitespace=True):
        if item.type != "declaration":
            continue
        declarations.append(Declaration(selector, item.name.lower(), serialize(item.value), source))
    return declarations


def parse_rules(rules: list[Any], source: str, context: str = "") -> list[Declaration]:
    declarations: list[Declaration] = []
    for rule in rules:
        if rule.type == "qualified-rule":
            selector = serialize(rule.prelude)
            if context:
                selector = f"{context} {selector}".strip()
            declarations.extend(parse_declaration_list(rule.content, selector, source))
        elif rule.type == "at-rule" and rule.content:
            at_name = f"@{rule.lower_at_keyword}"
            if rule.lower_at_keyword == "font-face":
                declarations.extend(parse_declaration_list(rule.content, at_name, source))
            else:
                nested = tinycss2.parse_rule_list(rule.content, skip_comments=True, skip_whitespace=True)
                if nested:
                    prelude = serialize(rule.prelude)
                    next_context = f"{context} {at_name} {prelude}".strip()
                    declarations.extend(parse_rules(nested, source, next_context))
    return declarations


def extract_declarations(mockup_path: Path, soup: BeautifulSoup) -> list[Declaration]:
    declarations: list[Declaration] = []
    for index, style in enumerate(soup.find_all("style"), start=1):
        css_text = style.get_text("\n")
        rules = tinycss2.parse_stylesheet(css_text, skip_comments=True, skip_whitespace=True)
        declarations.extend(parse_rules(rules, f"{mockup_path.name}::<style {index}>"))

    for link in soup.find_all("link"):
        rel = link.get("rel") or []
        rel_values = rel if isinstance(rel, list) else [rel]
        if "stylesheet" not in {str(value).lower() for value in rel_values}:
            continue
        href = link.get("href")
        if not href:
            continue
        css_path = linked_stylesheet_path(mockup_path, href)
        if not css_path:
            continue
        try:
            css_text = css_path.read_text(encoding="utf-8")
        except OSError as exc:
            warn(f"could not read linked stylesheet {href!r}: {exc}")
            continue
        rules = tinycss2.parse_stylesheet(css_text, skip_comments=True, skip_whitespace=True)
        declarations.extend(parse_rules(rules, str(css_path)))

    for element in soup.find_all(style=True):
        declarations.extend(parse_declaration_list(element.get("style", ""), selector_for_element(element), f"{mockup_path.name}::style-attribute"))
    return declarations


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def hex_to_rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


def rgb_to_hex(red: float, green: float, blue: float) -> str:
    return f"#{int(round(clamp(red, 0, 255))):02X}{int(round(clamp(green, 0, 255))):02X}{int(round(clamp(blue, 0, 255))):02X}"


def canonical_hash(value: str) -> tuple[str, float] | None:
    raw = value.strip().lstrip("#")
    if not re.fullmatch(r"[0-9A-Fa-f]{3,8}", raw):
        return None
    alpha = 1.0
    if len(raw) == 3:
        rgb = "".join(ch * 2 for ch in raw)
    elif len(raw) == 4:
        rgb = "".join(ch * 2 for ch in raw[:3])
        alpha = int(raw[3] * 2, 16) / 255
    elif len(raw) == 6:
        rgb = raw
    elif len(raw) == 8:
        rgb = raw[:6]
        alpha = int(raw[6:8], 16) / 255
    else:
        return None
    return f"#{rgb.upper()}", alpha


def parse_numeric_parts(text: str) -> list[str]:
    return re.findall(r"[-+]?(?:\d*\.\d+|\d+)(?:%|deg|rad|turn)?", text)


def percent_or_number(part: str, max_value: float) -> float:
    if part.endswith("%"):
        return float(part[:-1]) * max_value / 100
    return float(part.rstrip("deg").rstrip("rad").rstrip("turn"))


def hsl_to_rgb(hue: float, saturation: float, lightness: float) -> tuple[float, float, float]:
    hue = (hue % 360) / 360
    saturation = clamp(saturation / 100, 0, 1)
    lightness = clamp(lightness / 100, 0, 1)
    if saturation == 0:
        grey = lightness * 255
        return grey, grey, grey

    def hue_to_rgb(p: float, q: float, t: float) -> float:
        if t < 0:
            t += 1
        if t > 1:
            t -= 1
        if t < 1 / 6:
            return p + (q - p) * 6 * t
        if t < 1 / 2:
            return q
        if t < 2 / 3:
            return p + (q - p) * (2 / 3 - t) * 6
        return p

    q = lightness * (1 + saturation) if lightness < 0.5 else lightness + saturation - lightness * saturation
    p = 2 * lightness - q
    return hue_to_rgb(p, q, hue + 1 / 3) * 255, hue_to_rgb(p, q, hue) * 255, hue_to_rgb(p, q, hue - 1 / 3) * 255


def colors_from_function(token: Any) -> list[tuple[str, float]]:
    name = token.lower_name
    parts = parse_numeric_parts(serialize(token.arguments))
    if name in {"rgb", "rgba"} and len(parts) >= 3:
        red = percent_or_number(parts[0], 255)
        green = percent_or_number(parts[1], 255)
        blue = percent_or_number(parts[2], 255)
        alpha = percent_or_number(parts[3], 1) if len(parts) >= 4 else 1.0
        return [(rgb_to_hex(red, green, blue), clamp(alpha, 0, 1))]
    if name in {"hsl", "hsla"} and len(parts) >= 3:
        hue = float(parts[0].rstrip("deg").rstrip("rad").rstrip("turn"))
        saturation = percent_or_number(parts[1], 100)
        lightness = percent_or_number(parts[2], 100)
        alpha = percent_or_number(parts[3], 1) if len(parts) >= 4 else 1.0
        red, green, blue = hsl_to_rgb(hue, saturation, lightness)
        return [(rgb_to_hex(red, green, blue), clamp(alpha, 0, 1))]
    return []


def walk_tokens(tokens: list[Any]) -> list[Any]:
    walked: list[Any] = []
    for token in tokens:
        walked.append(token)
        for attr in ("arguments", "content"):
            nested = getattr(token, attr, None)
            if nested:
                walked.extend(walk_tokens(nested))
    return walked


def extract_colors_from_value(value: str) -> list[tuple[str, float]]:
    colors: list[tuple[str, float]] = []
    tokens = tinycss2.parse_component_value_list(value)
    for token in walk_tokens(tokens):
        if token.type == "hash":
            canonical = canonical_hash(token.value)
            if canonical:
                colors.append(canonical)
        elif token.type == "function":
            colors.extend(colors_from_function(token))
        elif token.type == "ident":
            named = NAMED_COLORS.get(token.value.lower())
            if named:
                colors.append((named, 1.0))
    return colors


def collect_color_occurrences(declarations: list[Declaration]) -> list[ColorOccurrence]:
    occurrences: list[ColorOccurrence] = []
    for declaration in declarations:
        for value, alpha in extract_colors_from_value(declaration.value):
            occurrences.append(ColorOccurrence(value, alpha, declaration.selector, declaration.property, declaration.value, declaration.source))
    return occurrences


def relative_luminance(hex_value: str) -> float:
    channels = []
    for channel in hex_to_rgb(hex_value):
        value = channel / 255
        channels.append(value / 12.92 if value <= 0.03928 else ((value + 0.055) / 1.055) ** 2.4)
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


def saturation(hex_value: str) -> float:
    red, green, blue = [channel / 255 for channel in hex_to_rgb(hex_value)]
    high = max(red, green, blue)
    low = min(red, green, blue)
    return 0 if high == 0 else (high - low) / high


def hue_degrees(hex_value: str) -> float:
    red, green, blue = [channel / 255 for channel in hex_to_rgb(hex_value)]
    high = max(red, green, blue)
    low = min(red, green, blue)
    delta = high - low
    if delta == 0:
        return 0
    if high == red:
        return (60 * ((green - blue) / delta) + 360) % 360
    if high == green:
        return 60 * ((blue - red) / delta + 2)
    return 60 * ((red - green) / delta + 4)


def is_red(hex_value: str) -> bool:
    hue = hue_degrees(hex_value)
    return saturation(hex_value) > 0.35 and (hue <= 25 or hue >= 335)


def is_green(hex_value: str) -> bool:
    hue = hue_degrees(hex_value)
    return saturation(hex_value) > 0.25 and 75 <= hue <= 165


def is_yellow_or_orange(hex_value: str) -> bool:
    hue = hue_degrees(hex_value)
    return saturation(hex_value) > 0.25 and 25 < hue <= 75


def is_accent_like(hex_value: str) -> bool:
    return saturation(hex_value) > 0.25 and not is_red(hex_value) and relative_luminance(hex_value) < 0.85


def first_unique_values(occurrences: list[ColorOccurrence]) -> list[str]:
    values: list[str] = []
    seen: set[str] = set()
    for occurrence in occurrences:
        if occurrence.value not in seen:
            seen.add(occurrence.value)
            values.append(occurrence.value)
    return values


def choose_occurrence(occurrences: list[ColorOccurrence], predicate: Any, scorer: Any) -> ColorOccurrence | None:
    candidates = [occurrence for occurrence in occurrences if predicate(occurrence)]
    if not candidates:
        return None
    return max(candidates, key=scorer)


def pick_or_fallback(occurrence: ColorOccurrence | None, fallback_values: list[str], fallback_index: int = 0) -> str:
    if occurrence:
        return occurrence.value
    if fallback_values:
        return fallback_values[min(fallback_index, len(fallback_values) - 1)]
    warn("no colors found; using #000000 placeholder to satisfy token schema")
    return "#000000"


def build_color_tokens(occurrences: list[ColorOccurrence]) -> OrderedDict[str, str]:
    values = first_unique_values(occurrences)
    light_values = sorted(values, key=relative_luminance, reverse=True)
    dark_values = sorted(values, key=relative_luminance)

    def bg(occ: ColorOccurrence) -> bool:
        return occ.property in {"background", "background-color"} or "background" in occ.property

    def border(occ: ColorOccurrence) -> bool:
        return "border" in occ.property and "radius" not in occ.property

    def text(occ: ColorOccurrence) -> bool:
        return occ.property == "color"

    surface = choose_occurrence(
        occurrences,
        lambda occ: bg(occ) and any(hint in occ.context for hint in ("body", "html", "app", "shell", "page", "main")),
        lambda occ: relative_luminance(occ.value),
    )
    elevated = choose_occurrence(
        occurrences,
        lambda occ: bg(occ)
        and (not surface or occ.value != surface.value)
        and any(hint in occ.context for hint in ("card", "panel", "sidebar", "chip", "popover", "modal", "elevated", "surface")),
        lambda occ: relative_luminance(occ.value),
    )
    border_color = choose_occurrence(occurrences, border, lambda occ: relative_luminance(occ.value))
    primary_text = choose_occurrence(
        occurrences,
        lambda occ: text(occ) and relative_luminance(occ.value) < 0.35 and any(hint in occ.context for hint in ("body", "main", "h1", "title", "page")),
        lambda occ: -relative_luminance(occ.value),
    )
    secondary_text = choose_occurrence(
        occurrences,
        lambda occ: text(occ) and relative_luminance(occ.value) < 0.65 and any(hint in occ.context for hint in ("secondary", "muted", "meta", "nav", "caption", "subtle")),
        lambda occ: -relative_luminance(occ.value),
    )
    tertiary_text = choose_occurrence(
        occurrences,
        lambda occ: text(occ) and any(hint in occ.context for hint in ("tertiary", "disabled", "placeholder", "subtle", "muted")),
        lambda occ: relative_luminance(occ.value),
    )
    accent = choose_occurrence(
        occurrences,
        lambda occ: is_accent_like(occ.value) and any(hint in occ.context for hint in ("accent", "primary", "selected", "active", "link", "button")),
        lambda occ: saturation(occ.value) - relative_luminance(occ.value) * 0.15,
    )
    danger = choose_occurrence(
        occurrences,
        lambda occ: is_red(occ.value) and any(hint in occ.context for hint in ("danger", "error", "destructive", "severity", "p1", "critical", "alert")),
        lambda occ: saturation(occ.value),
    ) or choose_occurrence(occurrences, lambda occ: is_red(occ.value), lambda occ: saturation(occ.value))
    success = choose_occurrence(
        occurrences,
        lambda occ: is_green(occ.value) and any(hint in occ.context for hint in ("success", "ok", "complete", "resolved", "green")),
        lambda occ: saturation(occ.value),
    ) or choose_occurrence(occurrences, lambda occ: is_green(occ.value), lambda occ: saturation(occ.value))
    warning_color = choose_occurrence(
        occurrences,
        lambda occ: is_yellow_or_orange(occ.value) and any(hint in occ.context for hint in ("warning", "pending", "risk", "yellow", "orange")),
        lambda occ: saturation(occ.value),
    ) or choose_occurrence(occurrences, lambda occ: is_yellow_or_orange(occ.value), lambda occ: saturation(occ.value))
    focus = choose_occurrence(
        occurrences,
        lambda occ: "focus" in occ.context and ("outline" in occ.property or "shadow" in occ.property or is_accent_like(occ.value)),
        lambda occ: saturation(occ.value),
    )

    default_surface = light_values[0] if light_values else "#FFFFFF"
    default_elevated = light_values[1] if len(light_values) > 1 else default_surface
    default_border = next((value for value in light_values if saturation(value) < 0.15 and value != default_surface), default_elevated)
    default_text = dark_values[0] if dark_values else "#000000"
    default_secondary = dark_values[1] if len(dark_values) > 1 else default_text
    default_accent = pick_or_fallback(accent, values, 0)
    default_danger = pick_or_fallback(danger, values, 0)

    tokens: OrderedDict[str, str] = OrderedDict()
    tokens["surface"] = pick_or_fallback(surface, [default_surface])
    tokens["surface-elevated"] = pick_or_fallback(elevated, [default_elevated])
    tokens["border"] = pick_or_fallback(border_color, [default_border])
    tokens["text-primary"] = pick_or_fallback(primary_text, [default_text])
    tokens["text-secondary"] = pick_or_fallback(secondary_text, [default_secondary])
    tokens["text-tertiary"] = pick_or_fallback(tertiary_text, [tokens["text-secondary"], tokens["border"]])
    tokens["accent"] = default_accent
    tokens["accent-hover"] = pick_or_fallback(
        choose_occurrence(occurrences, lambda occ: ":hover" in occ.context and is_accent_like(occ.value), lambda occ: saturation(occ.value)),
        [tokens["accent"]],
    )
    tokens["accent-pressed"] = pick_or_fallback(
        choose_occurrence(occurrences, lambda occ: (":active" in occ.context or "pressed" in occ.context) and is_accent_like(occ.value), lambda occ: saturation(occ.value)),
        [tokens["accent-hover"]],
    )
    tokens["success"] = pick_or_fallback(success, [tokens["accent"]])
    tokens["warning"] = pick_or_fallback(warning_color, [default_danger, tokens["accent"]])
    tokens["danger"] = default_danger
    tokens["focus-ring"] = pick_or_fallback(focus, [tokens["accent"]])
    return tokens


def length_token_to_px(token: Any, base_size: float = 16) -> float | None:
    if token.type == "dimension":
        unit = token.lower_unit
        if unit == "px":
            return float(token.value)
        if unit == "pt":
            return float(token.value) * 96 / 72
        if unit in {"rem", "em"}:
            return float(token.value) * base_size
    if token.type == "number" and float(token.value) == 0:
        return 0.0
    return None


def lengths_from_value(value: str, include_zero: bool = False) -> list[float]:
    lengths: list[float] = []
    for token in walk_tokens(tinycss2.parse_component_value_list(value)):
        amount = length_token_to_px(token)
        if amount is None:
            continue
        if amount == 0 and not include_zero:
            continue
        lengths.append(amount)
    return lengths


def rounded_ints(values: list[float]) -> list[int]:
    output: list[int] = []
    seen: set[int] = set()
    for value in values:
        integer = int(round(value))
        if integer not in seen:
            seen.add(integer)
            output.append(integer)
    return output


def choose_spacing_base(values: list[int]) -> int:
    positives = [value for value in values if value > 0]
    if not positives:
        return 4
    scores = {base: sum(1 for value in positives if value % base == 0) for base in (4, 6, 8, 2)}
    if scores[4] >= 3:
        return 4
    return max(scores, key=lambda base: (scores[base], -base))


def build_spacing_tokens(declarations: list[Declaration]) -> OrderedDict[str, Any]:
    lengths: list[float] = []
    for declaration in declarations:
        if declaration.property in SPACING_PROPS or (declaration.property.startswith("--") and any(hint in declaration.property for hint in ("spacing", "space", "gap", "padding", "margin", "inset"))):
            lengths.extend(lengths_from_value(declaration.value))
    scale = sorted(set(rounded_ints(lengths)))
    base = choose_spacing_base(scale)
    if len(scale) < 6:
        for value in [base, base * 2, base * 3, base * 4, base * 6, base * 8, base * 12, base * 16]:
            if value not in scale:
                scale.append(value)
        scale = sorted(set(scale))
        warn("spacing scale had fewer than six extracted values; extended with base multiples")
    return OrderedDict([("base", int(base)), ("scale", scale)])


def build_radius_tokens(declarations: list[Declaration]) -> OrderedDict[str, int]:
    radii: list[int] = []
    for declaration in declarations:
        if declaration.property in RADIUS_PROPS or "radius" in declaration.property:
            radii.extend(rounded_ints(lengths_from_value(declaration.value, include_zero=True)))
    unique = sorted(set(value for value in radii if 0 <= value <= 64))
    positives = [value for value in unique if value > 0]
    subtle = positives[0] if positives else 2
    standard = next((value for value in positives if value >= 5), positives[-1] if positives else 6)
    pillow = next((value for value in reversed(positives) if value <= 24), max(standard, 12))
    full = min(max(positives) if positives else 64, 64)
    if full < 24:
        full = 64
    return OrderedDict([("sharp", 0), ("subtle", int(subtle)), ("standard", int(standard)), ("pillow", int(pillow)), ("full", int(full))])


def parse_font_weight(value: str | None) -> int | None:
    if not value:
        return None
    lower = value.strip().lower()
    if lower == "normal":
        return 400
    if lower == "bold":
        return 700
    match = re.search(r"\b([1-9]00|950)\b", lower)
    if match:
        return int(match.group(1))
    return None


def clean_family(value: str) -> str:
    return re.sub(r"\s*,\s*", ", ", value.strip())


def first_length_px(value: str) -> float | None:
    for amount in lengths_from_value(value, include_zero=True):
        if amount > 0:
            return amount
    return None


def first_length_any_px(value: str) -> float | None:
    for amount in lengths_from_value(value, include_zero=True):
        return amount
    return None


def parse_letter_spacing(value: str) -> float:
    if value.strip().lower() == "normal":
        return 0.0
    amount = first_length_any_px(value)
    return round(amount if amount is not None else 0.0, 3)


def line_height_value(value: str, size: float) -> float | None:
    tokens = tinycss2.parse_component_value_list(value)
    for token in walk_tokens(tokens):
        if token.type == "number":
            return round(float(token.value) * size, 3)
        if token.type == "percentage":
            return round(float(token.value) * size / 100, 3)
        amount = length_token_to_px(token)
        if amount is not None and amount > 0:
            return round(amount, 3)
    return None


def parse_font_shorthand(value: str) -> dict[str, Any]:
    tokens = tinycss2.parse_component_value_list(value)
    result: dict[str, Any] = {}
    size_index = None
    for index, token in enumerate(tokens):
        amount = length_token_to_px(token)
        if amount and amount >= 6:
            result["size"] = round(amount, 3)
            size_index = index
            break
    if size_index is None:
        return result
    before = serialize(tokens[:size_index])
    weight = parse_font_weight(before)
    if weight:
        result["weight"] = weight

    family_start = size_index + 1
    next_token = next((i for i in range(size_index + 1, len(tokens)) if tokens[i].type != "whitespace"), None)
    if next_token is not None and getattr(tokens[next_token], "value", None) == "/":
        line_index = next((i for i in range(next_token + 1, len(tokens)) if tokens[i].type != "whitespace"), None)
        if line_index is not None:
            leading = line_height_value(serialize([tokens[line_index]]), result["size"])
            if leading:
                result["leading"] = leading
            family_start = line_index + 1

    family = clean_family(serialize(tokens[family_start:]))
    if family:
        result["family"] = family
    return result


def build_type_tokens(declarations: list[Declaration]) -> OrderedDict[str, dict[str, Any]]:
    records: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for declaration in declarations:
        if declaration.property not in TYPE_PROPS:
            continue
        record = records.setdefault(declaration.selector, {"selector": declaration.selector})
        if declaration.property == "font":
            record.update(parse_font_shorthand(declaration.value))
        elif declaration.property == "font-family":
            record["family"] = clean_family(declaration.value)
        elif declaration.property == "font-size":
            size = first_length_px(declaration.value)
            if size:
                record["size"] = round(size, 3)
        elif declaration.property == "font-weight":
            weight = parse_font_weight(declaration.value)
            if weight:
                record["weight"] = weight
        elif declaration.property == "line-height":
            record["line_height_raw"] = declaration.value
        elif declaration.property == "letter-spacing":
            record["tracking"] = parse_letter_spacing(declaration.value)

    if not records:
        warn("no type declarations found; using system fallback type tokens")

    body_record = next((record for selector, record in records.items() if "body" in selector.lower()), None)
    first_record = next(iter(records.values()), {})
    default_family = body_record.get("family") if body_record else first_record.get("family", "system-ui, sans-serif")
    default_size = float((body_record or first_record).get("size", 14))
    default_weight = int((body_record or first_record).get("weight", 400))
    default_tracking = float((body_record or first_record).get("tracking", 0))
    default_leading = float((body_record or first_record).get("leading", round(default_size * 1.4, 3)))

    candidates: list[dict[str, Any]] = []
    for record in records.values():
        size = float(record.get("size", default_size))
        leading = record.get("leading")
        if "line_height_raw" in record:
            leading = line_height_value(record["line_height_raw"], size)
        candidates.append(
            {
                "selector": record["selector"],
                "family": record.get("family", default_family),
                "size": round(size, 3),
                "weight": int(record.get("weight", default_weight)),
                "leading": round(float(leading if leading else max(default_leading, size * 1.2)), 3),
                "tracking": round(float(record.get("tracking", default_tracking if record is body_record else 0)), 3),
            }
        )

    if not candidates:
        candidates.append({"selector": "body", "family": default_family, "size": default_size, "weight": default_weight, "leading": default_leading, "tracking": default_tracking})

    def style_without_selector(candidate: dict[str, Any]) -> dict[str, Any]:
        return {key: candidate[key] for key in ("family", "size", "weight", "leading", "tracking")}

    def candidate_for(*hints: str) -> dict[str, Any] | None:
        for candidate in candidates:
            selector = candidate["selector"].lower()
            if any(hint in selector for hint in hints):
                return candidate
        return None

    largest = max(candidates, key=lambda item: item["size"])
    smallest = min(candidates, key=lambda item: (item["size"], item["weight"]))
    body = candidate_for("body") or min(candidates, key=lambda item: abs(item["size"] - default_size))
    title = candidate_for("h1", "title", "headline", "page-title") or largest
    h2 = candidate_for("h2", "section-title", "subhead") or sorted(candidates, key=lambda item: item["size"], reverse=True)[min(1, len(candidates) - 1)]
    caption = candidate_for("caption", "meta", "chip", "small", "nav") or smallest
    label = candidate_for("button", "label", "control") or caption

    tokens: OrderedDict[str, dict[str, Any]] = OrderedDict()
    tokens["display"] = style_without_selector(largest)
    tokens["h1"] = style_without_selector(title)
    tokens["h2"] = style_without_selector(h2)
    tokens["body"] = style_without_selector(body)
    tokens["caption"] = style_without_selector(caption)
    tokens["label"] = style_without_selector(label)

    row = candidate_for("row", "table", "cell")
    if row:
        tokens["row"] = style_without_selector(row)
    return tokens


def build_elevation_tokens(declarations: list[Declaration]) -> OrderedDict[str, str]:
    shadows: list[str] = []
    seen: set[str] = set()
    for declaration in declarations:
        if declaration.property == "box-shadow" or (declaration.property.startswith("--") and any(hint in declaration.property for hint in ("shadow", "elevation"))):
            normalized = re.sub(r"\s+", " ", declaration.value.strip())
            if normalized not in seen:
                seen.add(normalized)
                shadows.append(normalized)
    tokens: OrderedDict[str, str] = OrderedDict()
    tokens["none"] = next((shadow for shadow in shadows if shadow.lower() == "none"), "0 0 0 0 transparent")
    non_none = [shadow for shadow in shadows if shadow.lower() != "none"]
    if non_none:
        tokens["subtle"] = non_none[0]
        tokens["raised"] = non_none[min(1, len(non_none) - 1)]
    else:
        warn("no box-shadow declarations found; adding default none/subtle/raised elevation tokens")
        tokens["subtle"] = "0 1px 2px 0 #00000010"
        tokens["raised"] = "0 8px 24px -12px #00000030"
    return tokens


def duration_values_ms(value: str) -> list[int]:
    durations: list[int] = []
    for token in walk_tokens(tinycss2.parse_component_value_list(value)):
        if token.type == "dimension" and token.lower_unit in {"ms", "s"}:
            multiplier = 1 if token.lower_unit == "ms" else 1000
            durations.append(int(round(float(token.value) * multiplier)))
    return durations


def easing_values(value: str) -> list[str]:
    easings: list[str] = []
    for token in walk_tokens(tinycss2.parse_component_value_list(value)):
        if token.type == "function" and token.lower_name in {"cubic-bezier", "steps"}:
            easings.append(f"{token.lower_name}({serialize(token.arguments)})")
        elif token.type == "ident" and token.value.lower() in {"linear", "ease", "ease-in", "ease-out", "ease-in-out", "step-start", "step-end"}:
            easings.append(token.value.lower())
    return easings


def build_motion_tokens(declarations: list[Declaration]) -> OrderedDict[str, dict[str, Any]]:
    durations: list[int] = []
    easings: list[str] = []
    for declaration in declarations:
        if declaration.property in MOTION_PROPS or (declaration.property.startswith("--") and any(hint in declaration.property for hint in ("motion", "duration", "easing", "transition", "animation"))):
            durations.extend(duration_values_ms(declaration.value))
            easings.extend(easing_values(declaration.value))
    if not durations:
        warn("no transition or animation timings found; adding default web_ui motion timings")
        durations = [120, 150, 240]
    durations = sorted(set(durations))
    easing = easings[0] if easings else "cubic-bezier(.2, 0, 0, 1)"
    focus = min(durations)
    state_change = durations[len(durations) // 2]
    expressive = max(durations)
    return OrderedDict(
        [
            ("focus", {"duration_ms": int(focus), "easing": easing}),
            ("state_change", {"duration_ms": int(state_change), "easing": easing}),
            ("expressive", {"duration_ms": int(expressive), "easing": easing}),
        ]
    )


def build_density_tokens(soup: BeautifulSoup) -> OrderedDict[str, int]:
    semantic_rows = len(soup.find_all("tr")) + len(soup.find_all("li"))
    if semantic_rows == 0:
        for element in soup.find_all(True):
            classes = " ".join(element.get("class") or [])
            identity = f"{element.name} {element.get('id', '')} {classes}".lower()
            if "nav" in identity:
                continue
            if any(hint in identity for hint in ("row", "record", "alert", "result", "event", "list-item", "queue-item")):
                semantic_rows += 1
    return OrderedDict([("rows_visible_at_800pt", max(semantic_rows, 1))])


def alpha_pct_from_occurrences(occurrences: list[ColorOccurrence]) -> int:
    for occurrence in occurrences:
        if "focus" in occurrence.context and occurrence.alpha < 1:
            return int(round(occurrence.alpha * 100))
    return 60


def build_focus_tokens(declarations: list[Declaration], color_occurrences: list[ColorOccurrence], radius_tokens: OrderedDict[str, int]) -> OrderedDict[str, int]:
    focus_declarations = [declaration for declaration in declarations if ":focus" in declaration.selector.lower()]
    for declaration in focus_declarations:
        if declaration.property == "outline" and "blue" in declaration.value.lower():
            warn(f"default browser-like focus outline detected in {declaration.selector}: {declaration.value}")

    offset = None
    radius = None
    for declaration in focus_declarations:
        if declaration.property == "outline-offset":
            values = lengths_from_value(declaration.value, include_zero=True)
            if values:
                offset = int(round(values[0]))
        if declaration.property in RADIUS_PROPS:
            values = lengths_from_value(declaration.value, include_zero=True)
            if values:
                radius = int(round(values[0]))
    return OrderedDict([("offset", int(offset if offset is not None else 2)), ("color_alpha_pct", alpha_pct_from_occurrences(color_occurrences)), ("radius", int(radius if radius is not None else radius_tokens.get("standard", 4)))])


def srgb_to_linear(value: float) -> float:
    value = value / 255
    return value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4


def rgb_to_lab(red: int, green: int, blue: int) -> tuple[float, float, float]:
    r = srgb_to_linear(red)
    g = srgb_to_linear(green)
    b = srgb_to_linear(blue)
    x = r * 0.4124564 + g * 0.3575761 + b * 0.1804375
    y = r * 0.2126729 + g * 0.7151522 + b * 0.0721750
    z = r * 0.0193339 + g * 0.1191920 + b * 0.9503041
    x /= 0.95047
    z /= 1.08883

    def pivot(component: float) -> float:
        return component ** (1 / 3) if component > 0.008856 else 7.787 * component + 16 / 116

    fx = pivot(x)
    fy = pivot(y)
    fz = pivot(z)
    return 116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)


def delta_e76(first: str, second: str) -> float:
    lab1 = rgb_to_lab(*hex_to_rgb(first))
    lab2 = rgb_to_lab(*hex_to_rgb(second))
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(lab1, lab2)))


def warn_near_duplicate_colors(occurrences: list[ColorOccurrence]) -> None:
    values = first_unique_values(occurrences)
    for index, first in enumerate(values):
        for second in values[index + 1 :]:
            delta = delta_e76(first, second)
            if 0 < delta < 3:
                warn(f"near-duplicate colors {first} and {second} have Delta E76 {delta:.2f}; consider consolidation")


def build_payload(mockup_path: Path) -> OrderedDict[str, Any]:
    _html, soup = read_mockup(mockup_path)
    declarations = extract_declarations(mockup_path, soup)
    if not declarations:
        warn("no CSS declarations were extracted from mockup")
    colors = collect_color_occurrences(declarations)
    warn_near_duplicate_colors(colors)
    radius_tokens = build_radius_tokens(declarations)
    return OrderedDict(
        [
            ("color", build_color_tokens(colors)),
            ("type", build_type_tokens(declarations)),
            ("spacing", build_spacing_tokens(declarations)),
            ("radius", radius_tokens),
            ("elevation", build_elevation_tokens(declarations)),
            ("motion", build_motion_tokens(declarations)),
            ("density", build_density_tokens(soup)),
            ("focus", build_focus_tokens(declarations, colors, radius_tokens)),
        ]
    )


def validate_payload(payload: dict[str, Any]) -> list[str]:
    try:
        import jsonschema
    except ImportError as exc:  # pragma: no cover
        raise SystemExit("jsonschema is required. Install with: python3 -m pip install jsonschema") from exc
    schema_path = Path(__file__).resolve().parents[1] / "schemas" / "token-payload-web_ui.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(payload), key=lambda error: list(error.path))
    return [f"{'/'.join(str(part) for part in error.path) or '/'}: {error.message}" for error in errors]


def flatten_tokens(value: Any, prefix: str = "") -> dict[str, Any]:
    if isinstance(value, dict):
        flattened: dict[str, Any] = {}
        for key, child in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            flattened.update(flatten_tokens(child, path))
        return flattened
    return {prefix: value}


def load_manifest_tokens(path: Path) -> dict[str, Any]:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(manifest, dict) and "tokens" in manifest and isinstance(manifest["tokens"], dict):
        return manifest["tokens"]
    return manifest


def compare_manifest(payload: dict[str, Any], manifest_path: Path) -> dict[str, Any]:
    manifest_tokens = load_manifest_tokens(manifest_path)
    extracted = flatten_tokens(payload)
    declared = flatten_tokens(manifest_tokens)
    absent_in_manifest = sorted(path for path in extracted if path not in declared)
    absent_in_mockup = sorted(path for path in declared if path not in extracted)
    mismatches = []
    for path in sorted(set(extracted) & set(declared)):
        if extracted[path] != declared[path]:
            mismatches.append({"path": path, "extracted": extracted[path], "manifest": declared[path]})
    return {"valid": not absent_in_manifest and not absent_in_mockup and not mismatches, "absent_in_manifest": absent_in_manifest, "absent_in_mockup": absent_in_mockup, "value_mismatches": mismatches}


def write_payload(payload: dict[str, Any], out_path: Path | None) -> None:
    text = json.dumps(payload, indent=2) + "\n"
    sys.stdout.write(text)
    if out_path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text, encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mockup", required=True, help="Path to locked HTML mockup.")
    parser.add_argument("--out", help="Optional JSON output path.")
    parser.add_argument("--validate-against-manifest", help="Optional manifest.json path to compare against extracted tokens.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    mockup_path = Path(args.mockup).expanduser().resolve()
    if not mockup_path.exists():
        print(f"mockup not found: {mockup_path}", file=sys.stderr)
        return 2
    payload = build_payload(mockup_path)
    errors = validate_payload(payload)
    if errors:
        for error in errors:
            print(f"schema error: {error}", file=sys.stderr)
        return 1

    manifest_report = None
    if args.validate_against_manifest:
        manifest_report = compare_manifest(payload, Path(args.validate_against_manifest).expanduser().resolve())
        if not manifest_report["valid"]:
            print(json.dumps({"manifest_validation": manifest_report}, indent=2), file=sys.stderr)

    write_payload(payload, Path(args.out).expanduser() if args.out else None)
    if manifest_report and not manifest_report["valid"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
