"""
F1 RAG MCP server for Hermes / other agents.

HTTP (reachable from WSL):
  python -m rag.mcp_server --http --host 0.0.0.0 --port 8765
  Endpoint: http://<windows-host>:8765/mcp

Stdio (local process):
  python -m rag.mcp_server
"""

from __future__ import annotations

import argparse
import json
import os
import time

import requests
from mcp.server import MCPServer
from mcp.server.transport_security import TransportSecuritySettings

from rag.config import CHROMA_DIR, COLLECTION_NAME
from rag.query_rag import query as rag_query
from telemetry_live import compact_frame
from telemetry_live import snapshot as rf1_snapshot
from telemetry_live import summarize as rf1_summarize

PITCALL_URL = os.getenv("PITCALL_URL", "http://127.0.0.1:3000").rstrip("/")

mcp = MCPServer(
    name="f1-rag",
    instructions=(
        "Capabilities:\n"
        "1) F1 RAG (f1_rag_search) over FastF1 strategy/incident/track docs.\n"
        "2) Live rFactor telemetry (rf1_live_summary / rf1_live_snapshot).\n"
        "3) PIT//CALL web wall: pitcall_push_live posts telemetry; "
        "pitcall_post_agent posts a short recommendation for TTS + UI.\n"
        "Workflow: read summary → optional RAG → pitcall_post_agent with speak<=30 words. "
        "Keep context light; do not dump full snapshots into chat."
    ),
)


@mcp.tool()
def f1_rag_search(
    question: str,
    n: int = 5,
    doc_type: str | None = None,
) -> str:
    """Search the local F1 RAG vector database.

    Args:
        question: Natural-language query about F1 races, strategy, incidents, etc.
        n: Number of chunks to return (1-12).
        doc_type: Optional filter. One of: race_control, lap_summary, stint_summary,
            strategy_summary, incident_summary, driver_comparison, turning_point,
            regulation, track_info.
    """
    n = max(1, min(int(n), 12))
    hits = rag_query(question, n=n, doc_type=doc_type)
    return json.dumps(
        {
            "query": question,
            "doc_type": doc_type,
            "collection": COLLECTION_NAME,
            "chroma_dir": str(CHROMA_DIR),
            "results": hits,
        },
        ensure_ascii=False,
        indent=2,
    )


@mcp.tool()
def f1_rag_status() -> str:
    """Return F1 RAG index status (collection name, path, document count)."""
    import chromadb
    from chromadb.config import Settings

    from rag.utils import dir_size_bytes, format_bytes

    client = chromadb.PersistentClient(
        path=str(CHROMA_DIR),
        settings=Settings(anonymized_telemetry=False),
    )
    collection = client.get_collection(COLLECTION_NAME)
    return json.dumps(
        {
            "ok": True,
            "collection": COLLECTION_NAME,
            "chroma_dir": str(CHROMA_DIR),
            "count": collection.count(),
            "size": format_bytes(dir_size_bytes(CHROMA_DIR)),
        },
        indent=2,
    )


@mcp.tool()
def rf1_live_summary() -> str:
    """Return a short live summary of the current rFactor 1 session.

    Prefer this for coaching / commentary. Reads Windows shared memory on demand
    (rFactor must be running with the SharedMemoryMap plugin).
    """
    return rf1_summarize()


@mcp.tool()
def rf1_live_snapshot() -> str:
    """Return full live rFactor 1 telemetry as JSON (car, player, standings, tyres).

    Use when you need exact numbers. Prefer rf1_live_summary for quick status.
    """
    return json.dumps(rf1_snapshot(), ensure_ascii=False, indent=2)


@mcp.tool()
def pitcall_push_live(base_url: str | None = None) -> str:
    """Push one compact live telemetry frame to the PIT//CALL Next.js /api/live endpoint.

    Args:
        base_url: Optional override (default PITCALL_URL or http://127.0.0.1:3000).
    """
    url = (base_url or PITCALL_URL).rstrip("/") + "/api/live"
    frame = compact_frame()
    if not frame.get("ok"):
        return json.dumps(frame, indent=2)
    payload = {k: v for k, v in frame.items() if k != "ok"}
    try:
        res = requests.post(url, json=payload, timeout=5)
        return json.dumps(
            {"ok": res.ok, "status": res.status_code, "url": url, "frame": payload},
            indent=2,
        )
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"ok": False, "error": str(exc), "url": url}, indent=2)


@mcp.tool()
def pitcall_post_agent(
    call: str,
    speak: str | None = None,
    confidence_pct: int = 75,
    evidence: list[str] | None = None,
    rag_refs: list[str] | None = None,
    regulation_citation: str | None = None,
    base_url: str | None = None,
) -> str:
    """Post a short Hermes pit-wall recommendation to PIT//CALL /api/agent (UI + TTS).

    Args:
        call: Decision text (e.g. 'STAY OUT. Manage rears.').
        speak: Optional TTS line (<= ~30 words). Defaults to call.
        confidence_pct: 0-100 confidence.
        evidence: Short evidence strings.
        rag_refs: Optional RAG citation titles.
        regulation_citation: Optional FIA article id.
        base_url: Optional Next.js base URL override.
    """
    url = (base_url or PITCALL_URL).rstrip("/") + "/api/agent"
    payload = {
        "ts": time.time(),
        "call": call,
        "speak": speak or call,
        "confidence_pct": int(confidence_pct),
        "evidence": (evidence or [])[:6],
        "rag_refs": (rag_refs or [])[:4],
        "regulation_citation": regulation_citation,
        # Transcript only — UI auto-TTS is reserved for AUTO RADIO (source=coach)
        "source": "hermes",
    }
    try:
        res = requests.post(url, json=payload, timeout=10)
        body: dict | str
        try:
            body = res.json()
        except Exception:  # noqa: BLE001
            body = res.text[:500]
        return json.dumps({"ok": res.ok, "status": res.status_code, "url": url, "body": body}, indent=2)
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"ok": False, "error": str(exc), "url": url}, indent=2)


def main() -> None:
    parser = argparse.ArgumentParser(description="F1 RAG MCP server")
    parser.add_argument(
        "--http",
        action="store_true",
        help="Serve Streamable HTTP (for Hermes on WSL)",
    )
    parser.add_argument("--host", default=os.getenv("F1_RAG_HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.getenv("F1_RAG_PORT", "8765")))
    args = parser.parse_args()

    if args.http:
        print(f"F1 RAG MCP listening on http://{args.host}:{args.port}/mcp")
        print(f"Chroma: {CHROMA_DIR}  collection={COLLECTION_NAME}")
        # Local-only RAG helper: allow WSL / Hyper-V hostnames and IPs.
        security = TransportSecuritySettings(
            enable_dns_rebinding_protection=False,
            allowed_hosts=["*"],
            allowed_origins=["*"],
        )
        mcp.run(
            transport="streamable-http",
            host=args.host,
            port=args.port,
            streamable_http_path="/mcp",
            json_response=True,
            stateless_http=True,
            transport_security=security,
        )
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
