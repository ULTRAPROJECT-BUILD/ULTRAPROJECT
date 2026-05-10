#!/usr/bin/env python3
from __future__ import annotations

"""Small cross-platform helpers for OneShot scripts.

The project mostly runs as plain Python, but a few operational helpers need to
choose a shell, launcher, or capture backend. Keep that logic centralized so
Windows/macOS/Linux behavior stays explicit and testable.
"""

import os
import platform
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Mapping


@dataclass(frozen=True)
class HostPlatform:
    system: str
    release: str
    is_windows: bool
    is_macos: bool
    is_linux: bool
    is_wsl: bool

    @property
    def name(self) -> str:
        if self.is_wsl:
            return "wsl"
        if self.is_windows:
            return "windows"
        if self.is_macos:
            return "macos"
        if self.is_linux:
            return "linux"
        return self.system.lower() or "unknown"


def detect_host(
    *,
    system: str | None = None,
    release: str | None = None,
    env: Mapping[str, str] | None = None,
) -> HostPlatform:
    env_map = env if env is not None else os.environ
    raw_system = system if system is not None else platform.system()
    raw_release = release if release is not None else platform.release()
    normalized = raw_system.lower()
    release_text = raw_release.lower()
    is_windows = normalized == "windows"
    is_macos = normalized == "darwin"
    is_linux = normalized == "linux"
    is_wsl = is_linux and (
        bool(env_map.get("WSL_DISTRO_NAME"))
        or bool(env_map.get("WSL_INTEROP"))
        or "microsoft" in release_text
        or "wsl" in release_text
    )
    return HostPlatform(
        system=raw_system,
        release=raw_release,
        is_windows=is_windows,
        is_macos=is_macos,
        is_linux=is_linux,
        is_wsl=is_wsl,
    )


def shell_run_kwargs(host: HostPlatform | None = None) -> dict:
    """Return kwargs for subprocess.run(..., shell=True) on this host.

    Windows should use the default shell chosen by Python/COMSPEC. Supplying a
    POSIX executable such as /bin/zsh makes native Windows runs fail before the
    command starts.
    """
    resolved = host or detect_host()
    if resolved.is_windows:
        return {"shell": True}

    preferred_shell = (
        os.environ.get("SHELL")
        or shutil.which("zsh")
        or shutil.which("bash")
        or shutil.which("sh")
    )
    if preferred_shell:
        return {"shell": True, "executable": preferred_shell}
    return {"shell": True}


def local_iso_minute() -> str:
    return datetime.now().astimezone().strftime("%Y-%m-%dT%H:%M")


def launcher_command_for_path(path: Path, host: HostPlatform | None = None) -> list[str] | None:
    resolved = host or detect_host()
    target = str(path)
    if resolved.is_windows:
        return None
    if resolved.is_macos:
        return ["open", target]
    opener = shutil.which("xdg-open")
    if opener:
        return [opener, target]
    return None


def launch_path(path: Path, host: HostPlatform | None = None) -> str:
    resolved = host or detect_host()
    if resolved.is_windows:
        os.startfile(str(path))  # type: ignore[attr-defined]
        return "startfile"

    command = launcher_command_for_path(path, resolved)
    if not command:
        raise RuntimeError(
            f"No desktop launcher is available for {resolved.name}; "
            "open the app manually or install xdg-open."
        )
    subprocess.run(command, check=False)
    return " ".join(command)


def desktop_capture_backend(host: HostPlatform | None = None) -> str:
    resolved = host or detect_host()
    if resolved.is_windows:
        return "gdigrab"
    if resolved.is_macos:
        return "avfoundation"
    if resolved.is_linux:
        return "x11grab"
    raise RuntimeError(f"Desktop capture is not configured for {resolved.system or 'this OS'}.")
