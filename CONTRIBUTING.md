# Contributing To OneShot

Thanks for helping improve OneShot. The goal of this project is to make serious AI agent work more planned, resumable, and provably complete.

## Canonical Repository

The canonical source project that OneShot was derived from lives at:

```text
https://github.com/ULTRAPROMPT-BUILD/ULTRAPROMPT
```

For this OneShot distribution, use the issue, pull request, security report, and project discussion channels provided by the OneShot maintainers. The ULTRAPROMPT URL above is provenance for the source project, not the support channel for OneShot.

## Contribution License

OneShot is licensed under the [Apache License 2.0](LICENSE).

By submitting a pull request, issue patch, code snippet, documentation change, test, example, or other contribution for inclusion in this repository, you agree that your contribution is submitted under Apache 2.0 unless you clearly mark it as "Not a Contribution" before submission.

Do not submit code, prompts, docs, generated output, images, datasets, or other materials unless you have the right to contribute them.

## Developer Certificate Of Origin

This project uses a lightweight Developer Certificate of Origin process. Each commit should include a sign-off line:

```text
Signed-off-by: Your Name <you@example.com>
```

You can add it automatically with:

```bash
git commit -s
```

By signing off a commit, you certify that you wrote the contribution or otherwise have the right to submit it under the project license. Maintainers may ask you to amend commits that are missing sign-off.

The sign-off means you certify the following:

```text
Developer Certificate of Origin
Version 1.1

Copyright (C) 2004, 2006 The Linux Foundation and its contributors.

Everyone is permitted to copy and distribute verbatim copies of this
license document, but changing it is not allowed.

Developer's Certificate of Origin 1.1

By making a contribution to this project, I certify that:

(a) The contribution was created in whole or in part by me and I
    have the right to submit it under the open source license
    indicated in the file; or

(b) The contribution is based upon previous work that, to the best
    of my knowledge, is covered under an appropriate open source
    license and I have the right under that license to submit that
    work with modifications, whether created in whole or in part
    by me, under the same open source license (unless I am
    permitted to submit under a different license), as indicated
    in the file; or

(c) The contribution was provided directly to me by some other
    person who certified (a), (b) or (c) and I have not modified
    it.

(d) I understand and agree that this project and the contribution
    are public and that a record of the contribution (including all
    personal information I submit with it, including my sign-off) is
    maintained indefinitely and may be redistributed consistent with
    this project or the open source license(s) involved.
```

## Pull Request Rules

Before opening a pull request:

- Read `README.md`, `SYSTEM.md`, and the files related to your change.
- Keep changes focused. Do not mix unrelated cleanup with behavior changes.
- Add or update tests when behavior changes.
- Update documentation when user-facing behavior, setup, policies, or prompts change.
- Do not commit secrets, live credentials, private customer data, or local machine state.
- Do not remove proof gates, quality gates, safety checks, or scope guardrails unless the pull request explains why and the maintainer explicitly approves it.

## Brand And Naming

The Apache 2.0 license does not grant permission to use the OneShot name, logo, or project identity in a way that suggests official status, endorsement, or ownership.

Forks and commercial distributions should use their own names. It is fine to describe truthful compatibility, such as "compatible with OneShot", as long as the wording does not imply the project is official. See [TRADEMARKS.md](TRADEMARKS.md).

## Security Issues

Please do not open public issues for vulnerabilities or exposed credentials. Follow [SECURITY.md](SECURITY.md).
