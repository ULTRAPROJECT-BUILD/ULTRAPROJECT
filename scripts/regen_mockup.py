#!/usr/bin/env python3
"""Re-render a mockup HTML file through headless Chromium and capture a PNG."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
import time
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
RENDER_CACHE_DIR = REPO_ROOT / "vault" / "cache" / "visual-spec" / "render"
VIEWPORT_RE = re.compile(r"^(\d+)x(\d+)$")


class DependencyError(RuntimeError):
    """Raised when Playwright or its Chromium browser is unavailable."""


def sha256_file(path: Path) -> str:
    """Return the content SHA-256 for a file."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_viewport(value: str) -> tuple[int, int]:
    """Parse a viewport string in WxH form."""
    match = VIEWPORT_RE.match(value.strip())
    if not match:
        raise ValueError(f"Invalid viewport {value!r}; expected WxH, for example 1440x900.")
    width, height = int(match.group(1)), int(match.group(2))
    if width <= 0 or height <= 0:
        raise ValueError("Viewport width and height must be positive.")
    return width, height


def render_png(html_path: Path, out_png: Path, width: int, height: int) -> None:
    """Render a local HTML file to a PNG using Playwright Chromium."""
    try:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise DependencyError(
            "regen_mockup.py requires Playwright. Install with: "
            "python3 -m pip install playwright && python3 -m playwright install chromium"
        ) from exc

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            context = browser.new_context(
                viewport={"width": width, "height": height},
                device_scale_factor=2,
            )
            page = context.new_page()
            page.goto(html_path.as_uri())
            page.wait_for_load_state("networkidle")
            page.screenshot(path=str(out_png), full_page=False)
            browser.close()
    except PlaywrightError as exc:
        message = str(exc)
        if "Executable doesn't exist" in message or "playwright install" in message.lower():
            raise DependencyError(
                "Playwright Chromium is not installed. Run: python3 -m playwright install chromium"
            ) from exc
        if "MachPortRendezvous" in message or "Permission denied" in message:
            raise RuntimeError(
                "Playwright Chromium launch was blocked by OS or sandbox permissions "
                "(MachPortRendezvous permission denied). Run this helper from an unrestricted "
                "terminal session or grant the required Chromium/Playwright permissions."
            ) from exc
        first_line = message.strip().splitlines()[0] if message.strip() else "unknown Playwright error"
        raise RuntimeError(f"Playwright render failed: {first_line}") from exc


def regenerate_mockup(html: Path, out_png: Path, viewport: str = "1440x900", *, use_cache: bool = False) -> dict[str, Any]:
    """Render HTML to PNG, optionally using the visual-spec render cache."""
    html_path = html.expanduser().resolve()
    out_path = out_png.expanduser().resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    width, height = parse_viewport(viewport)
    start = time.perf_counter()
    cached = False

    content_hash = sha256_file(html_path)
    cache_png = RENDER_CACHE_DIR / f"{content_hash}.png"
    cache_meta = RENDER_CACHE_DIR / f"{content_hash}.json"
    html_mtime_ns = html_path.stat().st_mtime_ns

    if use_cache and cache_png.exists() and cache_meta.exists():
        try:
            meta = json.loads(cache_meta.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            meta = {}
        if meta.get("html_mtime_ns") == html_mtime_ns and meta.get("viewport") == f"{width}x{height}":
            if cache_png.resolve() != out_path:
                shutil.copyfile(cache_png, out_path)
            cached = True

    if not cached:
        render_png(html_path, out_path, width, height)
        if use_cache:
            RENDER_CACHE_DIR.mkdir(parents=True, exist_ok=True)
            if cache_png.resolve() != out_path:
                shutil.copyfile(out_path, cache_png)
            cache_meta.write_text(
                json.dumps(
                    {
                        "html": str(html_path),
                        "html_mtime_ns": html_mtime_ns,
                        "viewport": f"{width}x{height}",
                    },
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )

    return {
        "html": str(html_path),
        "out_png": str(out_path),
        "viewport": f"{width}x{height}",
        "cached": cached,
        "render_seconds": round(time.perf_counter() - start, 3),
    }


def write_json(data: dict[str, Any]) -> None:
    """Write JSON to stdout."""
    sys.stdout.write(json.dumps(data, indent=2, sort_keys=True) + "\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--html", required=True, help="HTML file to render.")
    parser.add_argument("--out-png", required=True, help="PNG output path.")
    parser.add_argument("--viewport", default="1440x900", help="Viewport in WxH form. Default: 1440x900.")
    parser.add_argument("--cache", action="store_true", help="Use the visual-spec render cache.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        data = regenerate_mockup(Path(args.html), Path(args.out_png), args.viewport, use_cache=args.cache)
    except DependencyError as exc:
        data = {"error": str(exc)}
        write_json(data)
        print(str(exc), file=sys.stderr)
        return 2
    except Exception as exc:
        data = {"error": str(exc)}
        write_json(data)
        return 1
    write_json(data)
    return 0


if __name__ == "__main__":
    sys.exit(main())
