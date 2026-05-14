from __future__ import annotations

import os
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SERVER_PATH = REPO_ROOT / "tools" / "stitch-mcp-proxy" / "server.mjs"


def test_stitch_proxy_exits_cleanly_when_api_key_missing():
    env = os.environ.copy()
    env.pop("STITCH_API_KEY", None)
    env["STITCH_PROXY_SKIP_REPO_ENV"] = "1"
    result = subprocess.run(
        ["node", str(SERVER_PATH)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        env=env,
        timeout=10,
    )
    assert result.returncode == 1
    assert "STITCH_API_KEY" in result.stderr
    assert ".env" in result.stderr
