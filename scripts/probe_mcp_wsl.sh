#!/usr/bin/env bash
set -euo pipefail
WIN_IP=$(grep -m1 nameserver /etc/resolv.conf | awk '{print $2}')
echo "WIN_IP=$WIN_IP"
URL="http://${WIN_IP}:8765/mcp"
echo "URL=$URL"
curl -sS -m 10 -w "\nHTTP:%{http_code}\n" -X POST "$URL" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"0.1"}}}' \
  | head -c 1200
echo
