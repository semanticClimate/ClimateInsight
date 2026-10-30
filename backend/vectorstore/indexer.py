"""
indexer.py
----------
Stores chunks inside ChromaDB.
"""

from .chroma_client import get_collection
from .embedder import embed


def ingest_chunks(chunks: list[dict], batch_size: int = 64):
    """
    Store chunks inside ChromaDB.

    Safe to run multiple times.
    Existing chunks are skipped, and chunks previously stored for a
    re-ingested file that are no longer produced by it are deleted.
    """

    collection = get_collection()

    # Identical text in the same section yields the same ID; keep one copy
    # (Chroma rejects duplicate IDs within a single add call).
    chunks = list({c["chunk_id"]: c for c in chunks}.values())
    incoming_ids = {c["chunk_id"] for c in chunks}

    existing = (
        collection.get(include=["metadatas"])
        if collection.count() > 0
        else {"ids": [], "metadatas": []}
    )

    # ── Prune stale chunks from files being re-ingested ──────────────────────
    reingested_paths = {c.get("source_path") for c in chunks} - {"", None}
    stale_ids = [
        cid
        for cid, meta in zip(existing["ids"], existing["metadatas"])
        if (meta or {}).get("source_path") in reingested_paths
        and cid not in incoming_ids
    ]
    if stale_ids:
        print(f"Removing {len(stale_ids)} stale chunk(s) from re-ingested files...")
        for i in range(0, len(stale_ids), 5000):
            collection.delete(ids=stale_ids[i:i + 5000])

    existing_ids = set(existing["ids"]) - set(stale_ids)

    new_chunks = [
        c for c in chunks
        if c["chunk_id"] not in existing_ids
    ]

    if not new_chunks:
        print(f"All {len(chunks)} chunks already in ChromaDB — nothing to do.")
        return

    print(
        f"Ingesting {len(new_chunks)} chunks "
        f"(skipping {len(existing_ids)} already stored)..."
    )

    for i in range(0, len(new_chunks), batch_size):

        batch = new_chunks[i:i + batch_size]

        ids = [c["chunk_id"] for c in batch]
        texts = [c["text"] for c in batch]

        embeddings = embed(texts)

        metadatas = [
            {
                "section": c.get("section", ""),
                "section_title": c.get("section_title", ""),
                "source_id": c.get("source_id", ""),
                "citation_label": c.get("citation_label", ""),
                "source_path": c.get("source_path", ""),
                "document_title": c.get("document_title", ""),
                "source_type": c.get("source_type", ""),
                "doi": c.get("doi", ""),
                "pmcid": c.get("pmcid", ""),
                "section_hierarchy": c.get("section_hierarchy", "[]"),
            }
            for c in batch
        ]

        collection.add(
            ids=ids,
            documents=texts,
            embeddings=embeddings,
            metadatas=metadatas,
        )

        print(
            f"  {min(i + batch_size, len(new_chunks))}/{len(new_chunks)} stored..."
        )

    print(f"Done. ChromaDB now has {collection.count()} chunks.")