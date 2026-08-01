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

from mcp.server import MCPServer
from mcp.server.transport_security import TransportSecuritySettings

from rag.config import CHROMA_DIR, COLLECTION_NAME
from rag.query_rag import query as rag_query

mcp = MCPServer(
    name="f1-rag",
    instructions=(
        "Formula 1 RAG over FastF1-derived docs: race control, lap/stint/strategy "
        "summaries, incidents, driver comparisons, turning points, regulations, "
        "and track guides (2024–2025 Race + Sprint)."
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
