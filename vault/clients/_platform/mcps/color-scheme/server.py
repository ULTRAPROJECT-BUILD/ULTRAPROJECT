"""
color-scheme MCP Server
Harmonious color palette generation, WCAG contrast checking, color format conversion,
and framework-ready output (CSS variables, SCSS, Tailwind). Pure Python — no external APIs.
"""

import colorsys
import json
import math
import re
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("color-scheme")


# --- Color Parsing & Conversion Utilities ---

def _parse_hex(hex_str: str) -> tuple:
    """Parse hex color string to (r, g, b) floats 0-1."""
    hex_str = hex_str.strip().lstrip("#")
    if len(hex_str) == 3:
        hex_str = "".join(c * 2 for c in hex_str)
    if len(hex_str) != 6:
        raise ValueError(f"Invalid hex color: #{hex_str}")
    r = int(hex_str[0:2], 16) / 255.0
    g = int(hex_str[2:4], 16) / 255.0
    b = int(hex_str[4:6], 16) / 255.0
    return (r, g, b)


def _rgb_to_hex(r: float, g: float, b: float) -> str:
    """Convert (r, g, b) floats 0-1 to hex string."""
    return "#{:02x}{:02x}{:02x}".format(
        max(0, min(255, round(r * 255))),
        max(0, min(255, round(g * 255))),
        max(0, min(255, round(b * 255)))
    )


def _parse_rgb_string(rgb_str: str) -> tuple:
    """Parse 'rgb(R, G, B)' or 'R, G, B' to (r, g, b) floats 0-1."""
    nums = re.findall(r"[\d.]+", rgb_str)
    if len(nums) < 3:
        raise ValueError(f"Invalid RGB string: {rgb_str}")
    return (float(nums[0]) / 255.0, float(nums[1]) / 255.0, float(nums[2]) / 255.0)


def _parse_hsl_string(hsl_str: str) -> tuple:
    """Parse 'hsl(H, S%, L%)' or 'H, S, L' to (r, g, b) floats 0-1."""
    nums = re.findall(r"[\d.]+", hsl_str)
    if len(nums) < 3:
        raise ValueError(f"Invalid HSL string: {hsl_str}")
    h = float(nums[0]) / 360.0
    s = float(nums[1]) / 100.0
    l = float(nums[2]) / 100.0
    r, g, b = colorsys.hls_to_rgb(h, l, s)
    return (r, g, b)


def _parse_color(color: str) -> tuple:
    """Parse any supported color format to (r, g, b) floats 0-1."""
    color = color.strip()
    # Named colors (common subset)
    named = _NAMED_COLORS.get(color.lower())
    if named:
        return _parse_hex(named)
    if color.startswith("#") or re.match(r"^[0-9a-fA-F]{3,6}$", color):
        return _parse_hex(color)
    if color.lower().startswith("rgb"):
        return _parse_rgb_string(color)
    if color.lower().startswith("hsl"):
        return _parse_hsl_string(color)
    # Try as comma-separated RGB
    if "," in color:
        return _parse_rgb_string(color)
    raise ValueError(f"Cannot parse color: {color}. Use hex (#ff0000), rgb(255,0,0), hsl(0,100%,50%), or a named color.")


def _rgb_to_hsl(r: float, g: float, b: float) -> tuple:
    """Convert RGB floats to HSL (H in degrees, S and L as percentages)."""
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    return (round(h * 360, 1), round(s * 100, 1), round(l * 100, 1))


def _rgb_to_hsv(r: float, g: float, b: float) -> tuple:
    """Convert RGB floats to HSV (H in degrees, S and V as percentages)."""
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    return (round(h * 360, 1), round(s * 100, 1), round(v * 100, 1))


def _color_info(r: float, g: float, b: float, name: str = "") -> dict:
    """Build a comprehensive color info dict."""
    hex_val = _rgb_to_hex(r, g, b)
    h, s, l = _rgb_to_hsl(r, g, b)
    hv, sv, vv = _rgb_to_hsv(r, g, b)
    return {
        "name": name,
        "hex": hex_val,
        "rgb": {"r": round(r * 255), "g": round(g * 255), "b": round(b * 255)},
        "hsl": {"h": h, "s": s, "l": l},
        "hsv": {"h": hv, "s": sv, "v": vv},
        "css_rgb": f"rgb({round(r*255)}, {round(g*255)}, {round(b*255)})",
        "css_hsl": f"hsl({h}, {s}%, {l}%)",
    }


# --- WCAG Contrast Utilities ---

