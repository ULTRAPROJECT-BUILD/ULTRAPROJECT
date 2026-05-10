#!/usr/bin/env python3
"""
Capture short walkthrough videos for browser/web and desktop/native artifacts.

Examples:
  python3 scripts/capture_walkthrough_video.py web \
    --url http://localhost:4173 \
    --output /tmp/qc-walkthrough.mp4 \
    --duration 8 \
    --scroll

  python3 scripts/capture_walkthrough_video.py desktop \
    --output /tmp/qc-walkthrough.mp4 \
    --duration 8 \
    --display-id 0
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from platform_support import desktop_capture_backend


def base_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="mode", required=True)

    web = subparsers.add_parser("web", help="Record a browser/web walkthrough using Playwright video.")
    web.add_argument("--url", required=True, help="URL or file:// URL to record.")
    web.add_argument("--output", required=True, help="Output path (.webm, .mp4, or .mov).")
    web.add_argument("--duration", type=float, default=8.0, help="Total recording duration in seconds.")
    web.add_argument("--viewport-width", type=int, default=1440, help="Viewport width.")
    web.add_argument("--viewport-height", type=int, default=900, help="Viewport height.")
    web.add_argument(
        "--wait-until",
        choices=("load", "domcontentloaded", "networkidle"),
        default="networkidle",
        help="Navigation readiness condition.",
    )
    web.add_argument("--ready-selector", help="Optional selector that must appear before recording settles.")
    web.add_argument("--timeout-ms", type=int, default=30000, help="Selector/navigation timeout.")
    web.add_argument("--wait-ms", type=int, default=1000, help="Extra dwell time after load.")
    web.add_argument("--scroll", action="store_true", help="Auto-scroll through the page during the recording.")
    web.add_argument("--scroll-steps", type=int, default=8, help="Auto-scroll step count.")

    desktop = subparsers.add_parser("desktop", help="Record the desktop/native app surface via ffmpeg.")
    desktop.add_argument("--output", help="Output path (.mp4, .mov, or .webm).")
    desktop.add_argument("--duration", type=float, default=8.0, help="Total recording duration in seconds.")
    desktop.add_argument("--display-id", type=int, default=0, help="AVFoundation display ID (macOS only).")
    desktop.add_argument("--fps", type=int, default=12, help="Capture framerate.")
    desktop.add_argument("--audio-device", default="none", help="AVFoundation audio device ID or 'none' (macOS only).")
    desktop.add_argument(
        "--scale-width",
        type=int,
        default=1600,
        help="Optional max output width for smaller review artifacts. Set 0 to disable scaling.",
    )
    desktop.add_argument("--list-devices", action="store_true", help="Print desktop capture backend device info and exit.")
    return parser


def require_ffmpeg() -> str:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise SystemExit("ffmpeg is required but was not found in PATH.")
    return ffmpeg


def run(cmd: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, text=True, capture_output=True, check=check)


def ensure_parent(path: Path) -> None:
    path.expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)


def transcode_video(source: Path, output: Path) -> None:
    ffmpeg = require_ffmpeg()
    ensure_parent(output)
    output = output.expanduser().resolve()
    suffix = output.suffix.lower()

    if suffix == ".webm":
        cmd = [ffmpeg, "-y", "-i", str(source), "-c:v", "libvpx-vp9", "-b:v", "0", "-crf", "32", str(output)]
    else:
        cmd = [
            ffmpeg,
            "-y",
            "-i",
            str(source),
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(output),
        ]
    result = run(cmd, check=False)
    if result.returncode != 0:
        raise SystemExit(f"Video transcode failed:\n{result.stderr}")


def auto_scroll(page, duration_ms: int, steps: int) -> None:
    if duration_ms <= 0:
        return
    max_scroll = page.evaluate(
        """
        () => {
          const height = Math.max(
            document.body.scrollHeight,
            document.documentElement.scrollHeight,
            document.body.offsetHeight,
            document.documentElement.offsetHeight
          );
          return Math.max(0, height - window.innerHeight);
        }
        """
    )
    if not max_scroll:
        page.wait_for_timeout(duration_ms)
        return

    pause_ms = max(250, int(duration_ms / max(1, steps)))
    for index in range(steps):
        y = int(max_scroll * (index + 1) / steps)
        page.evaluate("(value) => window.scrollTo({ top: value, behavior: 'instant' })", y)
        page.wait_for_timeout(pause_ms)


def record_web(args: argparse.Namespace) -> Path:
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:  # pragma: no cover - surfaced in validation
        raise SystemExit(f"Playwright is required for web walkthrough capture: {exc}")

    output = Path(args.output).expanduser().resolve()
    ensure_parent(output)
    with tempfile.TemporaryDirectory(prefix="walkthrough-video-") as video_dir_str:
        video_dir = Path(video_dir_str)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            context = browser.new_context(
                viewport={"width": args.viewport_width, "height": args.viewport_height},
                record_video_dir=str(video_dir),
                record_video_size={"width": args.viewport_width, "height": args.viewport_height},
            )
            page = context.new_page()
            video = page.video
            started = time.monotonic()
            page.goto(args.url, wait_until=args.wait_until, timeout=args.timeout_ms)
            if args.ready_selector:
                page.wait_for_selector(args.ready_selector, timeout=args.timeout_ms)
            if args.wait_ms:
                page.wait_for_timeout(args.wait_ms)
            if args.scroll:
                elapsed_ms = int((time.monotonic() - started) * 1000)
                remaining_ms = max(0, int(args.duration * 1000) - elapsed_ms)
                auto_scroll(page, remaining_ms, args.scroll_steps)
            elapsed = time.monotonic() - started
            if elapsed < args.duration:
                page.wait_for_timeout(int((args.duration - elapsed) * 1000))
            page.close()
            context.close()
            browser.close()

            source = Path(video.path())

        if output.suffix.lower() == ".webm":
            shutil.copy2(source, output)
        else:
            transcode_video(source, output)
    return output


def list_desktop_devices() -> int:
    ffmpeg = require_ffmpeg()
    backend = desktop_capture_backend()
    if backend == "avfoundation":
        result = run([ffmpeg, "-f", "avfoundation", "-list_devices", "true", "-i", ""], check=False)
        text = result.stderr or result.stdout
        print(text.strip())
    elif backend == "gdigrab":
        print("Windows desktop capture uses ffmpeg gdigrab input: desktop")
    elif backend == "x11grab":
        display = os.environ.get("ONESHOT_X11_DISPLAY") or os.environ.get("DISPLAY") or ":0.0"
        size = os.environ.get("ONESHOT_X11_VIDEO_SIZE") or "1920x1080"
        print(f"Linux desktop capture uses ffmpeg x11grab display={display} video_size={size}")
    else:
        raise SystemExit(f"Unsupported desktop capture backend: {backend}")
    return 0


def build_desktop_capture_command(args: argparse.Namespace, ffmpeg: str, temp_output: Path, backend: str | None = None) -> list[str]:
    resolved_backend = backend or desktop_capture_backend()
    if resolved_backend == "avfoundation":
        input_spec = f"{args.display_id}:{args.audio_device}"
        cmd = [
            ffmpeg,
            "-y",
            "-f",
            "avfoundation",
            "-framerate",
            str(args.fps),
            "-i",
            input_spec,
            "-t",
            str(args.duration),
        ]
    elif resolved_backend == "gdigrab":
        cmd = [
            ffmpeg,
            "-y",
            "-f",
            "gdigrab",
            "-framerate",
            str(args.fps),
            "-i",
            "desktop",
            "-t",
            str(args.duration),
        ]
    elif resolved_backend == "x11grab":
        display = os.environ.get("ONESHOT_X11_DISPLAY") or os.environ.get("DISPLAY")
        if not display:
            raise SystemExit("Linux desktop capture requires DISPLAY or ONESHOT_X11_DISPLAY.")
        video_size = os.environ.get("ONESHOT_X11_VIDEO_SIZE") or "1920x1080"
        cmd = [
            ffmpeg,
            "-y",
            "-f",
            "x11grab",
            "-video_size",
            video_size,
            "-framerate",
            str(args.fps),
            "-i",
            display,
            "-t",
            str(args.duration),
        ]
    else:
        raise SystemExit(f"Unsupported desktop capture backend: {resolved_backend}")

    if args.scale_width and args.scale_width > 0:
        cmd.extend(["-vf", f"scale=min(iw\\,{args.scale_width}):-2"])
    cmd.extend(
        [
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(temp_output),
        ]
    )
    return cmd


def record_desktop(args: argparse.Namespace) -> Path:
    ffmpeg = require_ffmpeg()
    output = Path(args.output).expanduser().resolve()
    ensure_parent(output)
    if output.suffix.lower() == ".mp4":
        temp_output = output
    else:
        fd, temp_name = tempfile.mkstemp(suffix=".mp4", prefix="desktop-walkthrough-")
        os.close(fd)
        temp_output = Path(temp_name)

    cmd = build_desktop_capture_command(args, ffmpeg, temp_output)
    result = run(cmd, check=False)
    if result.returncode != 0:
        raise SystemExit(f"Desktop walkthrough capture failed:\n{result.stderr}")

    if temp_output != output:
        transcode_video(temp_output, output)
        temp_output.unlink(missing_ok=True)
    return output


def main() -> int:
    parser = base_parser()
    args = parser.parse_args()

    if args.mode == "desktop" and args.list_devices:
        return list_desktop_devices()
    if args.mode == "desktop" and not args.output:
        raise SystemExit("--output is required unless --list-devices is used.")

    if args.mode == "web":
        output = record_web(args)
    else:
        output = record_desktop(args)

    print(f"mode={args.mode}")
    print(f"output={output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
