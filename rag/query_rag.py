from __future__ import annotations

import argparse
import json

from rag.config import CHROMA_DIR, COLLECTION_NAME
from rag.embeddings import SpurEmbedder


def query(text: str, n: int = 5, doc_type: str | None = None) -> list[dict]:
    import chromadb
    from chromadb.config import Settings

    client = chromadb.PersistentClient(
        path=str(CHROMA_DIR),
        settings=Settings(anonymized_telemetry=False),
    )
    collection = client.get_collection(COLLECTION_NAME)
    embedder = SpurEmbedder()
    vector = embedder.embed([text])[0]
    where = {"doc_type": doc_type} if doc_type else None
    result = collection.query(
        query_embeddings=[vector],
        n_results=n,
        where=where,
        include=["documents", "metadatas", "distances"],
    )
    hits = []
    for i in range(len(result["ids"][0])):
        hits.append(
            {
                "id": result["ids"][0][i],
                "distance": result["distances"][0][i],
                "metadata": result["metadatas"][0][i],
                "document": result["documents"][0][i],
            }
        )
    return hits


def main() -> int:
    parser = argparse.ArgumentParser(description="Query the local F1 Chroma RAG index")
    parser.add_argument("question", help="Natural language query")
    parser.add_argument("-n", type=int, default=5, help="Number of results")
    parser.add_argument(
        "--type",
        dest="doc_type",
        default=None,
        help="Optional doc_type filter (race_control, strategy_summary, ...)",
    )
    args = parser.parse_args()
    hits = query(args.question, n=args.n, doc_type=args.doc_type)
    print(json.dumps(hits, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
