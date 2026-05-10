---
type: skill
name: register-mcp
description: Adds a built MCP server to .mcp.json so Claude Code can use it
inputs:
  - name (required — server name, must match the MCP server's FastMCP name)
  - server_path (required — absolute path to server.py)
  - env_vars (optional — dict of environment variable names and descriptions)
  - client (optional — client slug, for documentation purposes)
---

# Register MCP

You are registering an MCP server so Claude Code can discover and use its tools.

## Process

### Step 1: Read Current Config

1. Read `.mcp.json` at the project root.
2. If the file doesn't exist, create it with an empty `mcpServers` object:
   ```json
   {
     "mcpServers": {}
   }
   ```

### Step 2: Security Review (MANDATORY — blocks registration)

Before registering, run a Codex security audit on ALL source files in the MCP directory:
```
codex exec "Security audit {path}/. Check every source file for: network calls to unexpected hosts, filesystem access outside expected scope, env var reads beyond documented keys, eval/exec/subprocess, obfuscated code, dependency risks. Verdict: PASS / FAIL with specific issues."
```
- **PASS:** proceed to Step 2b (admin approval).
- **FAIL:** do NOT register. Log issues in the ticket work log. Create a fix task. Stop here.
- If Codex is unavailable: do NOT register. Flag for admin review.

### Step 2b: Admin Approval (MANDATORY — blocks registration)

After Codex passes the security review, **request admin approval** before registering:

1. Write an admin approval request in the relevant ticket/project log and surface it in chat with:
   - Subject: "🔒 Approval needed: register MCP '{name}'"
   - Body: MCP name, server path, what it does, what tools it exposes, what env vars it needs, and the Codex security review verdict.
2. Create a ticket with `status: waiting`, `assignee: human`, `priority: high`:
   - Title: "Approve MCP registration: {name}"
   - Description: include the same details from the approval request.
3. **STOP and wait.** Do NOT proceed to Step 3 until the admin approves the ticket (status changed to `closed` by admin or manual update).
4. If admin denies: do NOT register. Close the ticket. Stop here.

**Why:** MCP servers are executable code with env var access and network capabilities. No MCP should be registered without human review, regardless of what the automated gate review says.

### Step 3: Validate the MCP Server

Before registering, verify:
1. The `server.py` file exists at the specified path.
2. A `requirements.txt` exists in the same directory.
3. The server file imports from `mcp.server.fastmcp`.

### Step 3: Install Dependencies

1. Read the `requirements.txt` from the MCP server directory.
2. Run `pip install -r {path}/requirements.txt` to install dependencies.
3. If installation fails, report the error and do NOT proceed with registration.

### Step 4: Build the Registration Entry

```json
{
  "mcpServers": {
    "{name}": {
      "type": "stdio",
      "command": "python",
      "args": ["{absolute_path_to_server.py}"],
      "env": {
        "{VAR_NAME}": "{value_or_placeholder}"
      }
    }
  }
}
```

**Environment variables:**
- For platform MCPs: read actual values from the system environment or platform config.
- For client MCPs: use placeholder values that the operator fills in.
- NEVER write actual API keys or passwords into `.mcp.json` — use environment variable references.

### Step 5: Admin Writes the Registration to .mcp.json

**Agents cannot write to `.mcp.json` directly** — it is protected by the restrict-paths hook. After admin approval (Step 2b), the agent must:

1. Prepare the full JSON entry that should be added (server name, path, env vars).
2. Include the exact JSON snippet in the approval email and ticket from Step 2b.
3. **The admin performs the actual `.mcp.json` edit** — either manually or by running the agent in interactive mode with explicit permission.
4. If an entry with the same name already exists:
   - **If the path is the same:** note this in the approval request (update vs. new).
   - **If the path is different:** warn the admin and let them decide.

### Step 6: Verify Registration

1. Read `.mcp.json` again to confirm the entry was written correctly.
2. Verify the JSON is valid (no syntax errors).

## Output

Return:
- Server name registered
- Path to server.py
- Environment variables configured
- Whether this was a new registration or an update
- `.mcp.json` file path

## Notes

- Claude Code reads `.mcp.json` on startup. After registering a new MCP, the user may need to restart Claude Code for the tools to become available.
- The `.mcp.json` file should be at the project root directory.
- Multiple MCP servers can coexist — each gets its own entry in `mcpServers`.

## See Also

- [[build-mcp-server]]
- [[test-mcp-server]]
- [[source-capability]]
