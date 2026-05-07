<div align="center">

# OneShot

### One prompt. Full delivery.

OneShot is a Claude plugin that turns one big request into a finished project. You type `/oneshot`, describe what you want, and Claude keeps working until it's done — or until it needs a decision only you can make.

Works with Claude Desktop. Also works with Codex.

[![License](https://img.shields.io/badge/license-Apache%202.0-blue)](LICENSE)

![OneShot](docs/assets/hero.png)

</div>

---

## What it does

A normal Claude chat answers one question. OneShot keeps Claude going through the whole job — making the files, running the checks, fixing what broke, verifying the result. It can run for an hour, a day, or across resumed sessions.

It pauses and asks you when it needs a password, a payment, or a real human decision. Otherwise, it keeps working.

## Install (Claude Desktop)

1. Download `oneshot-claude-plugin-0.1.0.plugin` from the [latest release](https://github.com/ULTRAPROMPT-BUILD/oneshot/releases/tag/v0.1.0).
2. In Claude Desktop, open plugin settings and upload the file.
3. Enable OneShot.

To start a job: open Claude in the folder you want work done in, type `/oneshot`, and paste your request.

> The `.zip` in the release is the same plugin in a different wrapper — only use it if your system blocks `.plugin` files.

## How to use it

The simplest version:

```text
/oneshot build a small habit-tracking app I can run locally
```

For better results, tell Claude five things:

- **Goal** — what you want
- **Audience** — who it's for
- **Done means** — what "finished" looks like
- **Avoid** — anything off-limits
- **Proof** — what you want to see before it hands the work back

Example:

```text
/oneshot build a local-first personal finance dashboard.

Audience: a non-technical person who wants private budgeting.
Done: working app, setup instructions, sample data, screenshots, CSV import, monthly charts, PDF export.
Avoid: paid APIs, busy design, sending data outside the device.
Proof: run it locally, test import/export, screenshots, summary of checks.
```

## More prompt ideas

```text
/oneshot make a playable browser game from this idea, with setup instructions
/oneshot research the best options for this product category and recommend one
/oneshot clean up this project, fix obvious issues, run checks, summarize what changed
/oneshot turn this rough idea into a working first version I can try
```

## Using Codex instead

Codex doesn't use plugin files — just open Codex in the OneShot folder and ask:

```text
Run a OneShot for this:

[your prompt]
```

That's the whole setup.

## What to expect

- **Big asks take real time.** Hours, sometimes longer.
- **It can't bypass logins or payments.** It pauses and asks.
- **If a session ends**, reopen Claude in the same folder and tell it to resume the active OneShot.
- **It needs a workspace.** Open Claude in the folder where the work should happen.

## Safety

OneShot lets Claude read your files, edit them, run commands, and use connected tools. Only point it at folders you're comfortable with that.

Don't paste secrets or credentials into prompts.

## More

- [Architecture](docs/ARCHITECTURE.md) — how OneShot works under the hood
- [Publishing](docs/PUBLISHING.md) — building and releasing the plugin yourself

## License

[Apache 2.0](LICENSE). OneShot is derived from the project listed in [`NOTICE`](NOTICE).
