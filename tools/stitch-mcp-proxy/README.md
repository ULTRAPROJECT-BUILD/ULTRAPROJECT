# Stitch MCP Proxy

A thin stdio MCP server that bridges [Google Stitch](https://stitch.withgoogle.com/) into the Model Context Protocol so agents (Claude Code, Codex, etc.) can drive Stitch's design generation through standard MCP tool calls.

## What it does

- Reads `STITCH_API_KEY` from the environment, or from the platform repo's `.env` file.
- Exposes the Stitch SDK over an MCP stdio transport so any MCP-aware client can use it.

## Install

From the repo root:

```bash
cd tools/stitch-mcp-proxy
npm install
```

## Configure

Add `STITCH_API_KEY` to the repo's `.env`:

```bash
echo "STITCH_API_KEY=<your-key-here>" >> .env
```

Or export it in the shell where you start Claude / Codex.

## Wire into MCP

The repo's `.mcp.template.json` includes the MCP registry shape. Add a `stitch` server entry like this:

```json
{
  "mcpServers": {
    "stitch": {
      "type": "stdio",
      "command": "node",
      "args": ["tools/stitch-mcp-proxy/server.mjs"],
      "env": { "STITCH_API_KEY": "replace-with-stitch-api-key" }
    }
  }
}
```

Copy `.mcp.template.json` → `.mcp.json`, add the entry, fill in the key, and restart your agent.

## Skip the repo `.env`

If you'd rather only read the key from `process.env` and ignore the repo's `.env` file (e.g. running in CI):

```bash
STITCH_PROXY_SKIP_REPO_ENV=1 STITCH_API_KEY=<your-key> node server.mjs
```

## Notes

- The proxy exits with a clear error if `STITCH_API_KEY` is missing.
- It handles `SIGINT` / `SIGTERM` and closes the SDK cleanly.
- This is a thin scaffold — you can fork and extend it with custom Stitch flows if your agents need more than the SDK's defaults.
