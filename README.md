<div align="center">

# OneShot

### One prompt. Full delivery.

OneShot is a Claude plugin for big AI requests. Ask for the app, game, website, research, cleanup, migration, or project you want delivered, and OneShot tells Claude to keep going until the result is finished, checked, or blocked by something only you can decide.

You do not need to understand the project-management stuff behind it. That stays under the hood. You just use `/oneshot`.

[![License](https://img.shields.io/badge/license-Apache%202.0-blue)](LICENSE)
[![Status](https://img.shields.io/badge/status-public--release--ready-green)](#for-publishers)

![OneShot](docs/assets/hero.png)

[Install](#install) . [Use](#use) . [Examples](#examples) . [Codex](#using-codex) . [Publish](#for-publishers)

</div>

---

## What OneShot Does

Normal Claude chats are great for quick answers. Big requests are different.

If you ask Claude to build something serious, you often have to keep nudging it: remember the goal, make the files, run the checks, fix the mistakes, explain what changed, keep going.

OneShot is made for that kind of work.

You give Claude one serious prompt. OneShot pushes it to:

- understand what you want
- make reasonable assumptions when details are missing
- keep working instead of stopping at a first draft
- check the work before handing it back
- tell you clearly if it needs a password, payment, approval, or other human decision
- resume from saved progress if the session gets interrupted

It can run for an hour, a day, or longer if that is what the job takes.

## Install

Download one of the OneShot plugin files from the release:

```text
oneshot-claude-plugin-0.1.0.plugin
```

or:

```text
oneshot-claude-plugin-0.1.0.zip
```

Then:

1. Open Claude Desktop.
2. Go to your plugin settings.
3. Upload the OneShot plugin file.
4. Enable OneShot.
5. Open Claude where you want the work done.
6. Type `/oneshot` and paste your request.

You do not need to download the whole OneShot repo to use the Claude plugin. The repo is only needed if you want to build, inspect, or publish the plugin yourself.

Some Claude screens may show the full name as:

```text
/oneshot:oneshot
```

That is the same OneShot plugin. Pick the OneShot option from the slash menu if you see both.

## Use

Start with `/oneshot`, then say what you want.

```text
/oneshot build a simple personal budget app with CSV import, charts, setup instructions, screenshots, and proof that the main flows work
```

That is enough.

For better results, add:

- what you want built
- who it is for
- what "done" means
- anything to avoid
- what proof you want before it is handed back

Example:

```text
/oneshot build a local-first personal finance dashboard.

It is for a non-technical person who wants private budgeting.

Done means: working app, setup instructions, sample data, screenshots, CSV import, spending categories, monthly charts, and PDF export.

Constraints: no paid APIs, calm design, and no financial data sent to outside services.

Proof: run it locally, test import/export, capture screenshots, and summarize what was checked.
```

## Examples

```text
/oneshot build a small habit-tracking app I can run locally
```

```text
/oneshot make a playable browser game from this idea and include setup instructions
```

```text
/oneshot research the best options for this product category and give me a clear recommendation
```

```text
/oneshot clean up this project, fix obvious issues, run checks, and tell me what changed
```

```text
/oneshot turn this rough app idea into a working first version I can try
```

## What To Expect

OneShot does not magically bypass real limits.

- If Claude needs access to files, open it where those files are available.
- If the work needs a login, API key, payment, or approval, OneShot should stop and tell you.
- If the session ends, reopen the same project and ask Claude to resume the active OneShot project.
- If you ask for something huge, expect it to take real time and model usage.

The goal is simple: one prompt in, full delivery out.

## Using Codex

Claude is the main `/oneshot` plugin experience. This section is only for people using Codex.

Codex works differently. It does not upload a `.plugin` file and it does not create a `/oneshot` slash command.

For Codex, add the OneShot repository as a plugin marketplace source:

```bash
codex plugin marketplace add /path/to/OneShot
```

Then open Codex on the project you want worked on and start with:

```text
Run a OneShot for this:

[your prompt]
```

That uses the bundled OneShot Codex skill.

## For Publishers

People publishing or validating OneShot can build the Claude plugin files with:

```bash
scripts/package_claude_plugin.sh
```

Useful docs:

- [Quickstart](docs/QUICKSTART.md)
- [Publishing checklist](docs/PUBLISHING.md)
- [Claude plugin install notes](plugins/claude/oneshot/INSTALL.md)
- [Codex plugin notes](plugins/codex/oneshot/INSTALL.md)

## Safety

OneShot can ask Claude to read files, edit files, run commands, and use connected tools. Use it in workspaces where you are comfortable letting Claude work.

Do not upload secrets, private customer data, or payment credentials unless you understand where they will be used.

## License

OneShot is derived from the source project identified in the legal and provenance files.

[Apache 2.0](LICENSE). Keep the copyright notice and `NOTICE` file.
