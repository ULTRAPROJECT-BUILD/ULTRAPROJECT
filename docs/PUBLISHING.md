# Publishing OneShot

This checklist is for preparing a public GitHub release.

## Public Repo Checklist

1. Run tests:

```bash
python3 -m pytest tests
```

2. Validate plugin manifests:

```bash
python3 -m json.tool plugins/claude/oneshot/.claude-plugin/plugin.json >/tmp/oneshot-claude-plugin-json.out
python3 -m json.tool plugins/codex/oneshot/.codex-plugin/plugin.json >/tmp/oneshot-codex-plugin-json.out
python3 -m json.tool .agents/plugins/marketplace.json >/tmp/oneshot-codex-marketplace-json.out
```

3. Validate the Claude plugin package:

```bash
claude plugin validate plugins/claude/oneshot
```

4. Build upload artifacts:

```bash
scripts/package_claude_plugin.sh
```

5. Scan public surfaces for local-only paths or private state:

```bash
rg -n '/Users/|Desktop/|Credit balance|personal skill|this machine|local-desktop-app-uploads|disabled-oneshot' \
  README.md docs/QUICKSTART.md docs/SETUP.md docs/ARCHITECTURE.md plugins .agents .claude
```

Expected result: no hits.

6. Check git status:

```bash
git status --short
```

Generated artifacts such as `dist/`, `proof/`, `.pytest_cache/`, `.env`, and `.mcp.json` should remain untracked.

## Release Artifacts

The Claude upload artifacts are generated locally and should usually be attached to a GitHub release rather than committed:

```text
dist/claude/oneshot-claude-plugin-0.1.0.zip
dist/claude/oneshot-claude-plugin-0.1.0.plugin
```

The `.plugin` file is a zip-formatted alias for upload flows that prefer that extension.

## Plugin Invocation

The public user-facing command should be documented as:

```text
/oneshot <your prompt>
```

Some Claude Code plugin test contexts may display the fully qualified namespace:

```text
/oneshot:oneshot <your prompt>
```

That is the same OneShot skill. Keep `/oneshot` as the headline usage pattern.

## What Not To Claim

Do not claim official marketplace submission, live authenticated install, or unattended background execution unless you have current proof for that release.
