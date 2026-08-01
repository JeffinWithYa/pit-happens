#!/usr/bin/env python3
"""Minimal Streamable-HTTP MCP tool caller for smoke tests."""
from __future__ import annotations

import json
import sys
import urllib.request

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8765/mcp"
TOOL = sys.argv[2] if len(sys.argv) > 2 else "rf1_live_summary"
ARGS = json.loads(sys.argv[3]) if len(sys.argv) > 3 else {}


def post(payload: dict, session: str | None = None) -> tuple[dict | None, str | None]:
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    if session:
        headers["Mcp-Session-Id"] = session
    req = urllib.request.Request(
        URL,
        data=json.dumps(payload).encode(),
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        sid = resp.headers.get("Mcp-Session-Id")
        body = resp.read().decode("utf-8", errors="replace")
        # Handle optional SSE wrapping
        if body.startswith("event:") or "data:" in body:
            for line in body.splitlines():
                if line.startswith("data:"):
                    body = line[5:].strip()
                    break
        return json.loads(body), sid


init, sid = post(
    {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "call-tool", "version": "0.1"},
        },
    }
)
post(
    {"jsonrpc": "2.0", "method": "notifications/initialized"},
    session=sid,
)
result, _ = post(
    {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {"name": TOOL, "arguments": ARGS},
    },
    session=sid,
)
print(json.dumps(result, indent=2, ensure_ascii=False)[:3000])
