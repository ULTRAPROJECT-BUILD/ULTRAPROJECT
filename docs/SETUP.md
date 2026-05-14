# New Mac Setup

Use this when setting up OneShot on a fresh machine.

## 1. Install Tools

```bash
xcode-select --install
brew install git gh python node ripgrep
```

Install whichever agent tools you want to use: Claude Code, Codex, OpenCode, a VS Code-style editor agent, a desktop app, or another GUI agent that can open this folder, read and edit files, run shell commands, and follow long repo instructions. A plain web chat without repo and terminal access is not enough.

## 2. Clone

```bash
# Use the OneShot source location provided with your distribution.
cd OneShot
```

## 3. Python Environment

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e .
```

That installs the `oneshot` command on your PATH. For optional extras (video evidence, ChromaDB indexing, etc.), use:

```bash
pip install -e ".[full]"        # third-party integrations
pip install -e ".[dev]"         # pytest
```

Or pin everything to the full dev list with `pip install -r requirements.txt`.

## 4. Local Secrets

```bash
oneshot
```

That copies `.env.template` → `.env`, `.mcp.template.json` → `.mcp.json`, and `vault/clients/_registry.template.md` → `vault/clients/_registry.md` (skipping any that already exist), then verifies `claude`, `codex`, or `opencode` is on PATH.

Edit `.env` and `.mcp.json` locally. Never commit them. Leave the `.template` files alone — they're the source of truth for new installs.

Minimum useful variables:

- `STITCH_API_KEY` if using Stitch

## 5. macOS Permissions

If using browser/video evidence:

```bash
python3 -m playwright install chromium
```

## 6. Vault Bootstrap

The repo includes a sanitized `vault/config/platform.md`, `vault/clients/_registry.template.md`, and `vault/clients/_template/`. After step 4 you also have a live `vault/clients/_registry.md`.

For a real install:

1. Update `vault/config/platform.md`.
2. Add real agent CLI commands under `agent_routing`.
3. Create a first practice project/client from `vault/clients/_template/`.

## 7. Verify

```bash
python3 -m pytest tests
```

Once you start a OneShot run, view live state by opening `vault/projects/<slug>.derived/status.md` (or the client-scoped equivalent) in any markdown viewer.

## 8. Chat-Native Operation

Start orchestration from your AI coding tool with a direct prompt that reads `SYSTEM.md` and `skills/orchestrator.md`. Claude Code and Codex have the most tested deeper routing support today; other compatible tools can run OneShot chat-native from this folder. This clean distribution deliberately omits scheduled execution and external-message automation.
