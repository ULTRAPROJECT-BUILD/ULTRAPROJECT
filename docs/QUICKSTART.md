# OneShot Quickstart

This is the shortest path for each host.

- **Claude:** download the OneShot repo, install the plugin, open Claude in the OneShot folder, type `/oneshot`, and paste the job.
- **Codex:** open Codex in the OneShot folder, then start with `Run a OneShot for this:`.

## Claude: Install OneShot

OneShot has two pieces:

- The **OneShot repo/folder**, which stores the workflow, vault, projects, tickets, and proof.
- The **Claude plugin**, which gives Claude the `/oneshot` command.

Download or clone the OneShot repo from the [latest release](https://github.com/ULTRAPROMPT-BUILD/oneshot/releases/tag/v0.1.0), then put the folder somewhere permanent.

Download one of the Claude plugin artifacts from the same release:

```text
oneshot-claude-plugin-0.1.0.plugin
```

or:

```text
oneshot-claude-plugin-0.1.0.zip
```

Upload it in Claude Desktop or your Claude organization plugin marketplace, then enable OneShot.

If you are building from source instead of downloading a release artifact, run this from the OneShot repo root:

```bash
scripts/package_claude_plugin.sh
```

The script creates both upload formats under `dist/claude/`.

## Claude: Use `/oneshot`

Open Claude Code or Cowork in the OneShot folder, then run:

```text
/oneshot <your prompt, specs, project, goal, etc.>
```

Example:

```text
/oneshot build a polished local-first budgeting app with CSV import, charts, PDF export, setup docs, screenshots, and proof that the main flows work
```

OneShot already carries the strict delivery contract inside the plugin. You do not need to paste the long orchestration prompt by hand.

Do not open Claude in an old ULTRAPROMPT folder. That folder has a different vault and can send work to the wrong place.

Some Claude Code plugin contexts display the fully qualified plugin namespace:

```text
/oneshot:oneshot <your prompt, specs, project, goal, etc.>
```

That is the same OneShot skill. Select the OneShot entry from the slash menu when in doubt.

## Codex: Use The OneShot Folder

Codex does not upload a `.plugin` file and does not use Claude-style `/oneshot` slash commands. Open Codex in the OneShot folder:

```bash
codex -C /path/to/OneShot
```

Start the run with:

```text
Run a OneShot for this:

[Your prompt, specs, project, goal, etc.]
```

That uses the bundled OneShot Codex skill and the repo-backed workflow.

## Write A Better OneShot Prompt

You can paste a rough ask, but better prompts usually include:

- **Goal:** the concrete result you want.
- **Audience:** who will use or judge it.
- **Done means:** what must exist before the work is finished.
- **Constraints:** stack, style, budget, files, timing, and things to avoid.
- **Proof:** tests, screenshots, citations, reports, command output, or reviews.

You do not need to describe OneShot's internal process. Describe the result you want to come back to.

## Let It Run

OneShot is for work that may take an hour, a day, or a longer resumed project. It keeps the agent aimed at full delivery: files changed, checks run, assumptions recorded, blockers named, and handoff clear.

OneShot does not run as a hidden background service. The active Claude, Codex, or compatible local agent does the work while OneShot supplies the delivery workflow.

## Resume Later

If the session ends, reopen the same project in your agent and ask it to resume the active OneShot project from disk:

```text
Resume the active OneShot project in this repo. Do not create a new project.

Restore state from the latest OneShot checkpoint and continue to delivery. If more than one active OneShot project exists, ask me which one to resume.
```

Progress lives in the OneShot repo vault.

## Developer Source Setup

Use this only if you are developing OneShot, validating the package, or building release artifacts yourself.

```bash
cd oneshot
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e .
oneshot
```

The `oneshot` helper bootstraps local config examples and checks for an available agent CLI. The main user workflows are still the Claude plugin command or the Codex marketplace skill.

## Next

- [README.md](../README.md) for the product overview and example prompts
- [SETUP.md](SETUP.md) for deeper environment setup
- [PUBLISHING.md](PUBLISHING.md) for public-release packaging and checks
