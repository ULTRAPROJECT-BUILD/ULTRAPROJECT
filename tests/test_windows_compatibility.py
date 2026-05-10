from __future__ import annotations

import argparse
import os
import shlex
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import capture_walkthrough_video
import platform_support
import verify_release


def shell_command(parts: list[str]) -> str:
    if os.name == "nt":
        return subprocess.list2cmdline(parts)
    return " ".join(shlex.quote(part) for part in parts)


def desktop_args() -> argparse.Namespace:
    return argparse.Namespace(
        duration=5.0,
        display_id=1,
        fps=12,
        audio_device="none",
        scale_width=1600,
    )


def test_detect_host_identifies_windows_and_wsl():
    windows = platform_support.detect_host(system="Windows", release="10", env={})
    assert windows.name == "windows"
    assert windows.is_windows is True
    assert platform_support.shell_run_kwargs(windows) == {"shell": True}

    wsl = platform_support.detect_host(
        system="Linux",
        release="5.15.90.1-microsoft-standard-WSL2",
        env={"WSL_DISTRO_NAME": "Ubuntu"},
    )
    assert wsl.name == "wsl"
    assert wsl.is_linux is True
    assert wsl.is_wsl is True


def test_launcher_command_is_host_specific():
    target = Path("demo-app.exe")
    windows = platform_support.detect_host(system="Windows", release="10", env={})
    macos = platform_support.detect_host(system="Darwin", release="23.0.0", env={})

    assert platform_support.launcher_command_for_path(target, windows) is None
    assert platform_support.launcher_command_for_path(target, macos) == ["open", str(target)]


def test_verify_release_command_runner_uses_available_native_shell(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    command = shell_command([sys.executable, "-c", "print('verify-ok')"])

    result = verify_release.run_command(command, source, timeout_seconds=30)

    assert result["status"] == "PASS"
    assert result["exit_code"] == 0
    assert "verify-ok" in result["stdout_tail"]


def test_desktop_capture_command_uses_windows_gdigrab_backend():
    output = Path("walkthrough.mp4")

    command = capture_walkthrough_video.build_desktop_capture_command(
        desktop_args(),
        "ffmpeg",
        output,
        backend="gdigrab",
    )

    assert command[:5] == ["ffmpeg", "-y", "-f", "gdigrab", "-framerate"]
    assert "desktop" in command
    assert str(output) == command[-1]


def test_desktop_capture_command_keeps_macos_avfoundation_backend():
    command = capture_walkthrough_video.build_desktop_capture_command(
        desktop_args(),
        "ffmpeg",
        Path("walkthrough.mp4"),
        backend="avfoundation",
    )

    assert "avfoundation" in command
    assert "1:none" in command


def test_desktop_capture_command_supports_linux_x11grab_backend(monkeypatch):
    monkeypatch.setenv("DISPLAY", ":99")
    monkeypatch.setenv("ONESHOT_X11_VIDEO_SIZE", "1280x720")

    command = capture_walkthrough_video.build_desktop_capture_command(
        desktop_args(),
        "ffmpeg",
        Path("walkthrough.mp4"),
        backend="x11grab",
    )

    assert "x11grab" in command
    assert "1280x720" in command
    assert ":99" in command
