# Validation

Run these checks from the OneShot repo root after editing this package.

## Static Checks

Parse the Claude manifest:

```bash
python3 -m json.tool plugins/claude/oneshot/.claude-plugin/plugin.json >/tmp/oneshot-claude-plugin-json.out
```

Parse the local Claude catalog:

```bash
python3 -m json.tool plugins/claude/marketplace.json >/tmp/oneshot-claude-marketplace-json.out
```

Inspect the package tree:

```bash
find plugins/claude/oneshot -maxdepth 4 -print | sort
```

Reject invalid nesting:

```bash
test ! -e plugins/claude/oneshot/.claude-plugin/skills \
  && test ! -e plugins/claude/oneshot/.claude-plugin/commands \
  && test ! -e plugins/claude/oneshot/.claude-plugin/hooks \
  && test ! -e plugins/claude/oneshot/.claude-plugin/agents
```

Check for stale placeholders in the Claude package:

```bash
rg -n "T[O]DO|T[B]D|example\\.[i]nvalid|plugin-[n]ame|my-first-[p]lugin" plugins/claude/oneshot plugins/claude/marketplace.json
```

Expected result: no hits.

The package intentionally names legacy source-project files only in setup guardrails that stop Claude from using an old vault.

## Claim Readback

Read these files and confirm they do not claim official marketplace submission, remote marketplace availability, or an installed uppercase `/ONESHOT` command:

```text
plugins/claude/oneshot/README.md
plugins/claude/oneshot/INSTALL.md
plugins/claude/oneshot/LIMITATIONS.md
plugins/claude/oneshot/VALIDATION.md
plugins/claude/marketplace.json
```

Expected result: marketplace language is local/catalog-only unless a host command is manually verified, and the installed package presents one OneShot skill rather than a legacy command/uppercase command pair.

## Host Checks

If the Claude CLI is available and authenticated, test local loading from the repo root:

```bash
claude --plugin-dir ./plugins/claude/oneshot
```

If the CLI is missing, unauthenticated, or opens an interactive session that cannot be completed in automation, classify this as infrastructure-dependent and keep the static validation transcript.

If an interactive Claude Code session is available after editing plugin files, run:

```text
/reload-plugins
```

Record the session result in the active ticket or proof pack.
