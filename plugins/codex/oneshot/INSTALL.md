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

## Use From Codex

Codex does not upload the Claude `.plugin` file. Open Codex in the OneShot repo/folder:

```bash
codex -C /path/to/OneShot
```

Then start with:

```text
Run a OneShot for this:

[Your goal, constraints, definition of done, and proof expectations.]
```

The OneShot repo/folder is required because it stores `SYSTEM.md`, `skills/orchestrator.md`, the vault, projects, tickets, and proof.

## Optional Marketplace Discovery

Some Codex setups support marketplace-source discovery. If you want this package listed as a local plugin source, add the OneShot repository:

```bash
codex plugin marketplace add /path/to/OneShot
```

This command may depend on the installed Codex version, local configuration, and authentication state. Static package validation does not require running a mutating marketplace install command.
