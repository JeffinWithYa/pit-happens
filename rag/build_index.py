from __future__ import annotations

import argparse
import json
import shutil
import sys
from collections import Counter
from pathlib import Path

from tqdm import tqdm

from rag.config import (
    CHROMA_DIR,
    COLLECTION_NAME,
    DOCS_DIR,
    MAX_DB_BYTES,
    SEASONS,
    SESSION_TYPES,
)
from rag.embeddings import SpurEmbedder
from rag.fetch_sessions import configure_cache, iter_target_sessions, load_session
from rag.generate_docs import docs_for_session
from rag.static_docs import build_static_documents
from rag.utils import dir_size_bytes, format_bytes, read_jsonl, write_jsonl


def generate_all_docs(
    seasons: tuple[int, ...],
    session_types: tuple[str, ...],
    *,
    resume: bool = False,
) -> list[dict]:
    configure_cache()
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    all_docs: list[dict] = []
    targets = list(iter_target_sessions(seasons=seasons, session_types=session_types))
    print(f"Target sessions: {len(targets)} ({seasons=}, {session_types=})")

    for year, event, stype in tqdm(targets, desc="Sessions"):
        round_number = int(event["RoundNumber"])
        out = DOCS_DIR / f"{year}_R{round_number:02d}_{stype}.jsonl"
        if resume and out.exists() and out.stat().st_size > 0:
            docs = read_jsonl(out)
            all_docs.extend(docs)
            continue
        bundle = load_session(year, event, stype)
        if bundle is None:
            continue
        docs = docs_for_session(bundle)
        write_jsonl(out, docs)
        print(
            f"  {year} R{bundle.round_number} {stype} {bundle.event_name}: "
            f"{len(docs)} docs"
        )
        all_docs.extend(docs)

    static_docs = build_static_documents()
    write_jsonl(DOCS_DIR / "static_regs_tracks.jsonl", static_docs)
    all_docs.extend(static_docs)
    write_jsonl(DOCS_DIR / "all_docs.jsonl", all_docs)
    return all_docs


def load_docs_from_disk() -> list[dict]:
    all_path = DOCS_DIR / "all_docs.jsonl"
    if all_path.exists():
        return read_jsonl(all_path)
    docs: list[dict] = []
    for path in sorted(DOCS_DIR.glob("*.jsonl")):
        docs.extend(read_jsonl(path))
    return docs


def upsert_chroma(docs: list[dict], reset: bool = False) -> None:
    import chromadb
    from chromadb.config import Settings

    if reset and CHROMA_DIR.exists():
        shutil.rmtree(CHROMA_DIR)
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)

    client = chromadb.PersistentClient(
        path=str(CHROMA_DIR),
        settings=Settings(anonymized_telemetry=False),
    )
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )

    embedder = SpurEmbedder()
    # Probe embedding dimension once.
    probe = embedder.embed(["dimension probe"])
    dim = len(probe[0])
    print(f"Embedding model={embedder.model} dim={dim}")

    batch = 32
    for i in tqdm(range(0, len(docs), batch), desc="Indexing"):
        chunk = docs[i : i + batch]
        ids = [d["id"] for d in chunk]
        texts = [d["text"] for d in chunk]
        metas = [d.get("metadata") or {} for d in chunk]
        vectors = embedder.embed(texts)
        collection.upsert(ids=ids, documents=texts, metadatas=metas, embeddings=vectors)

    count = collection.count()
    print(f"Chroma collection '{COLLECTION_NAME}' count={count}")


def size_report() -> None:
    chroma_size = dir_size_bytes(CHROMA_DIR)
    docs_size = dir_size_bytes(DOCS_DIR)
    cache_size = dir_size_bytes(Path("data/fastf1_cache"))
    print("Size report:")
    print(f"  docs:   {format_bytes(docs_size)}")
    print(f"  chroma: {format_bytes(chroma_size)}")
    print(f"  cache:  {format_bytes(cache_size)} (not part of vector DB)")
    if chroma_size > MAX_DB_BYTES:
        raise SystemExit(
            f"Chroma DB exceeds cap ({format_bytes(chroma_size)} > {format_bytes(MAX_DB_BYTES)})"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build F1 RAG Chroma index from FastF1")
    parser.add_argument(
        "--seasons",
        type=int,
        nargs="+",
        default=list(SEASONS),
        help="Seasons to include (default: 2024 2025)",
    )
    parser.add_argument(
        "--sessions",
        nargs="+",
        default=list(SESSION_TYPES),
        help="Session types: R S Q (default: R S)",
    )
    parser.add_argument(
        "--skip-fetch",
        action="store_true",
        help="Reuse existing JSONL docs under data/docs",
    )
    parser.add_argument(
        "--skip-index",
        action="store_true",
        help="Only generate docs, do not embed/index",
    )
    parser.add_argument(
        "--reset-chroma",
        action="store_true",
        help="Delete existing Chroma directory before indexing",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Reuse existing per-session JSONL files; only fetch missing sessions",
    )
    args = parser.parse_args(argv)

    seasons = tuple(args.seasons)
    session_types = tuple(args.sessions)

    if args.skip_fetch:
        docs = load_docs_from_disk()
        if not docs:
            print("No docs found. Run without --skip-fetch first.", file=sys.stderr)
            return 1
    else:
        docs = generate_all_docs(seasons, session_types, resume=args.resume)

    # Deduplicate by id
    by_id = {d["id"]: d for d in docs}
    docs = list(by_id.values())
    counts = Counter((d.get("metadata") or {}).get("doc_type", "unknown") for d in docs)
    print(f"Total documents: {len(docs)}")
    print("By type:", json.dumps(dict(counts), indent=2))

    if not args.skip_index:
        upsert_chroma(docs, reset=args.reset_chroma)

    size_report()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
