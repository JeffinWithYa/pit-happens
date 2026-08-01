#!/usr/bin/env python3
"""Run inside WSL: python3 scripts/probe_mcp_from_wsl.py"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request


def windows_host_ip() -> str:
    with open("/etc/resolv.conf", encoding="utf-8") as fh:
        for line in fh:
            m = re.match(r"nameserver\s+(\S+)", line.strip())
            if m:
                return m.group(1)
    raise RuntimeError("Could not find Windows host IP in /etc/resolv.conf")


def probe(url: str) -> None:
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "wsl-probe", "version": "0.1"},
        },
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        },
        method="POST",
    )
    print(f"Probing {url}")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            print(f"STATUS:{resp.status}")
            print(body[:1200])
    except Exception as exc:  # noqa: BLE001
        print(f"FAILED: {exc}")


if __name__ == "__main__":
    ip = windows_host_ip()
    print(f"WIN_IP={ip}")
    probe(f"http://{ip}:8765/mcp")
    probe("http://127.0.0.1:8765/mcp")
