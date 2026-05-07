"""
Computer Use MCP Server

Wraps macOS native tools as an MCP server so platform agents can see and
interact with the desktop — screenshot, click, type, scroll, drag, and
press keys.

Implementation:
  - Screenshots: macOS `screencapture` (requires Screen Recording permission)
  - Mouse/keyboard: `cliclick` (requires Accessibility permission)
  - Scroll: `cliclick` scroll via osascript CGEvent helper
  - Screen size: osascript + AppKit (no pip dependencies)

Prerequisites:
  - brew install cliclick
  - Grant Terminal/IDE Accessibility permission (System Settings > Privacy)
  - Grant Terminal/IDE Screen Recording permission (System Settings > Privacy)

Tools:
  - screenshot        — capture the current screen, returns base64 PNG
  - mouse_click       — click at (x, y) with button and click type
  - mouse_move        — move cursor to (x, y)
  - mouse_drag        — drag from (x1, y1) to (x2, y2)
  - mouse_down        — press and hold mouse button at (x, y)
  - mouse_up          — release mouse button at (x, y)
  - keyboard_type     — type a string of text
  - keyboard_key      — press a key or key combo (e.g. "cmd+s", "Return")
  - scroll            — scroll at (x, y) in a direction by amount
  - get_screen_size   — returns display width and height in pixels
  - wait              — pause for a specified duration (seconds)
"""

from __future__ import annotations

import base64
import os
import subprocess
import tempfile
import time

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("computer-use")

# Cache cliclick path
_cliclick_path: str | None = None

# Exact key names cliclick kp: accepts (from cliclick -h)
_CLICLICK_NAMED_KEYS = {
    "arrow-down", "arrow-left", "arrow-right", "arrow-up",
    "brightness-down", "brightness-up",
    "delete", "end", "enter", "esc",
    "f1", "f2", "f3", "f4", "f5", "f6", "f7", "f8",
    "f9", "f10", "f11", "f12", "f13", "f14", "f15", "f16",
    "fwd-delete", "home",
    "keys-light-down", "keys-light-toggle", "keys-light-up",
    "mute",
    "num-0", "num-1", "num-2", "num-3", "num-4",
    "num-5", "num-6", "num-7", "num-8", "num-9",
    "num-clear", "num-divide", "num-enter", "num-equals",
    "num-minus", "num-multiply", "num-plus",
    "page-down", "page-up",
    "play-next", "play-pause", "play-previous",
    "return", "space", "tab",
    "volume-down", "volume-up",
}

# Keys valid only for kd:/ku: (modifiers), not kp:
_CLICLICK_MODIFIER_KEYS = {"alt", "cmd", "ctrl", "fn", "shift"}

# Map user-friendly key names to cliclick key names
_KEY_ALIASES = {
    "return": "return", "enter": "return",
    "escape": "esc", "esc": "esc",
    "tab": "tab", "space": "space",
    "delete": "delete", "backspace": "delete",
    "up": "arrow-up", "down": "arrow-down",
    "left": "arrow-left", "right": "arrow-right",
    "pageup": "page-up", "pagedown": "page-down",
    "home": "home", "end": "end",
}


def _run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    """Run a subprocess with timeout."""
    return subprocess.run(cmd, capture_output=True, text=True, timeout=15, check=check)


def _get_cliclick() -> str:
    """Return path to cliclick, raising with install instructions if missing."""
    global _cliclick_path
    if _cliclick_path:
        return _cliclick_path
    result = subprocess.run(["which", "cliclick"], capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            "cliclick is not installed. Run: brew install cliclick\n"
            "Then grant Accessibility permission to Terminal in "
            "System Settings > Privacy & Security > Accessibility."
        )
    _cliclick_path = result.stdout.strip()
    return _cliclick_path


def _ok(message: str) -> dict:
    """Standard success response."""
    return {"success": True, "message": message}


def _err(message: str) -> dict:
    """Standard error response."""
    return {"success": False, "error": message}


def _cli(args: list[str]) -> dict:
    """Run cliclick with args, return structured response."""
    try:
        cli = _get_cliclick()
    except RuntimeError as e:
        return _err(str(e))
    try:
        result = _run([cli] + args)
        return _ok(result.stdout.strip() if result.stdout.strip() else "OK")
    except subprocess.CalledProcessError as e:
        return _err(f"cliclick failed: {e.stderr.strip()}")
    except subprocess.TimeoutExpired:
        return _err("cliclick timed out")


