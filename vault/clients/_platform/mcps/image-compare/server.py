"""
Image Compare MCP Server — Visual diff for design QC

Provides pixel-level image comparison tools for verifying design fidelity:
- compare_images: compare two local image files, generate diff image and stats
- compare_urls: compare two URLs by screenshotting them (requires playwright)
- generate_diff_report: structured pass/fail report against configurable threshold

Uses Pillow for image processing. No external API required — all processing is local.
Dependencies: Pillow, mcp
"""

import json
import math
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from PIL import Image, ImageChops, ImageDraw
from mcp.server.fastmcp import FastMCP

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_THRESHOLD = 5.0  # percentage diff above which comparison fails
DEFAULT_PIXEL_TOLERANCE = 10  # per-channel tolerance (0-255) for pixel matching
DIFF_OUTPUT_DIR = os.environ.get(
    "IMAGE_COMPARE_OUTPUT_DIR",
    os.path.join(tempfile.gettempdir(), "image-compare-diffs"),
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ensure_dir(path: str) -> None:
    """Create parent directories for the given file path if they don't exist."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)


def _file_size_str(size_bytes: int) -> str:
    """Return a human-readable file size string."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.2f} MB"


def _load_and_normalize(path: str) -> Image.Image:
    """Load an image, convert to RGBA for consistent comparison."""
    img = Image.open(path)
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    return img


def _resize_to_match(img1: Image.Image, img2: Image.Image) -> tuple:
    """Resize images to the same dimensions (use the larger canvas).

    Returns (img1_resized, img2_resized, size_mismatch_info).
    If sizes already match, returns originals unchanged.
    """
    if img1.size == img2.size:
        return img1, img2, None

    # Use the union bounding box (max width, max height)
    w = max(img1.size[0], img2.size[0])
    h = max(img1.size[1], img2.size[1])

    mismatch_info = {
        "image1_size": f"{img1.size[0]}x{img1.size[1]}",
        "image2_size": f"{img2.size[0]}x{img2.size[1]}",
        "canvas_size": f"{w}x{h}",
        "note": "Images had different dimensions. Both placed on same-size canvas (top-left aligned) for comparison.",
    }

    # Create canvases with transparent background
    canvas1 = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    canvas2 = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    canvas1.paste(img1, (0, 0))
    canvas2.paste(img2, (0, 0))

    return canvas1, canvas2, mismatch_info


def _compute_diff(
    img1: Image.Image,
    img2: Image.Image,
    pixel_tolerance: int = DEFAULT_PIXEL_TOLERANCE,
) -> dict:
    """Compute pixel-level diff between two same-size RGBA images.

    Returns dict with diff stats and a diff image (red overlay on changed pixels).
    """
    w, h = img1.size
    total_pixels = w * h

    px1 = img1.load()
    px2 = img2.load()

    # Create diff visualization image
    # Base: blend of both images at 50% opacity for context
    blended = Image.blend(img1.convert("RGBA"), img2.convert("RGBA"), 0.5)
    diff_img = blended.copy()
    diff_draw = diff_img.load()

    diff_count = 0
    max_channel_diff = 0

    for y in range(h):
        for x in range(w):
            r1, g1, b1, a1 = px1[x, y]
            r2, g2, b2, a2 = px2[x, y]

            # Per-channel absolute difference
            dr = abs(r1 - r2)
            dg = abs(g1 - g2)
            db = abs(b1 - b2)
            da = abs(a1 - a2)

            channel_max = max(dr, dg, db, da)
            if channel_max > max_channel_diff:
                max_channel_diff = channel_max

            # If any channel exceeds tolerance, this pixel is "different"
            if channel_max > pixel_tolerance:
                diff_count += 1
                # Color the diff pixel red with intensity based on magnitude
                intensity = min(255, int(channel_max * 2))
                diff_draw[x, y] = (255, 0, 0, intensity)

    diff_percentage = (diff_count / total_pixels * 100) if total_pixels > 0 else 0

    return {
        "total_pixels": total_pixels,
        "diff_pixels": diff_count,
        "diff_percentage": round(diff_percentage, 4),
        "max_channel_diff": max_channel_diff,
        "dimensions": f"{w}x{h}",
        "diff_image": diff_img,
    }


def _save_diff_image(diff_img: Image.Image, output_path: str) -> str:
    """Save the diff visualization image to disk."""
    _ensure_dir(output_path)
    diff_img.save(output_path, format="PNG")
    return output_path


def _screenshot_url(url: str, output_path: str, width: int = 1280, height: int = 720) -> str:
    """Take a screenshot of a URL using playwright CLI.

    Returns the path to the saved screenshot, or raises an exception.
    """
    _ensure_dir(output_path)
    # Use npx playwright screenshot command
    cmd = [
        "npx", "playwright", "screenshot",
        "--viewport-size", f"{width},{height}",
        "--full-page",
        url,
        output_path,
    ]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Playwright screenshot failed (exit {result.returncode}): {result.stderr.strip()}"
        )
    if not os.path.isfile(output_path):
        raise RuntimeError(f"Screenshot file was not created at {output_path}")
    return output_path


