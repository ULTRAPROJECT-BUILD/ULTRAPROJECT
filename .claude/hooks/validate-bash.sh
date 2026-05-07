#!/bin/bash
# Hook: PreToolUse — blocks destructive or dangerous bash commands
# Also enforces writes-only-in-platform-dir for bash redirects/pipes
# Exit 0 = allow, Exit 2 = block

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('tool_input',{}).get('command',''))" 2>/dev/null)

if [[ -z "$COMMAND" ]]; then
    exit 0
fi

export PLATFORM_DIR="${PLATFORM_DIR:-$(pwd)}"

COMMAND_TEXT="$COMMAND" python3 << 'PYCHECK'
import os
import sys, re

command = os.environ.get("COMMAND_TEXT", "").strip()

PLATFORM_DIR = os.path.realpath(os.environ.get("PLATFORM_DIR", os.getcwd()))

# === DESTRUCTIVE COMMANDS ===
destructive_patterns = [
    r'rm\s+-[rR]f?\s+[/~]',       # rm -rf / or ~
    r'rm\s+-[rR]f?\s+\.\s',        # rm -rf .
    r'rmdir\s+/',                    # rmdir /
    r'mkfs\b',                       # format disk
    r'dd\s+if=',                     # disk overwrite
    r'>\s*/dev/',                     # write to device
    r'chmod\s+-R\s+777\s+/',        # open permissions on root
    r':()\s*\{',                     # fork bomb
]

for pattern in destructive_patterns:
    if re.search(pattern, command):
        print(f"BLOCKED: Destructive command detected. Pattern: {pattern}", file=sys.stderr)
        sys.exit(2)

# === CREDENTIAL EXFILTRATION ===
# Check for reading sensitive files and piping/sending them externally
sensitive_paths = [r'\.ssh', r'\.gnupg', r'\.env', r'credentials', r'\.netrc', r'id_rsa', r'id_ed25519',
                   r'\.aws', r'\.azure', r'\.kube', r'\.npmrc', r'\.pypirc', r'Keychains']
exfil_commands = [r'curl', r'wget', r'nc\b', r'ncat', r'scp\b', r'rsync', r'sftp', r'python3?\s+-c', r'node\s+-e']

reads_sensitive = any(re.search(p, command) for p in sensitive_paths)
has_exfil = any(re.search(p, command) for p in exfil_commands)

if reads_sensitive and has_exfil:
    print("BLOCKED: Potential credential exfiltration — reading sensitive files and sending externally in the same command.", file=sys.stderr)
    sys.exit(2)

# === PLATFORM CREDENTIAL FILES — BLOCK ALL READS ===
# These files contain secrets that agents should never access directly.
# Credentials are passed via environment variables or .mcp.json, not by reading these files.
credential_files = [
    r'(?:^|[\s;|&/])\.mcp\.json\b',
    r'(?:^|[\s;|&/])\.env\b(?!\.)',
    r'(?:^|[\s;|&/])\.financial-secrets\b',
]
for pattern in credential_files:
    if re.search(pattern, command):
        print(f"BLOCKED: Direct access to credential files is not allowed. Credentials are provided via environment variables.", file=sys.stderr)
        sys.exit(2)

# === PROTECTED FILES WITHIN PLATFORM DIR (BASH REDIRECTS) ===
# These files are protected by restrict-paths.sh for Write/Edit tools, but bash
# redirects (echo x > file) bypass that hook. Block bash writes to these too.
protected_within_platform = [
    os.path.join(PLATFORM_DIR, ".env"),
    os.path.join(PLATFORM_DIR, ".mcp.json"),
    os.path.join(PLATFORM_DIR, ".financial-secrets"),
    os.path.join(PLATFORM_DIR, "vault", "config", ".spending-integrity"),
    os.path.join(PLATFORM_DIR, "vault", "config", "platform.md"),
    os.path.join(PLATFORM_DIR, "SYSTEM.md"),
    os.path.join(PLATFORM_DIR, "CLAUDE.md"),
]
# Check for bash writes (>, >>, tee, cp, mv) targeting protected files
for prot_file in protected_within_platform:
    # Check both absolute and relative forms
    basename = os.path.basename(prot_file)
    rel_from_platform = os.path.relpath(prot_file, PLATFORM_DIR)
    for form in [prot_file, basename, rel_from_platform, "./" + rel_from_platform]:
        # Look for redirects or write commands targeting this file
        # Note: >> must be tried before > to avoid partial match; \s* allows spaces after operators
        if re.search(r'(?:>>\s*|>\s*|tee\s+|cp\s+\S+\s+|mv\s+\S+\s+)' + re.escape(form) + r'(?:\s|$)', command):
            print(f"BLOCKED: Bash write to protected file '{basename}' is not allowed.", file=sys.stderr)
            sys.exit(2)
        # Also check rm/unlink on protected files
        if re.search(r'(?:rm\s+(?:-f\s+)?)' + re.escape(form) + r'(?:\s|$)', command):
            print(f"BLOCKED: Deleting protected file '{basename}' is not allowed.", file=sys.stderr)
            sys.exit(2)

# === RESTRICTED PATH WRITES VIA BASH ===
# Catch redirects (>, >>, tee) and file-writing commands targeting outside platform dir
write_indicators = [r'>\s*/', r'>>\s*/', r'tee\s+/', r'cp\s+.+\s+/', r'mv\s+.+\s+/', r'install\s+.+\s+/']

for pattern in write_indicators:
    matches = re.finditer(pattern, command)
    for match in matches:
        # Extract the target path after the operator
        rest = command[match.start():]
        # Find the path
        path_match = re.search(r'[/~][\w./-]+', rest)
        if path_match:
            target = path_match.group()
            if target.startswith("~"):
                target = os.path.expanduser(target)
            # Allow writes within platform dir
            if not target.startswith(PLATFORM_DIR + "/") and target != PLATFORM_DIR:
                # Allow /tmp and /var/tmp for temp files
                if not target.startswith("/tmp/") and not target.startswith("/var/tmp/"):
                    print(f"BLOCKED: Bash write to path outside platform directory: {target}", file=sys.stderr)
                    sys.exit(2)

sys.exit(0)
PYCHECK
