# Windows Compatibility Acceptance Report

Captured: `2026-05-10T17:27` local machine time  
Recommended commit name: `Finalize native Windows compatibility acceptance`

## Executive Verdict

OneShot's core platform workflow is now verified as native-Windows compatible on
this machine. The original Unix/macOS assumptions were concentrated in shell
selection, agent CLI paths, desktop launching, path serialization, Claude hooks,
and setup guidance. Those surfaces have been rewritten or guarded with tests.

This report does not claim that every optional integration is Windows-native.
Two bundled optional capabilities remain intentionally platform-specific:

- `vault/clients/_platform/mcps/computer-use`: macOS desktop automation using
  `screencapture`, `cliclick`, and `osascript`.
- `vault/clients/_platform/mcps/mlx-whisper`: Apple Silicon / MLX specific.

The core bootstrap, routing, vault scripts, release verification,
walkthrough-planning, path handling, and Claude hook safety layer are covered by
native-Windows test evidence.

## Windows Test Environment

Observed on this machine:

| Component | Evidence |
|---|---|
| OS | `Microsoft Windows NT 10.0.26200.0` |
| PowerShell | `5.1.26100.8115` |
| Python | `Python 3.13.13` |
| Git | `git version 2.53.0.windows.1` |
| Node | `v24.13.1` |
| ripgrep | `ripgrep 15.1.0` |
| ffmpeg | Not installed / not on PATH |

## What Was Rewritten

### Platform Detection And Shell Execution

Added `scripts/platform_support.py`.

Purpose:

- Detect `windows`, `macos`, `linux`, and `wsl`.
- Avoid POSIX shell injection into native Windows subprocess calls.
- Select desktop launch behavior per host.
- Select desktop capture backend per host:
  - Windows -> `gdigrab`
  - macOS -> `avfoundation`
  - Linux/WSL -> `x11grab`

Critical replacement:

```text
Before: subprocess.run(..., shell=True, executable="/bin/zsh")
After:  subprocess.run(..., **shell_run_kwargs())
```

### Release Verification

Updated `scripts/verify_release.py`.

Result:

- Native Windows uses the default Python/COMSPEC shell behavior.
- POSIX systems still use the available shell (`$SHELL`, `zsh`, `bash`, or `sh`).
- Verified with normal paths and a Windows workdir containing spaces.

### Agent Runtime

Updated `scripts/agent_runtime.py`.

Changes:

- Default Codex/Gemini routing no longer hardcodes Homebrew paths.
- CLI splitting handles quoted Windows executable paths, e.g.
  `C:\Program Files\Codex\codex.exe`.
- Frontmatter strings with Windows backslashes round-trip without doubled slashes.
- Stitch proxy Node detection accepts `node.exe`.

### Desktop Launch And Walkthrough Capture

Updated:

- `scripts/ensure_qc_walkthrough.py`
- `scripts/capture_walkthrough_video.py`

Changes:

- Removed hardcoded macOS `open`.
- Windows launch uses `os.startfile`.
- Linux launch uses `xdg-open` when available.
- Desktop capture command construction supports `gdigrab`, `avfoundation`, and
  `x11grab`.

Runtime note:

- ffmpeg is required for actual desktop video capture.
- ffmpeg is not installed on this machine, so the test suite verifies the
  Windows backend command generation and graceful prerequisite failure, while
  skipping the synthetic ffmpeg video fixture.

### Project And Artifact Path Handling

Updated:

- `scripts/build_project_context.py`
- `scripts/plan_phase_adversarial_probe.py`

Changes:

- Paths inside the OneShot repo serialize as forward-slash vault paths even on
  Windows, e.g. `vault/clients/acme/projects/demo.md`.
- Windows absolute workspace paths are discovered, e.g.
  `C:\Users\Leo\Documents\GitHQ\sample-app`.
- Brief-resolution references support both Unicode arrows and ASCII arrows:
  `→` and `->`.

### Claude Hooks

Replaced Bash hooks with Python hooks:

- `.claude/hooks/verify_first.py`
- `.claude/hooks/validate_bash.py`
- `.claude/hooks/restrict_paths.py`
- `.claude/hooks/audit_log.py`

Removed legacy `.sh` hooks after verifying `.claude/settings.json` points only
to Python hook entrypoints.

Windows-specific safety checks now include:

- PowerShell-style destructive delete blocking.
- File-write restriction outside platform root.
- Protection for `.claude/settings.json`.
- Cross-platform audit log writes.

### Documentation And CI

Updated:

- `README.md`
- `docs/SETUP.md`
- `docs/QUICKSTART.md`
- `docs/PUBLISHING.md`
- `AGENTS.md`
- `CLAUDE.md`
- `SYSTEM.md`
- `vault/SCHEMA.md`
- affected skills under `skills/`

Changes:

- WSL is documented as optional, not required for core OneShot.
- Windows PowerShell setup is documented.
- Timestamp instructions include PowerShell.
- Package-manager examples include Windows where relevant.
- `.github/workflows/ci.yml` now includes `windows-latest` in the test matrix.

## Edge Cases Verified

The compatibility suite now checks the exact classes of failures that made the
repo Unix-biased before this work:

