# Cross-Platform Setup

Use this when setting up OneShot on a fresh machine. The core workflow is native
on macOS, Windows, and Linux/WSL. Pick the host environment where your coding
agent and target projects will actually run.

## 1. Install Tools

Minimum tools:

- Python 3.9+
- Git
- Node.js
- ripgrep (`rg`)
- A coding-agent CLI or editor agent that can open this folder, edit files, run
  commands, and follow long repo instructions

macOS example:

```bash
xcode-select --install
brew install git gh python node ripgrep
```

Windows PowerShell example:

```powershell
winget install Git.Git
winget install Python.Python.3.12
winget install OpenJS.NodeJS
winget install BurntSushi.ripgrep.MSVC
```

Linux/WSL example:

```bash
sudo apt update
sudo apt install -y git python3 python3-venv python3-pip nodejs npm ripgrep
```

Install whichever agent tools you want to use, for example Claude Code, Codex,
OpenCode, a VS Code-style editor agent, a desktop app, or another GUI agent. A
plain web chat without repo and terminal access is not enough.

## 2. Clone

```bash
# Use the OneShot source location provided with your distribution.
cd OneShot
```

## 3. Python Environment

Windows PowerShell:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
```

macOS/Linux/WSL:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
```

That installs the `oneshot` command on your PATH. For optional extras (video
evidence, ChromaDB indexing, etc.), use:

```bash
python -m pip install -e ".[full]"        # third-party integrations
python -m pip install -e ".[dev]"         # pytest
```

Or pin everything to the full dev list with `python -m pip install -r requirements.txt`.

## 4. Local Secrets

```bash
oneshot
```

That copies `.env.example` -> `.env`, `.mcp.example.json` -> `.mcp.json`, and
`vault/clients/_registry.example.md` -> `vault/clients/_registry.md` (skipping
any that already exist), then verifies `claude`, `codex`, or `opencode` is on
PATH.

Edit `.env` and `.mcp.json` locally. Never commit them. Leave the `.example`
files alone; they are the source of truth for new installs.

Minimum useful variables:

- `STITCH_API_KEY` if using Stitch

## 5. Optional Browser And Video Evidence

For browser walkthrough capture:

```bash
python -m playwright install chromium
```

For desktop/native walkthrough capture, install ffmpeg and use the host-native
backend:

- macOS: `avfoundation`
- Windows: `gdigrab`
- Linux/WSL with GUI display: `x11grab`

The bundled `computer-use` MCP is still macOS-oriented because it depends on
`screencapture`, `cliclick`, and `osascript`. The rest of the core orchestration
and verification flow does not require those tools.

## 6. Vault Bootstrap

The repo includes a sanitized `vault/config/platform.md`,
`vault/clients/_registry.example.md`, and `vault/clients/_template/`. After step
4 you also have a live `vault/clients/_registry.md`.

For a real install:

1. Update `vault/config/platform.md`.
2. Add real agent CLI commands under `agent_routing` if they are not discoverable on PATH.
3. Create a first practice project/client from `vault/clients/_template/`.

## 7. Verify

```bash
python -m pytest tests
```

Once you start a OneShot run, view live state by opening
`vault/projects/<slug>.derived/status.md` (or the client-scoped equivalent) in
any markdown viewer.

## 8. Chat-Native Operation

Start orchestration from your AI coding tool with a direct prompt that reads
`SYSTEM.md` and `skills/orchestrator.md`. Claude Code and Codex have the most
tested deeper routing support today; other compatible tools can run OneShot
chat-native from this folder. This clean distribution deliberately omits
scheduled execution and external-message automation.

## Windows Versus WSL

Use native Windows when your coding agent, Python, Node, browser tests, and
target projects all run comfortably from PowerShell or an editor terminal. Use
WSL when the target project expects POSIX shell scripts, Linux packages, or
Unix-only development tooling. Claude Desktop can still open WSL folders via
`\\wsl$\` paths when you choose that route.
