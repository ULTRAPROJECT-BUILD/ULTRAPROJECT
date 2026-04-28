"""
Example MCP Server — Template
This is a reference MCP server that agents can learn from when building new ones.
Copy this directory as a starting point for client-specific MCP servers.
"""

import os
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("example")

# --- Configuration ---
# Always read secrets from environment variables, NEVER hardcode them
API_KEY = os.environ.get("EXAMPLE_API_KEY", "")
BASE_URL = os.environ.get("EXAMPLE_BASE_URL", "https://api.example.com")


# --- Tools ---

@mcp.tool()
def hello(name: str = "World") -> str:
    """A simple greeting tool for testing.

    Args:
        name: The name to greet (default: World)

    Returns:
        A greeting string
    """
    return f"Hello, {name}! This MCP server is working correctly."


@mcp.tool()
def get_config() -> str:
    """Returns the current configuration (without secrets).

    Returns:
        Configuration summary showing what env vars are set
    """
    return (
        f"API_KEY: {'configured' if API_KEY else 'NOT SET'}\n"
        f"BASE_URL: {BASE_URL}"
    )


# --- Entry Point ---

if __name__ == "__main__":
    mcp.run()
