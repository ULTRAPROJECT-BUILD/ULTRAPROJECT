# Install OneShot For Codex

## Local Repository Use

The plugin package lives at:

```text
plugins/codex/oneshot
```

The repo-local marketplace metadata lives at:

```text
.agents/plugins/marketplace.json
```

## Marketplace Discovery

Codex uses marketplace-source discovery. Add the OneShot repository as a marketplace source:

```bash
cd oneshot
codex plugin marketplace add .
```

For a published repo, users can add the GitHub source instead:

```bash
codex plugin marketplace add owner/repo
```

This command may depend on the installed Codex version, local configuration, and authentication state. Static package validation does not require running a mutating marketplace install command.

## First Prompt

After the plugin is available in Codex, open Codex on the project you want OneShot to work on and start with:

```text
Run the OneShot workflow for this prompt:

[Your goal, constraints, definition of done, and proof expectations.]
```

If you only want planning, say so explicitly. If you name a ticket, the skill should execute only that ticket.
