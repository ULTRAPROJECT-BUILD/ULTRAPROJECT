---
type: skill
name: test-mcp-server
description: Validates an MCP server with unit, protocol, and integration tests
inputs:
  - server_path (required — path to the MCP server directory containing server.py)
  - tools (optional — list of tool names to test; if omitted, tests all discovered tools)
  - test_inputs (optional — dict of tool_name → list of test input dicts)
---

# Test MCP Server

You are testing an MCP server to verify it works correctly before deployment.

## Test Levels

### Level 1: Structural Validation

1. **File check:**
   - `server.py` exists and is valid Python (no syntax errors).
   - `requirements.txt` exists.
   - `README.md` exists.

2. **Import check:**
   - Run `python3 -c "import ast; ast.parse(open('{server_path}/server.py').read())"` to verify syntax.
   - Check that the file imports from `mcp.server.fastmcp`.
   - Check that it creates a `FastMCP` instance.
   - Check that it has at least one `@mcp.tool()` decorated function.

3. **Dependency check (read-only):**
   - Read `requirements.txt` and verify all listed packages are either already installed or are well-known packages (requests, mcp, beautifulsoup4, etc.).
   - Do NOT run `pip install` until AFTER the security review passes (Level 1.5). This applies to ALL MCPs — external and internal.

### Level 1.5: Security Review (MANDATORY before Level 2 — ALL MCPs)

Run a Codex security audit before installing dependencies or starting the server. This applies to ALL MCPs — externally sourced AND internally built. See [[register-mcp]] Step 2 for the audit process.
- **PASS:** proceed to Level 2.
- **FAIL:** stop testing. Do not install, do not start. Log issues and create a fix task.

### Level 2: Server Startup Test (only after security review PASS)

1. Install dependencies: `pip install -r {server_path}/requirements.txt`
2. Start the server in a subprocess:
   ```bash
   cd {server_path} && timeout 10 python3 server.py &
   ```
3. Wait 3 seconds for startup.
4. Check if the process is still running (didn't crash on startup).
5. Kill the process.

**If startup fails:** Read stderr output for the error message. Common issues:
- Missing environment variables → set dummy values for testing.
- Missing dependencies → install them.
- Port conflicts → not applicable for stdio MCP servers.

### Level 3: Tool Invocation Test

For each tool in the MCP server:

1. **Discover tools** — read the server.py source code and find all `@mcp.tool()` decorated functions. Extract:
   - Function name
   - Parameters (names, types, defaults)
   - Return type
   - Docstring

2. **Generate test inputs** — if `test_inputs` not provided:
   - For `str` params: use a reasonable test string (e.g., "test@example.com" for email params).
   - For `int` params: use the default or 1.
   - For `bool` params: test both True and False.
   - For optional params: test with and without them.

3. **Call the tool** — use the MCP to invoke the tool with test inputs.

4. **Validate response:**
   - Did it return without crashing?
   - Is the return value the expected type?
   - Does the response contain an error message? (Some errors are expected with test data — e.g., invalid API key.)
   - Distinguish between "tool works but test data is bad" vs "tool is broken."

### Level 4: Error Handling Test

For each tool:
1. Call with missing required parameters → should return a clear error, not crash.
2. Call with wrong types → should return a clear error, not crash.
3. Call with empty strings → should handle gracefully.

## Test Report

Generate a test report:

```markdown
## MCP Test Report: {server_name}

**Server:** {server_path}
**Date:** {now}
**Overall:** PASS / FAIL / PARTIAL

### Structural Validation
- [x] server.py exists and valid Python
- [x] requirements.txt exists
- [x] Imports FastMCP correctly
- [x] Has tool decorators

### Server Startup
- [x] Starts without crashing
- [x] Exits cleanly

### Tool Tests
| Tool | Input | Result | Notes |
|------|-------|--------|-------|
| example_tool | {test input} | PASS | Returns expected format |
| credentialed_tool | {test input} | EXPECTED_FAIL | No credentials in test |

### Error Handling
| Tool | Test | Result |
|------|------|--------|
| check_email | Missing params | PASS — returns error message |
| send_email | Wrong types | PASS — returns error message |

### Artifact Evidence
| Tool | Artifact Path | Size / Proof | Result |
|------|---------------|--------------|--------|
| render_image | /abs/path/render.png | 247KB, 1920x1080 | PASS |
| export_zip | /abs/path/site.zip | 38KB, unzip lists 3 files | PASS |

### Issues Found
- {issue description and severity}

### Recommendation
DEPLOY / FIX_THEN_DEPLOY / DO_NOT_DEPLOY
```

## Artifact Verification (Critical)

**Do not report a tool as PASS based on code review alone.** If a tool is supposed to produce output (files, images, data), you MUST verify the output exists:

1. After calling a tool that generates files, check that the file exists on disk (`ls`, `stat`, or read it).
2. Verify the file is non-empty and the correct type (e.g., a PNG should be a valid image, not 0 bytes).
3. If the tool claims to have created something but no artifact exists, the test is **FAIL** — not PASS.
4. Log the actual file paths and sizes in the **Artifact Evidence** section of the test report as proof.

**The distinction:** "The code looks like it would render an image" is not a test result. "I ran the tool and confirmed `/path/to/render.png` exists (247KB, 1920x1080)" is a test result.

## Notes

- Some tools will legitimately fail with test data (e.g., email tools without real credentials). This is an EXPECTED_FAIL, not a real failure.
- The goal is to verify the server is structurally sound AND produces real output. Structural validation alone is insufficient.
- If testing a marketplace-sourced skill, be extra thorough — these may have bugs or compatibility issues.

## See Also

- [[build-mcp-server]]
- [[register-mcp]]
- [[source-capability]]
- [[quality-check]]
