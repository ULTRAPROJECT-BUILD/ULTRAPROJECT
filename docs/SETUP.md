# New Mac Setup

Use this when cloning ULTRAPROJECT onto a fresh machine.

## 1. Install Tools

```bash
xcode-select --install
brew install git gh python node ripgrep
```

Install whichever agent CLIs you want to use, for example Codex and/or Claude Code.

## 2. Clone

```bash
git clone https://github.com/ULTRAPROJECT-BUILD/ULTRAPROJECT
cd ULTRAPROJECT
```

## 3. Python Environment

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e .
```

That installs the `ultraproject` command on your PATH. For optional extras (video evidence, ChromaDB indexing, etc.), use:

```bash
pip install -e ".[full]"        # third-party integrations
pip install -e ".[dev]"         # pytest
```

Or pin everything to the full dev list with `pip install -r requirements.txt`.

## 4. Local Secrets

```bash
ultraproject
```

That copies `.env.example` → `.env`, `.mcp.example.json` → `.mcp.json`, and `vault/clients/_registry.example.md` → `vault/clients/_registry.md` (skipping any that already exist), then verifies `claude` or `codex` is on PATH.

Edit `.env` and `.mcp.json` locally. Never commit them. Leave the `.example` files alone — they're the source of truth for new installs.

Minimum useful variables:

- `STITCH_API_KEY` if using Stitch

## 5. macOS Permissions

If using browser/video evidence:

```bash
python3 -m playwright install chromium
```

## 6. Vault Bootstrap

The repo includes a sanitized `vault/config/platform.md`, `vault/clients/_registry.example.md`, and `vault/clients/_template/`. After step 4 you also have a live `vault/clients/_registry.md`.

For a real install:

1. Update `vault/config/platform.md`.
2. Add real agent CLI commands under `agent_routing`.
3. Create a first practice project/client from `vault/clients/_template/`.

## 7. Verify

```bash
python3 -m pytest tests
```

Once you start an ultraproject, view live state by opening `vault/projects/<slug>.derived/status.md` (or the client-scoped equivalent) in any markdown viewer.

## 8. Chat-Native Operation

Start orchestration from Codex or Claude with a direct prompt that reads `SYSTEM.md` and `skills/orchestrator.md`. This clean distribution deliberately omits scheduled execution and external-message automation.
