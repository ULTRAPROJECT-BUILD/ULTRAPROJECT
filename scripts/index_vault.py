#!/usr/bin/env python3
"""
Incremental vault indexer — runs end of each runner cycle.
Embeds new/changed vault files into ChromaDB using Gemini embeddings.

Usage:
    python3 scripts/index_vault.py          # incremental (default)
    python3 scripts/index_vault.py --full   # full rebuild
"""

import json
import os
import sys

# Add the MCP server directory to path so we can reuse its functions
PLATFORM_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MCP_DIR = os.path.join(PLATFORM_DIR, "vault", "clients", "_platform", "mcps", "semantic-search")
sys.path.insert(0, MCP_DIR)

# Source .env if it exists
env_file = os.path.join(PLATFORM_DIR, ".env")
if os.path.exists(env_file):
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                os.environ.setdefault(key.strip(), val.strip())

from server import reindex


def main():
    full = "--full" in sys.argv

    result = reindex(full=full)
    data = json.loads(result)

    if "error" in data:
        print(f"Indexing error: {data['error']}", file=sys.stderr)
        sys.exit(1)

    added = data.get("added", 0)
    updated = data.get("updated", 0)
    skipped = data.get("skipped", 0)
    errors = data.get("errors", 0)

    if added + updated > 0:
        print(f"Indexed: {added} new, {updated} updated, {skipped} unchanged, {errors} errors")
    # Silent when nothing changed (most cycles)


if __name__ == "__main__":
    main()
