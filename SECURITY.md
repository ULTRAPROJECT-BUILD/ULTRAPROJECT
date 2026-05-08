# Security

## Reporting a Vulnerability

If you find a security issue in OneShot — credential leaks, sandbox escapes, prompt-injection paths, hook bypasses, or anything that could let an agent or repo do harm — please use GitHub's private vulnerability reporting or open a private Security Advisory for `oneshot-repo/OneShot` rather than filing a public issue.

This project is in early release and shared as-is, so responses are best-effort — but I'd rather know than not.

## Threat Model

OneShot is an AI orchestration system that turns Claude Code or Codex into autonomous agents executing real work on your machine. By design, agents can:

- run shell commands (build tools, test runners, package managers, git, etc.)
- read and write files anywhere within the repo and any workspace it manages
- make outbound API calls when MCPs are configured (Stripe, Google APIs, social media, etc.)
- spawn child agent processes that survive the parent session

The included guardrails:

- `.claude/hooks/` — shell safety, path allowlists, audit logging, verification-first behavior
- `vault/config/platform.md` — quality contract, routing rules, agent enablement
- The orchestrator skill's external-code rules — read-only on cloned third-party repos, explicit access requests for computer-use, etc.

These are real but they are not a sandbox. Run OneShot in environments you control, with credentials scoped to least privilege, and assume the agents will do what their prompts ask them to do. If you hand the system a goal that requires a destructive action, it will plan and execute that action.

## Recommended Practices

- Use restricted-mode API keys (e.g., Stripe restricted keys) wherever supported.
- Keep `.env` and `.mcp.json` out of git. The `.gitignore` enforces this; do not override.
- Run on a dedicated user account or VM if you don't trust the goals you're feeding the system.
- Review the project plan and the first executor prompt before letting a long run start.
- Keep generated artifacts and proof packs outside the main git history unless intentional.
