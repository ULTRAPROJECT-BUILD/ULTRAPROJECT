# Example MCP Server

This is a template MCP server. Copy this directory when building new client-specific MCPs.

## Structure

```
_example/
├── server.py          ← main server code
├── requirements.txt   ← Python dependencies
└── README.md          ← this file
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| EXAMPLE_API_KEY | No | Demo API key (not used) |
| EXAMPLE_BASE_URL | No | Demo base URL (default: https://api.example.com) |

## Usage

```bash
pip install -r requirements.txt
python3 server.py
```

## Adding to .mcp.json

```json
{
  "example": {
    "type": "stdio",
    "command": "python3",
    "args": ["path/to/server.py"],
    "env": {
      "EXAMPLE_API_KEY": "your-key-here"
    }
  }
}
```