| Edge Case | Test Evidence |
|---|---|
| Native Windows shell execution does not request `/bin/zsh` | `test_detect_host_identifies_windows_and_wsl` |
| Fresh checkout verifier runs under native Windows shell | `test_verify_release_command_runner_uses_available_native_shell` |
| Fresh checkout verifier works in paths containing spaces | `test_verify_release_handles_windows_workdirs_with_spaces` |
| Quoted Windows CLI path with spaces is split correctly | `test_agent_runtime_splits_quoted_windows_cli_paths` |
| Windows backslash paths round-trip through frontmatter | `test_frontmatter_windows_paths_round_trip_without_extra_slashes` |
| Repo-relative paths serialize as slash paths | `test_platform_relative_paths_are_posix_inside_repo` |
| Windows absolute workspaces are discovered from project text | `test_context_extractor_recognizes_windows_absolute_workspaces` |
| Windows brief paths parse from `->` references | `test_phase_probe_regex_recognizes_windows_brief_paths` |
| Windows desktop capture backend is `gdigrab` | `test_platform_support_maps_windows_desktop_capture_backend` |
| Windows app launch uses `os.startfile` | `test_windows_launch_path_uses_startfile_without_posix_launcher` |
| QC walkthrough desktop path uses cross-platform launcher | `test_ensure_qc_walkthrough_desktop_path_uses_cross_platform_launcher` |
| PowerShell destructive delete is blocked | `test_python_validate_bash_hook_blocks_powershell_destructive_delete` |
| Hook blocks secret exfiltration command shape | `test_python_validate_bash_hook_blocks_secret_exfiltration` |
| Hook blocks writes outside platform root | `test_python_restrict_paths_hook_blocks_writes_outside_platform` |
| Hook blocks `.claude/settings.json` mutation | `test_python_restrict_paths_hook_blocks_settings_json_write` |
| Python audit hook writes an audit log | `test_python_audit_log_hook_writes_cross_platform_log` |
| CI includes native Windows | `test_ci_runs_on_native_windows` |
| Claude hooks are Python, not Bash scripts | `test_claude_hooks_use_python_entrypoints_not_bash_scripts` |
| Core runtime does not reintroduce POSIX/Homebrew assumptions | `test_core_runtime_has_no_hardcoded_posix_shell_or_homebrew_paths` |

## Commands Run And Results

### Targeted Windows Compatibility Tests

Command:

```powershell
python -m pytest tests\test_windows_compatibility.py tests\test_cross_platform_contracts.py -q
```

Result:

```text
25 passed in 0.51s
```

### Full Test Suite

Command:

```powershell
python -m pytest tests -q
```

Result:

```text
281 passed, 1 skipped in 9.55s
```

The single skipped test is the ffmpeg-dependent synthetic video fixture. ffmpeg
is not installed on this Windows machine.

### Release Verification Smoke Test

Command:

```powershell
python .\scripts\verify_release.py --source .\docs --command "python --version" --artifact SETUP.md --timeout-seconds 15
```

Result:

```text
verdict=PASS
commands_passed=1/1
artifacts_passed=1/1
warning_lines=0
```

### Bootstrap CLI Smoke Test

Command:

```powershell
python .\oneshot.py --version
```

Result:

```text
oneshot 1.0.0
```

### Agent Mode Read Test

Command:

```powershell
python .\scripts\set_agent_mode.py
```

Result:

```text
chat_native
```

### QC Walkthrough Planning Smoke Test

Command shape:

```powershell
python .\scripts\ensure_qc_walkthrough.py --deliverables-root <workspace-smoke-dir> --brief <brief> --plan-only --json-out <report>
```

Result:

```text
requirement=required
mode=web
status=planned-only
output=<workspace-smoke-dir>\qc-walkthrough.mp4
```

This verifies native Windows path handling through the walkthrough planner.

### Desktop Capture Prerequisite Check

Command:

```powershell
python .\scripts\capture_walkthrough_video.py desktop --list-devices
```

Result:

```text
ffmpeg is required but was not found in PATH.
```

This is a correct prerequisite failure, not a path/shell failure. The Windows
backend command generation is covered by tests; actual desktop capture requires
installing ffmpeg.

### Package Manager Check

Command:

```powershell
winget --version
```

Result:

```text
Program 'winget.exe' failed to run: A specified logon session does not exist.
```

Because `winget` is unavailable in this session, ffmpeg installation was not
attempted through the test run. The setup documentation now names host package
manager options instead of assuming Homebrew.

## Static Review Findings

The compatibility scan no longer finds active core-runtime uses of:

- `/bin/zsh`
- `/opt/homebrew/bin/codex`
- `/opt/homebrew/bin/gemini`
- hardcoded `subprocess.run(["open", ...])`
- `.claude/settings.json` references to `.sh` hooks

Remaining `python3` strings are either Unix shebangs, Linux setup examples, or
legacy script docstring examples. They are not active Windows runtime blockers.

## Conclusion

The repository has moved from "works smoothly only under macOS/Unix assumptions"
to "core OneShot runs and is tested on native Windows." The proof is not just a
manual smoke run; it is now enforced by:

- Native Windows local test execution.
- A Windows CI matrix leg.
- Static no-regression contract tests.
- Edge-case unit tests covering Windows paths, quoting, launch behavior,
  frontmatter serialization, and hook safety.

The remaining non-Windows pieces are optional integrations with explicit
platform requirements, not part of the core OneShot control plane.
