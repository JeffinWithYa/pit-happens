#!/usr/bin/env bash
# Hermes stdio launcher (run from WSL).
# Uses Windows Python + the Windows-side Chroma index.
set -eu
ROOT="/mnt/c/Users/jjeya/Desktop/rfactor1_gemma"
PY="/mnt/c/Users/jjeya/AppData/Local/Programs/Python/Python312/python.exe"
export PYTHONPATH="$ROOT"
# Load SPUR_EMBED_TOKEN from Windows .env without printing secrets
if [[ -f "$ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source <(tr -d '\r' < "$ROOT/.env" | grep -E '^[A-Za-z_][A-Za-z0-9_]*=')
  set +a
fi
cd "$ROOT"
exec "$PY" -m rag.mcp_server