def _relative_luminance(r: float, g: float, b: float) -> float:
    """Calculate relative luminance per WCAG 2.1 spec."""
    def linearize(c):
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * linearize(r) + 0.7152 * linearize(g) + 0.0722 * linearize(b)


def _contrast_ratio(rgb1: tuple, rgb2: tuple) -> float:
    """Calculate WCAG contrast ratio between two RGB tuples."""
    l1 = _relative_luminance(*rgb1)
    l2 = _relative_luminance(*rgb2)
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def _wcag_verdict(ratio: float) -> dict:
    """Return WCAG compliance levels for a contrast ratio."""
    return {
        "ratio": round(ratio, 2),
        "AA_normal_text": ratio >= 4.5,
        "AA_large_text": ratio >= 3.0,
        "AAA_normal_text": ratio >= 7.0,
        "AAA_large_text": ratio >= 4.5,
        "AA_ui_components": ratio >= 3.0,
    }


# --- Palette Generation ---

def _hue_shift(r: float, g: float, b: float, degrees: float) -> tuple:
    """Shift hue by given degrees, return new RGB."""
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    h = (h + degrees / 360.0) % 1.0
    return colorsys.hls_to_rgb(h, l, s)


def _generate_harmony(r: float, g: float, b: float, harmony: str) -> list:
    """Generate harmonious colors based on color theory rules."""
    harmonies = {
        "complementary": [180],
        "analogous": [-30, 30],
        "triadic": [120, 240],
        "split-complementary": [150, 210],
        "tetradic": [90, 180, 270],
        "square": [90, 180, 270],
        "monochromatic": [],  # handled separately
    }
    if harmony not in harmonies:
        raise ValueError(f"Unknown harmony: {harmony}. Options: {', '.join(harmonies.keys())}")

    colors = [(r, g, b)]
    if harmony == "monochromatic":
        h, l, s = colorsys.rgb_to_hls(r, g, b)
        for l_shift in [-0.25, -0.12, 0.12, 0.25]:
            new_l = max(0.05, min(0.95, l + l_shift))
            colors.append(colorsys.hls_to_rgb(h, new_l, s))
    else:
        for deg in harmonies[harmony]:
            colors.append(_hue_shift(r, g, b, deg))
    return colors


# --- Named Colors ---

_NAMED_COLORS = {
    "black": "#000000", "white": "#ffffff", "red": "#ff0000", "green": "#008000",
    "blue": "#0000ff", "yellow": "#ffff00", "cyan": "#00ffff", "magenta": "#ff00ff",
    "orange": "#ffa500", "purple": "#800080", "pink": "#ffc0cb", "brown": "#a52a2a",
    "gray": "#808080", "grey": "#808080", "navy": "#000080", "teal": "#008080",
    "olive": "#808000", "maroon": "#800000", "lime": "#00ff00", "aqua": "#00ffff",
    "silver": "#c0c0c0", "gold": "#ffd700", "coral": "#ff7f50", "salmon": "#fa8072",
    "khaki": "#f0e68c", "plum": "#dda0dd", "orchid": "#da70d6", "tan": "#d2b48c",
    "crimson": "#dc143c", "indigo": "#4b0082", "violet": "#ee82ee", "turquoise": "#40e0d0",
    "sienna": "#a0522d", "peru": "#cd853f", "chocolate": "#d2691e", "tomato": "#ff6347",
    "slateblue": "#6a5acd", "steelblue": "#4682b4", "royalblue": "#4169e1",
    "dodgerblue": "#1e90ff", "skyblue": "#87ceeb", "mintcream": "#f5fffa",
    "ivory": "#fffff0", "lavender": "#e6e6fa", "honeydew": "#f0fff0",
    "aliceblue": "#f0f8ff", "beige": "#f5f5dc", "linen": "#faf0e6",
    "seagreen": "#2e8b57", "forestgreen": "#228b22", "darkgreen": "#006400",
    "darkblue": "#00008b", "darkred": "#8b0000", "darkgray": "#a9a9a9",
    "lightgray": "#d3d3d3", "whitesmoke": "#f5f5f5",
}


# --- MCP Tools ---

