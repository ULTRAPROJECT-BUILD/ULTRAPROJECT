# Install OneShot For Claude

This package is meant to be used as an installed Claude plugin:

- Claude.ai/Cowork organization marketplaces, where manual upload expects a valid `.zip` or `.plugin` file.
- Claude Code local development/testing, where plugins are directories loaded with `--plugin-dir` or installed through a local marketplace.

End users need both the OneShot repo/folder and the plugin file. The repo stores the OneShot workflow, vault, projects, tickets, and proof. The plugin adds the `/oneshot` command in Claude.

## Option 1: Claude.ai / Cowork Upload

Use this when an organization owner wants to upload OneShot through Claude Desktop's Cowork plugin marketplace UI.

Build upload artifacts from the repo root:

```bash
scripts/package_claude_plugin.sh
```

The script creates `dist/claude/oneshot-claude-plugin-0.1.0.zip` and a zip-formatted `.plugin` alias.

Upload steps:

1. Open Claude Desktop.
2. Go to Organization settings -> Plugins.
3. Click Add plugins.
4. Choose Upload a file.
5. Select `oneshot-claude-plugin-0.1.0.zip`, or `oneshot-claude-plugin-0.1.0.plugin` if that extension is preferred by the upload UI.
6. Add it to a new or existing marketplace.
7. Set the plugin availability preference for your users.
8. In Cowork or Claude Code, install or enable OneShot.
9. Open Claude in the OneShot repo/folder, not an old ULTRAPROMPT folder and not an unrelated project folder.
10. Invoke OneShot from the slash menu:

```text
/oneshot <your prompt, specs, project, goal, etc.>
```

The zip is built from the plugin root contents, so `.claude-plugin/plugin.json`, `skills/`, and docs are at the archive root.

## Option 2: Claude Code Local Marketplace

From the OneShot repo root:

```bash
cd oneshot
claude
```

Inside Claude Code, add the local marketplace directory:

```text
/plugin marketplace add ./plugins/claude
```

Then install the plugin:

```text
/plugin install oneshot@oneshot-local
```

Restart Claude Code if prompted, then run:

```text
/oneshot <your prompt, specs, project, goal, etc.>
```

Run that command from a Claude session opened in the OneShot repo/folder.

The Claude Code marketplace metadata lives at:

```text
plugins/claude/.claude-plugin/marketplace.json
```

The package also keeps a readable catalog copy at:

```text
plugins/claude/marketplace.json
```

Some Claude Code plugin test contexts display the fully qualified form:

```text
/oneshot:oneshot <your prompt, specs, project, goal, etc.>
```

That is the same OneShot skill. The intended user-facing surface is `/oneshot`.

## Option 3: Claude Code Local Load

From the OneShot repo root:

```bash
cd oneshot
claude --plugin-dir ./plugins/claude/oneshot
```

Inside Claude Code, run:

```text
/oneshot <your prompt, specs, project, goal, etc.>
```

If your local plugin loader exposes the namespace, use `/oneshot:oneshot` or select the OneShot entry from the slash menu.

The skill description is:

```text
OneShot: paste a prompt, the orchestrator delivers it.
```

Claude skill names are lowercase in this package, so some Claude UIs may show the skill as `/oneshot`. The package intentionally avoids legacy `commands/` files and duplicate skill/command pairs so users see one OneShot entry.

## Not Claimed

This package does not claim:

- official Claude marketplace submission
- remote marketplace availability
- unattended external automation
- a completed authenticated Cowork upload
- an uppercase `/ONESHOT` command inside the installed plugin
- a legacy `commands/` file in addition to the skill