# ---------------------------------------------------------------------------
# MCP Server
# ---------------------------------------------------------------------------

mcp = FastMCP("image-compare")


@mcp.tool()
def compare_images(
    image1_path: str,
    image2_path: str,
    output_diff_path: str = "",
    pixel_tolerance: int = DEFAULT_PIXEL_TOLERANCE,
    threshold: float = DEFAULT_THRESHOLD,
) -> str:
    """Compare two local image files pixel-by-pixel and generate a visual diff.

    Computes the percentage of pixels that differ beyond the tolerance, generates
    a diff overlay image (red highlights on changed pixels), and returns a
    pass/fail verdict against the threshold.

    Use this for design QC: compare a reference mockup against a built screenshot
    to find visual discrepancies.

    Args:
        image1_path: Path to the reference/baseline image (e.g., design mockup).
        image2_path: Path to the comparison image (e.g., screenshot of built site).
        output_diff_path: Path to save the diff visualization image. If empty,
                          auto-generates a path in the temp directory.
        pixel_tolerance: Per-channel tolerance (0-255) below which pixel
                         differences are ignored. Default 10. Set to 0 for
                         exact pixel matching.
        threshold: Diff percentage (0-100) above which the comparison fails.
                   Default 5.0. Set to 0 for zero-tolerance matching.

    Returns:
        JSON string with diff_percentage, diff_pixels, total_pixels, verdict
        (pass/fail), diff_image_path, and size_mismatch info if applicable.
    """
    image1_path = image1_path.strip()
    image2_path = image2_path.strip()
    output_diff_path = output_diff_path.strip()

    if not image1_path or not image2_path:
        return json.dumps({"error": "Both image1_path and image2_path are required."})

    if not os.path.isfile(image1_path):
        return json.dumps({"error": f"Image 1 not found: {image1_path}"})

    if not os.path.isfile(image2_path):
        return json.dumps({"error": f"Image 2 not found: {image2_path}"})

    try:
        # Load and normalize
        img1 = _load_and_normalize(image1_path)
        img2 = _load_and_normalize(image2_path)

        # Resize to match if needed
        img1, img2, size_mismatch = _resize_to_match(img1, img2)

        # Compute diff
        diff_result = _compute_diff(img1, img2, pixel_tolerance)

        # Determine output path
        if not output_diff_path:
            Path(DIFF_OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
            base1 = Path(image1_path).stem
            base2 = Path(image2_path).stem
            output_diff_path = os.path.join(
                DIFF_OUTPUT_DIR, f"diff-{base1}-vs-{base2}.png"
            )

        # Save diff image
        diff_image_path = _save_diff_image(diff_result["diff_image"], output_diff_path)

        # Verdict
        verdict = "PASS" if diff_result["diff_percentage"] <= threshold else "FAIL"

        result = {
            "verdict": verdict,
            "diff_percentage": diff_result["diff_percentage"],
            "threshold": threshold,
            "diff_pixels": diff_result["diff_pixels"],
            "total_pixels": diff_result["total_pixels"],
            "max_channel_diff": diff_result["max_channel_diff"],
            "pixel_tolerance": pixel_tolerance,
            "dimensions": diff_result["dimensions"],
            "diff_image_path": diff_image_path,
            "image1_path": image1_path,
            "image2_path": image2_path,
        }

        if size_mismatch:
            result["size_mismatch"] = size_mismatch

        return json.dumps(result, indent=2)

    except Exception as e:
        return json.dumps({"error": f"Failed to compare images: {e}"})


@mcp.tool()
def compare_urls(
    url1: str,
    url2: str,
    output_diff_path: str = "",
    viewport_width: int = 1280,
    viewport_height: int = 720,
    pixel_tolerance: int = DEFAULT_PIXEL_TOLERANCE,
    threshold: float = DEFAULT_THRESHOLD,
) -> str:
    """Compare two web pages by taking screenshots and running a pixel diff.

    Takes full-page screenshots of both URLs using Playwright, then runs the
    same pixel comparison as compare_images. Useful for comparing a design
    reference URL against a deployed site.

    Requires Playwright to be installed (npx playwright install chromium).

    Args:
        url1: URL of the reference/baseline page.
        url2: URL of the comparison page.
        output_diff_path: Path to save the diff visualization image. If empty,
                          auto-generates a path in the temp directory.
        viewport_width: Browser viewport width in pixels. Default 1280.
        viewport_height: Browser viewport height in pixels. Default 720.
        pixel_tolerance: Per-channel tolerance (0-255). Default 10.
        threshold: Diff percentage above which the comparison fails. Default 5.0.

    Returns:
        JSON string with diff_percentage, verdict, screenshot paths, and
        diff_image_path.
    """
    url1 = url1.strip()
    url2 = url2.strip()
    output_diff_path = output_diff_path.strip()

    if not url1 or not url2:
        return json.dumps({"error": "Both url1 and url2 are required."})

    try:
        # Create temp directory for screenshots
        screenshots_dir = os.path.join(DIFF_OUTPUT_DIR, "screenshots")
        Path(screenshots_dir).mkdir(parents=True, exist_ok=True)

        # Sanitize URLs for filenames
        def _url_to_filename(url: str) -> str:
            clean = url.replace("https://", "").replace("http://", "")
            clean = clean.replace("/", "_").replace(":", "_").replace("?", "_")
            return clean[:80]

        shot1_path = os.path.join(screenshots_dir, f"shot1-{_url_to_filename(url1)}.png")
        shot2_path = os.path.join(screenshots_dir, f"shot2-{_url_to_filename(url2)}.png")

        # Take screenshots
        _screenshot_url(url1, shot1_path, viewport_width, viewport_height)
        _screenshot_url(url2, shot2_path, viewport_width, viewport_height)

        # Load and normalize
        img1 = _load_and_normalize(shot1_path)
        img2 = _load_and_normalize(shot2_path)

        # Resize to match if needed
        img1, img2, size_mismatch = _resize_to_match(img1, img2)

        # Compute diff
        diff_result = _compute_diff(img1, img2, pixel_tolerance)

        # Determine output path
        if not output_diff_path:
            output_diff_path = os.path.join(
                DIFF_OUTPUT_DIR, f"diff-url-compare.png"
            )

        # Save diff image
        diff_image_path = _save_diff_image(diff_result["diff_image"], output_diff_path)

        # Verdict
        verdict = "PASS" if diff_result["diff_percentage"] <= threshold else "FAIL"

        result = {
            "verdict": verdict,
            "diff_percentage": diff_result["diff_percentage"],
            "threshold": threshold,
            "diff_pixels": diff_result["diff_pixels"],
            "total_pixels": diff_result["total_pixels"],
            "max_channel_diff": diff_result["max_channel_diff"],
            "pixel_tolerance": pixel_tolerance,
            "dimensions": diff_result["dimensions"],
            "diff_image_path": diff_image_path,
            "screenshot1_path": shot1_path,
            "screenshot2_path": shot2_path,
            "url1": url1,
            "url2": url2,
            "viewport": f"{viewport_width}x{viewport_height}",
        }

        if size_mismatch:
            result["size_mismatch"] = size_mismatch

        return json.dumps(result, indent=2)

    except Exception as e:
        return json.dumps({"error": f"Failed to compare URLs: {e}"})


@mcp.tool()
def generate_diff_report(
    image1_path: str,
    image2_path: str,
    output_diff_path: str = "",
    pixel_tolerance: int = DEFAULT_PIXEL_TOLERANCE,
    threshold: float = DEFAULT_THRESHOLD,
    report_output_path: str = "",
) -> str:
    """Generate a structured diff report comparing two images for design QC.

    Runs the pixel comparison and produces a detailed markdown report with:
    - Pass/fail verdict with severity rating
    - Quantitative diff metrics
    - Region analysis (which quadrants have the most differences)
    - Recommendations

    Args:
        image1_path: Path to the reference/baseline image.
        image2_path: Path to the comparison image.
        output_diff_path: Path to save the diff visualization image.
        pixel_tolerance: Per-channel tolerance (0-255). Default 10.
        threshold: Diff percentage above which the comparison fails. Default 5.0.
        report_output_path: Path to save the markdown report. If empty,
                            auto-generates in the temp directory.

    Returns:
        JSON string with verdict, severity, metrics, region_analysis,
        report_path, and diff_image_path.
    """
    image1_path = image1_path.strip()
    image2_path = image2_path.strip()
    output_diff_path = output_diff_path.strip()
    report_output_path = report_output_path.strip()

    if not image1_path or not image2_path:
        return json.dumps({"error": "Both image1_path and image2_path are required."})

    if not os.path.isfile(image1_path):
        return json.dumps({"error": f"Image 1 not found: {image1_path}"})

    if not os.path.isfile(image2_path):
        return json.dumps({"error": f"Image 2 not found: {image2_path}"})

    try:
        # Load and normalize
        img1 = _load_and_normalize(image1_path)
        img2 = _load_and_normalize(image2_path)

        # Resize to match
        img1, img2, size_mismatch = _resize_to_match(img1, img2)

        # Compute diff
        diff_result = _compute_diff(img1, img2, pixel_tolerance)

        # Save diff image
        if not output_diff_path:
            Path(DIFF_OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
            base1 = Path(image1_path).stem
            base2 = Path(image2_path).stem
            output_diff_path = os.path.join(
                DIFF_OUTPUT_DIR, f"diff-{base1}-vs-{base2}.png"
            )
        diff_image_path = _save_diff_image(diff_result["diff_image"], output_diff_path)

        # Verdict and severity
        diff_pct = diff_result["diff_percentage"]
        if diff_pct <= threshold:
            verdict = "PASS"
            severity = "none"
        elif diff_pct <= threshold * 2:
            verdict = "FAIL"
            severity = "minor"
        elif diff_pct <= threshold * 5:
            verdict = "FAIL"
            severity = "moderate"
        else:
            verdict = "FAIL"
            severity = "major"

        # Region analysis — divide into 4 quadrants
        w, h = img1.size
        mid_x, mid_y = w // 2, h // 2
        px1 = img1.load()
        px2 = img2.load()

        quadrants = {
            "top_left": {"diff": 0, "total": 0},
            "top_right": {"diff": 0, "total": 0},
            "bottom_left": {"diff": 0, "total": 0},
            "bottom_right": {"diff": 0, "total": 0},
        }

        for y in range(h):
            for x in range(w):
                r1, g1, b1, a1 = px1[x, y]
                r2, g2, b2, a2 = px2[x, y]
                channel_max = max(abs(r1 - r2), abs(g1 - g2), abs(b1 - b2), abs(a1 - a2))
                is_diff = channel_max > pixel_tolerance

                if x < mid_x and y < mid_y:
                    q = "top_left"
                elif x >= mid_x and y < mid_y:
                    q = "top_right"
                elif x < mid_x and y >= mid_y:
                    q = "bottom_left"
                else:
                    q = "bottom_right"

                quadrants[q]["total"] += 1
                if is_diff:
                    quadrants[q]["diff"] += 1

        region_analysis = {}
        hotspot = None
        hotspot_pct = 0
        for name, data in quadrants.items():
            pct = round(data["diff"] / data["total"] * 100, 2) if data["total"] > 0 else 0
            region_analysis[name] = {
                "diff_pixels": data["diff"],
                "total_pixels": data["total"],
                "diff_percentage": pct,
            }
            if pct > hotspot_pct:
                hotspot_pct = pct
                hotspot = name

        # Generate markdown report
        report_lines = [
            f"# Image Comparison Report",
            f"",
            f"## Verdict: **{verdict}** ({severity})",
            f"",
            f"| Metric | Value |",
            f"|--------|-------|",
            f"| Diff Percentage | {diff_pct}% |",
            f"| Threshold | {threshold}% |",
            f"| Diff Pixels | {diff_result['diff_pixels']:,} / {diff_result['total_pixels']:,} |",
            f"| Max Channel Diff | {diff_result['max_channel_diff']} / 255 |",
            f"| Pixel Tolerance | {pixel_tolerance} |",
            f"| Dimensions | {diff_result['dimensions']} |",
            f"",
            f"## Images",
            f"",
            f"- **Reference:** `{image1_path}`",
            f"- **Comparison:** `{image2_path}`",
            f"- **Diff overlay:** `{diff_image_path}`",
            f"",
        ]

        if size_mismatch:
            report_lines.extend([
                f"## Size Mismatch Warning",
                f"",
                f"- Image 1: {size_mismatch['image1_size']}",
                f"- Image 2: {size_mismatch['image2_size']}",
                f"- {size_mismatch['note']}",
                f"",
            ])

        report_lines.extend([
            f"## Region Analysis",
            f"",
            f"| Quadrant | Diff % | Diff Pixels |",
            f"|----------|--------|-------------|",
        ])
        for name, data in region_analysis.items():
            label = name.replace("_", " ").title()
            marker = " **[HOTSPOT]**" if name == hotspot and data["diff_percentage"] > 0 else ""
            report_lines.append(
                f"| {label} | {data['diff_percentage']}% | {data['diff_pixels']:,}{marker} |"
            )

        report_lines.extend([
            f"",
            f"## Recommendations",
            f"",
        ])

        if verdict == "PASS":
            report_lines.append("Images match within acceptable tolerance. No action required.")
        else:
            if hotspot:
                report_lines.append(f"- Focus review on the **{hotspot.replace('_', ' ')}** region ({hotspot_pct}% diff).")
            if size_mismatch:
                report_lines.append("- Resolve the dimension mismatch between reference and comparison images.")
            if severity == "major":
                report_lines.append("- Major discrepancies detected. Full design review recommended.")
            elif severity == "moderate":
                report_lines.append("- Moderate discrepancies. Check layout shifts, color changes, and missing elements.")
            else:
                report_lines.append("- Minor discrepancies. May be anti-aliasing or sub-pixel rendering differences.")

        report_text = "\n".join(report_lines) + "\n"

        # Save report
        if not report_output_path:
            Path(DIFF_OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
            report_output_path = os.path.join(DIFF_OUTPUT_DIR, "diff-report.md")
        _ensure_dir(report_output_path)
        with open(report_output_path, "w") as f:
            f.write(report_text)

        result = {
            "verdict": verdict,
            "severity": severity,
            "diff_percentage": diff_pct,
            "threshold": threshold,
            "diff_pixels": diff_result["diff_pixels"],
            "total_pixels": diff_result["total_pixels"],
            "max_channel_diff": diff_result["max_channel_diff"],
            "pixel_tolerance": pixel_tolerance,
            "dimensions": diff_result["dimensions"],
            "diff_image_path": diff_image_path,
            "report_path": report_output_path,
            "region_analysis": region_analysis,
            "hotspot": hotspot,
            "image1_path": image1_path,
            "image2_path": image2_path,
        }

        if size_mismatch:
            result["size_mismatch"] = size_mismatch

        return json.dumps(result, indent=2)

    except Exception as e:
        return json.dumps({"error": f"Failed to generate diff report: {e}"})


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run()