@mcp.tool()
def convert_color(color: str, target_format: str = "all") -> str:
    """Convert a color between formats (hex, RGB, HSL, HSV, CSS).

    Args:
        color: Input color — hex (#ff0000), rgb(255,0,0), hsl(0,100%,50%), or named (red)
        target_format: Target format — 'hex', 'rgb', 'hsl', 'hsv', 'css', or 'all' (default: all)

    Returns:
        JSON with the color in the requested format(s)
    """
    try:
        r, g, b = _parse_color(color)
        info = _color_info(r, g, b)

        if target_format == "all":
            return json.dumps(info, indent=2)

        format_map = {
            "hex": info["hex"],
            "rgb": info["css_rgb"],
            "hsl": info["css_hsl"],
            "hsv": f"hsv({info['hsv']['h']}, {info['hsv']['s']}%, {info['hsv']['v']}%)",
            "css": {"rgb": info["css_rgb"], "hsl": info["css_hsl"], "hex": info["hex"]},
        }
        if target_format not in format_map:
            return json.dumps({"error": f"Unknown format: {target_format}. Options: hex, rgb, hsl, hsv, css, all"})
        return json.dumps({"input": color, "format": target_format, "result": format_map[target_format]}, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def generate_palette(base_color: str, harmony: str = "complementary", count: int = 5) -> str:
    """Generate a harmonious color palette from a base color using color theory.

    Args:
        base_color: Base color — hex (#3498db), rgb(52,152,219), hsl(204,70%,53%), or named
        harmony: Harmony type — complementary, analogous, triadic, split-complementary, tetradic, square, monochromatic
        count: Number of colors to return (default: 5, adds tints/shades if harmony produces fewer)

    Returns:
        JSON with palette colors including hex, RGB, HSL values and the harmony used
    """
    try:
        r, g, b = _parse_color(base_color)
        raw_colors = _generate_harmony(r, g, b, harmony)

        # If we need more colors than the harmony provides, add tints and shades
        while len(raw_colors) < count:
            h, l, s = colorsys.rgb_to_hls(r, g, b)
            offset = len(raw_colors) * 0.08
            if len(raw_colors) % 2 == 0:
                new_l = min(0.95, l + offset)
            else:
                new_l = max(0.05, l - offset)
            raw_colors.append(colorsys.hls_to_rgb(h, new_l, s))

        raw_colors = raw_colors[:count]

        harmony_names = {
            "complementary": ["base", "complement"],
            "analogous": ["base", "analogous-left", "analogous-right"],
            "triadic": ["base", "triad-2", "triad-3"],
            "split-complementary": ["base", "split-left", "split-right"],
            "tetradic": ["base", "tetra-2", "tetra-3", "tetra-4"],
            "square": ["base", "square-2", "square-3", "square-4"],
            "monochromatic": ["base", "dark-2", "dark-1", "light-1", "light-2"],
        }
        names = harmony_names.get(harmony, [])

        palette = []
        for i, (cr, cg, cb) in enumerate(raw_colors):
            name = names[i] if i < len(names) else f"variant-{i}"
            palette.append(_color_info(cr, cg, cb, name))

        return json.dumps({
            "base_color": base_color,
            "harmony": harmony,
            "count": len(palette),
            "palette": palette
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def check_contrast(foreground: str, background: str) -> str:
    """Check WCAG 2.1 contrast ratio between two colors for accessibility compliance.

    Args:
        foreground: Foreground/text color — hex, rgb, hsl, or named
        background: Background color — hex, rgb, hsl, or named

    Returns:
        JSON with contrast ratio and WCAG AA/AAA pass/fail for normal text, large text, and UI components
    """
    try:
        fg = _parse_color(foreground)
        bg = _parse_color(background)
        ratio = _contrast_ratio(fg, bg)
        verdict = _wcag_verdict(ratio)

        return json.dumps({
            "foreground": {"input": foreground, "hex": _rgb_to_hex(*fg)},
            "background": {"input": background, "hex": _rgb_to_hex(*bg)},
            "contrast_ratio": verdict["ratio"],
            "wcag_compliance": {
                "AA_normal_text": {"required": 4.5, "pass": verdict["AA_normal_text"]},
                "AA_large_text": {"required": 3.0, "pass": verdict["AA_large_text"]},
                "AAA_normal_text": {"required": 7.0, "pass": verdict["AAA_normal_text"]},
                "AAA_large_text": {"required": 4.5, "pass": verdict["AAA_large_text"]},
                "AA_ui_components": {"required": 3.0, "pass": verdict["AA_ui_components"]},
            },
            "summary": _contrast_summary(verdict),
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


def _contrast_summary(verdict: dict) -> str:
    """Human-readable contrast summary."""
    r = verdict["ratio"]
    if r >= 7.0:
        return f"Excellent contrast ({r}:1) — passes WCAG AAA for all text sizes"
    elif r >= 4.5:
        return f"Good contrast ({r}:1) — passes WCAG AA for normal text, AAA for large text"
    elif r >= 3.0:
        return f"Moderate contrast ({r}:1) — passes WCAG AA for large text and UI components only"
    else:
        return f"Poor contrast ({r}:1) — fails WCAG AA for all text. Not accessible."


@mcp.tool()
def suggest_accessible_pair(base_color: str, target_ratio: float = 4.5, role: str = "text") -> str:
    """Suggest a foreground or background color that meets WCAG contrast requirements with the given base.

    Args:
        base_color: The fixed color to pair against — hex, rgb, hsl, or named
        target_ratio: Minimum contrast ratio to achieve (default: 4.5 for WCAG AA normal text)
        role: Whether the base is 'background' (find text color) or 'text' (find background color)

    Returns:
        JSON with suggested color pairs that meet the target contrast ratio
    """
    try:
        r, g, b = _parse_color(base_color)
        luminance = _relative_luminance(r, g, b)
        suggestions = []

        # Try white and black first
        white_ratio = _contrast_ratio((r, g, b), (1.0, 1.0, 1.0))
        black_ratio = _contrast_ratio((r, g, b), (0.0, 0.0, 0.0))

        if white_ratio >= target_ratio:
            suggestions.append({
                "color": "#ffffff",
                "contrast_ratio": round(white_ratio, 2),
                "label": "white"
            })
        if black_ratio >= target_ratio:
            suggestions.append({
                "color": "#000000",
                "contrast_ratio": round(black_ratio, 2),
                "label": "black"
            })

        # Try lightened/darkened versions of the base color
        h, l, s = colorsys.rgb_to_hls(r, g, b)
        for step in range(1, 20):
            for direction in [1, -1]:
                new_l = l + (direction * step * 0.05)
                if new_l < 0.0 or new_l > 1.0:
                    continue
                nr, ng, nb = colorsys.hls_to_rgb(h, new_l, s)
                ratio = _contrast_ratio((r, g, b), (nr, ng, nb))
                if ratio >= target_ratio:
                    hex_val = _rgb_to_hex(nr, ng, nb)
                    if not any(s["color"] == hex_val for s in suggestions):
                        label = "lighter" if direction > 0 else "darker"
                        suggestions.append({
                            "color": hex_val,
                            "contrast_ratio": round(ratio, 2),
                            "label": f"{label} variant"
                        })
            if len(suggestions) >= 5:
                break

        # Sort by closest to target ratio (prefer minimal change)
        suggestions.sort(key=lambda s: abs(s["contrast_ratio"] - target_ratio))

        return json.dumps({
            "base_color": base_color,
            "base_hex": _rgb_to_hex(r, g, b),
            "target_ratio": target_ratio,
            "role": role,
            "suggestions": suggestions[:5],
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def palette_accessibility_matrix(colors: str) -> str:
    """Check WCAG contrast between all pairs in a color palette — useful for validating a full design system.

    Args:
        colors: Comma-separated list of colors (hex, rgb, hsl, or named). Example: '#ffffff, #333333, #3498db, #e74c3c'

    Returns:
        JSON matrix showing contrast ratios and WCAG compliance for every color pair
    """
    try:
        color_list = [c.strip() for c in colors.split(",")]
        if len(color_list) < 2:
            return json.dumps({"error": "Need at least 2 colors. Separate with commas."})

        parsed = []
        for c in color_list:
            rgb = _parse_color(c)
            parsed.append({"input": c, "hex": _rgb_to_hex(*rgb), "rgb": rgb})

        matrix = []
        for i, c1 in enumerate(parsed):
            for j, c2 in enumerate(parsed):
                if i >= j:
                    continue
                ratio = _contrast_ratio(c1["rgb"], c2["rgb"])
                verdict = _wcag_verdict(ratio)
                matrix.append({
                    "pair": [c1["hex"], c2["hex"]],
                    "contrast_ratio": verdict["ratio"],
                    "AA_normal": verdict["AA_normal_text"],
                    "AA_large": verdict["AA_large_text"],
                    "AAA_normal": verdict["AAA_normal_text"],
                })

        # Summary stats
        passing_aa = sum(1 for m in matrix if m["AA_normal"])
        total = len(matrix)

        return json.dumps({
            "color_count": len(parsed),
            "pair_count": total,
            "aa_normal_passing": passing_aa,
            "aa_normal_pass_rate": f"{round(passing_aa/total*100)}%" if total > 0 else "N/A",
            "pairs": matrix,
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def export_css_variables(colors: str, prefix: str = "color") -> str:
    """Export a palette as CSS custom properties (variables), SCSS variables, and Tailwind config.

    Args:
        colors: Comma-separated colors (hex, rgb, hsl, or named). Example: '#3498db, #2ecc71, #e74c3c'
        prefix: Variable name prefix (default: 'color'). Generates --{prefix}-1, --{prefix}-2, etc.

    Returns:
        JSON with CSS variables, SCSS variables, and Tailwind config object
    """
    try:
        color_list = [c.strip() for c in colors.split(",")]
        parsed = []
        for c in color_list:
            rgb = _parse_color(c)
            parsed.append({"input": c, "hex": _rgb_to_hex(*rgb), "rgb": rgb})

        # CSS custom properties
        css_lines = [":root {"]
        for i, c in enumerate(parsed):
            css_lines.append(f"  --{prefix}-{i+1}: {c['hex']};")
        css_lines.append("}")
        css_output = "\n".join(css_lines)

        # SCSS variables
        scss_lines = []
        for i, c in enumerate(parsed):
            scss_lines.append(f"${prefix}-{i+1}: {c['hex']};")
        scss_output = "\n".join(scss_lines)

        # Tailwind config
        tailwind_colors = {}
        for i, c in enumerate(parsed):
            tailwind_colors[f"{prefix}-{i+1}"] = c["hex"]
        tailwind_output = {
            "theme": {
                "extend": {
                    "colors": tailwind_colors
                }
            }
        }

        # CSS rgb() format for opacity support
        css_rgb_lines = [":root {"]
        for i, c in enumerate(parsed):
            r, g, b = c["rgb"]
            css_rgb_lines.append(f"  --{prefix}-{i+1}-rgb: {round(r*255)}, {round(g*255)}, {round(b*255)};")
        css_rgb_lines.append("}")
        css_rgb_output = "\n".join(css_rgb_lines)

        return json.dumps({
            "color_count": len(parsed),
            "css_variables": css_output,
            "css_rgb_variables": css_rgb_output,
            "scss_variables": scss_output,
            "tailwind_config": tailwind_output,
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def analyze_color(color: str) -> str:
    """Analyze a color's properties — hue, saturation, lightness, warmth, luminance, and nearest named color.

    Args:
        color: Color to analyze — hex (#ff6347), rgb(255,99,71), hsl(9,100%,64%), or named (tomato)

    Returns:
        JSON with comprehensive color analysis including perceptual properties
    """
    try:
        r, g, b = _parse_color(color)
        info = _color_info(r, g, b)
        luminance = _relative_luminance(r, g, b)
        h, s, l = _rgb_to_hsl(r, g, b)

        # Determine warmth
        if h <= 60 or h >= 300:
            warmth = "warm"
        elif 120 <= h <= 240:
            warmth = "cool"
        else:
            warmth = "neutral"

        # Determine lightness category
        if l < 20:
            lightness_cat = "very dark"
        elif l < 40:
            lightness_cat = "dark"
        elif l < 60:
            lightness_cat = "medium"
        elif l < 80:
            lightness_cat = "light"
        else:
            lightness_cat = "very light"

        # Determine saturation category
        if s < 10:
            sat_cat = "achromatic"
        elif s < 30:
            sat_cat = "muted"
        elif s < 60:
            sat_cat = "moderate"
        elif s < 85:
            sat_cat = "vivid"
        else:
            sat_cat = "pure"

        # Find nearest named color
        nearest = _find_nearest_named(r, g, b)

        return json.dumps({
            **info,
            "luminance": round(luminance, 4),
            "warmth": warmth,
            "lightness_category": lightness_cat,
            "saturation_category": sat_cat,
            "nearest_named_color": nearest,
            "is_light": luminance > 0.179,
            "recommended_text": "#000000" if luminance > 0.179 else "#ffffff",
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


def _find_nearest_named(r: float, g: float, b: float) -> dict:
    """Find the nearest CSS named color by Euclidean distance in RGB space."""
    best_name = ""
    best_dist = float("inf")
    best_hex = ""
    for name, hex_val in _NAMED_COLORS.items():
        nr, ng, nb = _parse_hex(hex_val)
        dist = math.sqrt((r - nr) ** 2 + (g - ng) ** 2 + (b - nb) ** 2)
        if dist < best_dist:
            best_dist = dist
            best_name = name
            best_hex = hex_val
    return {"name": best_name, "hex": best_hex, "distance": round(best_dist, 4)}


# --- Entry Point ---

if __name__ == "__main__":
    mcp.run()