def _resolve_key(key: str) -> str | None:
    """Resolve a user key name to a cliclick key name. Returns None if not a named key."""
    lower = key.lower()
    # Check aliases first
    aliased = _KEY_ALIASES.get(lower, lower)
    if aliased in _CLICLICK_NAMED_KEYS:
        return aliased
    return None


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@mcp.tool()
def screenshot(display: int = 1) -> dict:
    """
    Capture a screenshot of the current screen.

    Returns dict with 'success' and 'image' (base64 PNG) keys.
    Requires Screen Recording permission for Terminal.

    Args:
        display: Display number (default 1, the main display)
    """
    if not isinstance(display, int) or display < 1:
        return _err("display must be a positive integer")

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        tmp_path = f.name

    try:
        result = _run(
            ["screencapture", "-x", "-C", f"-D{display}", tmp_path],
            check=False,
        )
        if result.returncode != 0:
            return _err(f"screencapture failed: {result.stderr.strip()}")
        if not os.path.exists(tmp_path) or os.path.getsize(tmp_path) == 0:
            return _err(
                "Screenshot is empty. Check Screen Recording permission in "
                "System Settings > Privacy & Security > Screen & System Audio Recording."
            )
        with open(tmp_path, "rb") as f:
            data = f.read()
        return {"success": True, "image": base64.b64encode(data).decode("ascii")}
    except subprocess.TimeoutExpired:
        return _err("screencapture timed out")
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


@mcp.tool()
def get_screen_size() -> dict:
    """
    Get the main screen dimensions in pixels.

    Uses osascript + AppKit (no pip dependencies needed).
    Returns dict with 'success', 'width', and 'height' keys.
    """
    try:
        # Use osascript with ObjC bridge — works without pip PyObjC
        result = _run([
            "osascript", "-l", "JavaScript", "-e",
            'ObjC.import("AppKit"); '
            "var s = $.NSScreen.mainScreen; var f = s.frame; "
            "JSON.stringify({width: f.size.width, height: f.size.height})"
        ])
        import json
        data = json.loads(result.stdout.strip())
        return {"success": True, "width": int(data["width"]), "height": int(data["height"])}
    except Exception:
        # Fallback to system_profiler
        try:
            result = _run(["system_profiler", "SPDisplaysDataType"])
            for line in result.stdout.splitlines():
                if "Resolution" in line:
                    parts = line.split(":")[-1].strip().split()
                    return {"success": True, "width": int(parts[0]), "height": int(parts[2])}
        except Exception:
            pass
        return _err("Could not determine screen size")


@mcp.tool()
def mouse_click(
    x: int,
    y: int,
    button: str = "left",
    click_type: str = "single",
) -> dict:
    """
    Click the mouse at the given screen coordinates.

    Args:
        x: X coordinate (pixels from left)
        y: Y coordinate (pixels from top)
        button: 'left' or 'right'
        click_type: 'single', 'double', or 'triple' (double/triple only for left button)
    """
    if not isinstance(x, int) or not isinstance(y, int):
        return _err("x and y must be integers")
    if button not in ("left", "right"):
        return _err(f"Unsupported button: {button}. Use 'left' or 'right'.")
    if click_type not in ("single", "double", "triple"):
        return _err(f"Unsupported click_type: {click_type}. Use 'single', 'double', or 'triple'.")
    if button == "right" and click_type != "single":
        return _err("Right-click only supports 'single'. Double/triple right-click is not supported.")

    cmd_map = {
        ("left", "single"): f"c:{x},{y}",
        ("left", "double"): f"dc:{x},{y}",
        ("left", "triple"): f"tc:{x},{y}",
        ("right", "single"): f"rc:{x},{y}",
    }

    action = cmd_map[(button, click_type)]
    result = _cli([action])
    if result["success"]:
        return _ok(f"Clicked {button} {click_type} at ({x}, {y})")
    return result


@mcp.tool()
def mouse_move(x: int, y: int) -> dict:
    """
    Move the mouse cursor to the given screen coordinates.

    Args:
        x: X coordinate (pixels from left)
        y: Y coordinate (pixels from top)
    """
    if not isinstance(x, int) or not isinstance(y, int):
        return _err("x and y must be integers")
    result = _cli([f"m:{x},{y}"])
    if result["success"]:
        return _ok(f"Moved cursor to ({x}, {y})")
    return result


@mcp.tool()
def mouse_drag(x1: int, y1: int, x2: int, y2: int) -> dict:
    """
    Click and drag from one point to another.

    Args:
        x1: Starting X coordinate
        y1: Starting Y coordinate
        x2: Ending X coordinate
        y2: Ending Y coordinate
    """
    for v in (x1, y1, x2, y2):
        if not isinstance(v, int):
            return _err("All coordinates must be integers")
    result = _cli([f"dd:{x1},{y1}", f"dm:{x2},{y2}", f"du:{x2},{y2}"])
    if result["success"]:
        return _ok(f"Dragged from ({x1}, {y1}) to ({x2}, {y2})")
    return result


@mcp.tool()
def mouse_down(x: int, y: int) -> dict:
    """
    Press and hold the left mouse button at coordinates.

    Args:
        x: X coordinate
        y: Y coordinate
    """
    if not isinstance(x, int) or not isinstance(y, int):
        return _err("x and y must be integers")
    result = _cli([f"dd:{x},{y}"])
    if result["success"]:
        return _ok(f"Mouse down at ({x}, {y})")
    return result


