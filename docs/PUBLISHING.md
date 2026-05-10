# Publishing OneShot

This checklist is for preparing a public GitHub release.

OneShot is distributed as a repo/folder. Do not attach plugin packages or document slash-command installation unless that workflow has been deliberately reintroduced and freshly proven.

## Public Repo Checklist

1. Run tests:

```bash
python -m pytest tests
```

2. Scan public docs for stale plugin instructions, local-only paths, or private state:

```bash
rg -n '/Users/|Credit balance|personal skill|this machine|local-desktop-app-uploads|disabled-oneshot|(^|[[:space:]])/oneshot\\b|\\.plugin|plugin marketplace|package_claude_plugin' \
  README.md docs examples --glob '!docs/PUBLISHING.md'
```

Expected result: no hits, except examples where the matched word is part of an unrelated topic.

3. Check git status:

```bash
git status --short
```

Generated artifacts such as `dist/`, `proof/`, `.pytest_cache/`, `.env`, and `.mcp.json` should remain untracked.

## Release Artifacts

GitHub's automatic source archives are the release artifact:

```text
Source code (zip)
Source code (tar.gz)
```

Do not upload `.plugin` or plugin zip files for the current release model.

## Public Usage Pattern

The public user-facing workflow should be documented as:

```text
Open/select the OneShot folder, then paste the full starter prompt.
```

The starter prompt lives in the README and Quickstart.

## What Not To Claim

Do not claim plugin installation, slash-command support, official marketplace submission, live authenticated install, or unattended background execution unless you have current proof for that release.
