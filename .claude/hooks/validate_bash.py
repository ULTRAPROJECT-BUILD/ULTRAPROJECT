#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path


def platform_dir() -> Path:
    return Path(
        os.environ.get("PLATFORM_DIR")
        or os.environ.get("CLAUDE_PROJECT_DIR")
        or Path.cwd()
    ).resolve()


def normalize_for_match(path: Path | str) -> str:
    return str(path).replace("\\", "/")


def command_from_stdin() -> str:
    try:
        data = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        return ""
    return str(data.get("tool_input", {}).get("command", "") or "").strip()


def blocked(message: str) -> int:
    print(f"BLOCKED: {message}", file=sys.stderr)
    return 2


def check_destructive_commands(command: str) -> int | None:
    destructive_patterns = [
        r"rm\s+-[rR]f?\s+[/~]",
        r"rm\s+-[rR]f?\s+\.\s",
        r"rmdir\s+/",
        r"mkfs\b",
        r"dd\s+if=",
        r">\s*/dev/",
        r"chmod\s+-R\s+777\s+/",
        r":\(\)\s*\{",
        r"Remove-Item\s+.*-Recurse.*-Force\s+(?:[A-Za-z]:\\|/|~)",
        r"\brd\s+/s\s+(?:[A-Za-z]:\\|\\|/)",
        r"\brmdir\s+/s\s+(?:[A-Za-z]:\\|\\|/)",
        r"\bformat\s+[A-Za-z]:",
        r"\bdiskpart\b",
    ]
    for pattern in destructive_patterns:
        if re.search(pattern, command, re.IGNORECASE):
            return blocked(f"Destructive command detected. Pattern: {pattern}")
    return None


def check_credential_access(command: str) -> int | None:
    sensitive_paths = [
        r"\.ssh",
        r"\.gnupg",
        r"\.env",
        r"credentials",
        r"\.netrc",
        r"id_rsa",
        r"id_ed25519",
        r"\.aws",
        r"\.azure",
        r"\.kube",
        r"\.npmrc",
        r"\.pypirc",
        r"Keychains",
    ]
    exfil_commands = [
        r"curl",
        r"wget",
        r"nc\b",
        r"ncat",
        r"scp\b",
        r"rsync",
        r"sftp",
        r"python3?\s+-c",
        r"node\s+-e",
        r"Invoke-WebRequest",
        r"iwr\b",
    ]

    reads_sensitive = any(re.search(pattern, command, re.IGNORECASE) for pattern in sensitive_paths)
    has_exfil = any(re.search(pattern, command, re.IGNORECASE) for pattern in exfil_commands)
    if reads_sensitive and has_exfil:
        return blocked(
            "Potential credential exfiltration: reading sensitive files and sending externally "
            "in the same command."
        )

    credential_files = [
        r"(?:^|[\s;|&/\\])\.mcp\.json\b",
        r"(?:^|[\s;|&/\\])\.env\b(?!\.)",
        r"(?:^|[\s;|&/\\])\.financial-secrets\b",
    ]
    for pattern in credential_files:
        if re.search(pattern, command, re.IGNORECASE):
            return blocked("Direct access to credential files is not allowed.")
    return None


def protected_forms(root: Path) -> list[tuple[str, list[str]]]:
    protected = [
        root / ".env",
        root / ".mcp.json",
        root / ".financial-secrets",
        root / "vault" / "config" / ".spending-integrity",
        root / "vault" / "config" / "platform.md",
        root / "SYSTEM.md",
        root / "CLAUDE.md",
    ]
    forms: list[tuple[str, list[str]]] = []
    for path in protected:
        rel = os.path.relpath(path, root)
        forms.append(
            (
                path.name,
                [
                    normalize_for_match(path),
                    normalize_for_match(rel),
                    "./" + normalize_for_match(rel),
                    path.name,
                ],
            )
        )
    return forms


def check_protected_file_writes(command: str, root: Path) -> int | None:
    normalized_command = normalize_for_match(command)
    for basename, forms in protected_forms(root):
        for form in forms:
            escaped = re.escape(form)
            write_re = r"(?:>>\s*|>\s*|tee\s+|cp\s+\S+\s+|mv\s+\S+\s+)" + escaped + r"(?:\s|$)"
            delete_re = r"(?:rm\s+(?:-f\s+)?|del\s+|erase\s+)" + escaped + r"(?:\s|$)"
            if re.search(write_re, normalized_command, re.IGNORECASE):
                return blocked(f"Bash write to protected file '{basename}' is not allowed.")
            if re.search(delete_re, normalized_command, re.IGNORECASE):
                return blocked(f"Deleting protected file '{basename}' is not allowed.")
    return None


def check_external_writes(command: str, root: Path) -> int | None:
    normalized_command = normalize_for_match(command)
    root_text = normalize_for_match(root).rstrip("/")
    allowed_temp = ("/tmp/", "/var/tmp/")
    write_indicators = [
        r">>\s*",
        r">\s*",
        r"tee\s+",
        r"cp\s+.+\s+",
        r"mv\s+.+\s+",
        r"install\s+.+\s+",
        r"Set-Content\s+.*-Path\s+",
        r"Out-File\s+.*-FilePath\s+",
    ]
    path_re = re.compile(r"(?:[A-Za-z]:/|/|~)[^\s|&;'\"]+")
    for pattern in write_indicators:
        for match in re.finditer(pattern, normalized_command, re.IGNORECASE):
            rest = normalized_command[match.start() :]
            path_match = path_re.search(rest)
            if not path_match:
                continue
            target = path_match.group()
            if target.startswith("~"):
                target = normalize_for_match(Path(target).expanduser())
            if target == root_text or target.startswith(root_text + "/"):
                continue
            if target.startswith(allowed_temp):
                continue
            return blocked(f"Bash write to path outside platform directory: {target}")
    return None


def main() -> int:
    command = command_from_stdin()
    if not command:
        return 0

    root = platform_dir()
    for check in (
        check_destructive_commands,
        check_credential_access,
        lambda text: check_protected_file_writes(text, root),
        lambda text: check_external_writes(text, root),
    ):
        result = check(command)
        if result is not None:
            return result
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