@mcp.tool()
def mouse_up(x: int, y: int) -> dict:
    """
    Release the left mouse button at coordinates.

    Args:
        x: X coordinate
        y: Y coordinate
    """
    if not isinstance(x, int) or not isinstance(y, int):
        return _err("x and y must be integers")
    result = _cli([f"du:{x},{y}"])
    if result["success"]:
        return _ok(f"Mouse up at ({x}, {y})")
    return result


@mcp.tool()
def keyboard_type(text: str) -> dict:
    """
    Type a string of text at the current cursor position.

    Args:
        text: The text to type.
    """
    if not text:
        return _err("text must not be empty")
    result = _cli([f"t:{text}"])
    if result["success"]:
        return _ok(f"Typed {len(text)} characters")
    return result


@mcp.tool()
def keyboard_key(key: str) -> dict:
    """
    Press a key or key combination.

    Args:
        key: Key to press. Examples:
            - Single keys: 'return', 'esc', 'tab', 'space', 'delete'
            - Arrow keys: 'arrow-up', 'arrow-down', 'arrow-left', 'arrow-right'
            - Modifiers: 'cmd+s', 'cmd+shift+z', 'ctrl+c', 'alt+tab'
            - Function keys: 'f1', 'f2', etc.
    """
    if not key:
        return _err("key must not be empty")

    if "+" in key:
        # Modifier combo like "cmd+s" or "cmd+shift+z"
        parts = key.split("+")
        modifiers = parts[:-1]
        final_key = parts[-1]

        valid_mods = {"cmd", "ctrl", "alt", "shift", "fn"}
        for m in modifiers:
            if m.lower() not in valid_mods:
                return _err(f"Unknown modifier: {m}. Valid: {', '.join(valid_mods)}")

        # Resolve the final key first — fail before pressing any modifiers
        resolved = _resolve_key(final_key)
        is_named = resolved is not None

        cmds = []
        for m in modifiers:
            cmds.append(f"kd:{m.lower()}")

        if is_named:
            cmds.append(f"kp:{resolved}")
        else:
            # Printable character — use t: instead of kp:
            cmds.append(f"t:{final_key}")

        for m in reversed(modifiers):
            cmds.append(f"ku:{m.lower()}")

        result = _cli(cmds)
        if result["success"]:
            return _ok(f"Pressed {key}")
        return result
    else:
        # Single key
        lower = key.lower()
        if lower in _CLICLICK_MODIFIER_KEYS:
            # Modifier alone — tap with kd: + ku:
            result = _cli([f"kd:{lower}", f"ku:{lower}"])
        else:
            resolved = _resolve_key(key)
            if resolved is not None:
                result = _cli([f"kp:{resolved}"])
            else:
                # Printable character
                result = _cli([f"t:{key}"])
        if result["success"]:
            return _ok(f"Pressed {key}")
        return result


@mcp.tool()
def scroll(
    x: int,
    y: int,
    direction: str = "down",
    amount: int = 3,
) -> dict:
    """
    Scroll the mouse wheel at the given coordinates.

    Uses osascript to generate real CGEvent scroll wheel events.

    Args:
        x: X coordinate to scroll at
        y: Y coordinate to scroll at
        direction: 'up', 'down', 'left', or 'right'
        amount: Number of scroll lines (default 3)
    """
    if not isinstance(x, int) or not isinstance(y, int):
        return _err("x and y must be integers")
    if direction not in ("up", "down", "left", "right"):
        return _err(f"Invalid direction: {direction}. Use 'up', 'down', 'left', or 'right'.")
    if not isinstance(amount, int) or amount < 1:
        return _err("amount must be a positive integer")

    # Move cursor to position first
    move_result = _cli([f"m:{x},{y}"])
    if not move_result["success"]:
        return move_result

    # Generate real scroll wheel events via CGEvent through osascript ObjC bridge
    dy = amount if direction == "up" else (-amount if direction == "down" else 0)
    dx = (-amount if direction == "left" else (amount if direction == "right" else 0))

    # Use osascript with ObjC bridge for CGEvent scroll wheel
    script = f"""
ObjC.import('CoreGraphics');
var event = $.CGEventCreateScrollWheelEvent(null, $.kCGScrollEventUnitLine, 2, {dy}, {dx});
$.CGEventPost($.kCGHIDEventTap, event);
"""
    try:
        result = _run(["osascript", "-l", "JavaScript", "-e", script], check=False)
        if result.returncode != 0:
            return _err(f"Scroll failed: {result.stderr.strip()}")
        return _ok(f"Scrolled {direction} by {amount} at ({x}, {y})")
    except subprocess.TimeoutExpired:
        return _err("Scroll timed out")


@mcp.tool()
def wait(seconds: float = 1.0) -> dict:
    """
    Pause for a specified duration. Useful between UI interactions.

    Args:
        seconds: Duration to wait (default 1.0, max 10.0)
    """
    if not isinstance(seconds, (int, float)) or seconds <= 0:
        return _err("seconds must be a positive number")
    if seconds > 10:
        return _err("Maximum wait is 10 seconds")
    time.sleep(seconds)
    return _ok(f"Waited {seconds}s")


if __name__ == "__main__":
    mcp.run()
