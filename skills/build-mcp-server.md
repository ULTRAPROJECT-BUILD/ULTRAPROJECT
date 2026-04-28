---
type: skill
name: build-mcp-server
description: Builds a Python MCP server from scratch when source-capability finds nothing reusable
inputs:
  - name (required — server name, kebab-case)
  - description (required — what the MCP does)
  - tools (required — list of tools with name, description, parameters, return values)
  - api_docs (optional — URL or content of API documentation)
  - client (optional — client slug for client-scoped placement)
---

# Build MCP Server

You are building a Python MCP server from scratch. This is Tier 3 of the sourcing cascade — marketplace and archive had nothing usable.

## Output Location

- **Client-scoped (when building for a specific client project):** `vault/clients/{client}/mcps/{name}/`
- **Platform-scoped:** `vault/clients/_platform/mcps/{name}/`
- **grow-capabilities sourcing:** Always use platform-scoped path. NEVER write to client directories when sourcing for the grow-capabilities project.

## Template

Every MCP server follows this structure:

```
{name}/
├── server.py          ← main MCP server
├── requirements.txt   ← Python dependencies
└── README.md          ← setup instructions
```

## server.py Template

```python
"""
{name} MCP Server
{description}
"""

import os
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("{name}")


# --- Configuration ---

# Read config from environment variables
# API_KEY = os.environ.get("{NAME}_API_KEY", "")
# BASE_URL = os.environ.get("{NAME}_BASE_URL", "https://api.example.com")


# --- Tools ---

@mcp.tool()
def tool_name(param1: str, param2: int = 10) -> str:
    """Tool description — what it does and when to use it.

    Args:
        param1: Description of param1
        param2: Description of param2 (default: 10)

    Returns:
        Description of return value
    """
    try:
        # Implementation here
        return "result"
    except Exception as e:
        return f"Error: {str(e)}"


# --- Entry Point ---

if __name__ == "__main__":
    mcp.run()
```

## Build Process

### Step 1: Design the Tools

For each tool in the requirements:
1. Define the function signature (name, parameters with types, return type).
2. Write the docstring (description, args, returns).
3. Plan the implementation (API calls, data processing, file operations).

### Step 2: Identify Dependencies

- What Python packages are needed? (e.g., `requests`, `stripe`, `web3`)
- What environment variables are needed? (API keys, URLs, credentials)
- What system requirements exist? (e.g., macOS for AppleScript, specific CLI tools)

### Step 3: Write the Code

1. Start from the template above.
2. Implement each tool function.
3. Add proper error handling — every tool should catch exceptions and return error messages, never crash.
4. Use type hints for all parameters and return values.
5. Read configuration from environment variables, NEVER hardcode secrets.

### Step 4: Write requirements.txt

```
mcp
{additional packages}
```

### Step 5: Write README.md

```markdown
# {name} MCP Server

{description}

## Setup

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| {VAR} | Yes | {description} |

### Install Dependencies

\`\`\`bash
pip install -r requirements.txt
\`\`\`

## Tools

| Tool | Description |
|------|-------------|
| {tool_name} | {description} |

## Registration

Add to `.mcp.json`:
\`\`\`json
{
  "{name}": {
    "type": "stdio",
    "command": "python3",
    "args": ["{path}/server.py"],
    "env": {}
  }
}
\`\`\`
```

### Step 6: Test

Run [[test-mcp-server]] skill to validate:
- Server starts without errors
- Each tool responds to calls
- Error handling works (bad inputs don't crash the server)

## Code Quality Rules

1. **Never hardcode secrets** — always use environment variables.
2. **Always handle errors** — wrap API calls in try/except, return descriptive error messages.
3. **Use type hints** — every function parameter and return value must be typed.
4. **Docstrings on every tool** — the MCP protocol uses these for tool descriptions.
5. **Keep it simple** — one file per MCP. Only split into modules if the server exceeds 300 lines.
6. **Idempotent where possible** — tools should be safe to retry.
7. **Log sparingly** — use `print()` to stderr for debugging, but don't flood output.

## The Three-File FastMCP Standard

**Every MCP server MUST follow this structure:** `server.py` + `requirements.txt` + `README.md`. This is the proven standard — 10 MCPs were built in a single sprint using this pattern and all worked at scale. Key conventions:

- **Pure Python with minimal deps** — prefer `fpdf2` over `weasyprint`, `Pillow` for images, `requests` + `bs4` for scraping. No system-level dependencies; everything installable via pip.
- **Env vars for all credentials** — `UNSPLASH_ACCESS_KEY`, `NETLIFY_AUTH_TOKEN`, etc. Never hardcode keys.
- **Structured JSON returns** with error handling for every tool — consistent response format across all MCPs.
- **Same pattern for internal and archived MCPs** — the archive at `vault/archive/mcps/{name}/` always contains these 3 files.
- **A standard MCP takes 3-5 minutes to build** with this pattern. If a build is taking significantly longer, check whether the scope is too broad (split into multiple MCPs) or the dependencies are too heavy (find simpler alternatives).

(Learned from 2026-03-18-capability-sprint-fastmcp-standardization, 2026-03-18)

## Anti-Patterns to Avoid

- Don't create MCP servers that expose dangerous operations (file deletion, system commands) without explicit safety checks.
- Don't build a monolithic MCP — each MCP should serve one domain (email, payments, etc.).
- Don't include test code in the production server file.
- Don't use global mutable state between tool calls.

## Output

Return:
- Server file path
- Requirements file path
- List of tools implemented
- Environment variables needed
- Any issues or notes for the operator

## See Also

- [[test-mcp-server]]
- [[register-mcp]]
- [[source-capability]]
- [[archive-capability]]
