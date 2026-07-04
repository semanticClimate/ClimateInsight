"""
db.py — ChromaDB wrapper
------------------------
Two functions only:
  ingest_chunks(chunks)  — store chunks in ChromaDB
  query_chunks(question) — find the most relevant chunks
"""

import chromadb
from sentence_transformers import SentenceTransformer
from pathlib import Path

# ── Constants ─────────────────────────────────────────────────────────────────

CHROMA_DIR      = str(Path(__file__).parent / "data" / "chroma")
COLLECTION_NAME = "ipcc"
EMBED_MODEL     = "all-MiniLM-L6-v2"

# ── Lazy singletons ───────────────────────────────────────────────────────────

_model      = None
_collection = None


def _get_model():
    global _model
    if _model is None:
        print(f"Loading embedding model ({EMBED_MODEL})...")
        _model = SentenceTransformer(EMBED_MODEL)
        print("Embedding model loaded.")
    return _model


def _get_collection():
    global _collection
    if _collection is None:
        client      = chromadb.PersistentClient(path=CHROMA_DIR)
        _collection = client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
    return _collection


# ── Public functions ──────────────────────────────────────────────────────────

def ingest_chunks(chunks: list[dict], batch_size: int = 64) -> None:
    """
    Store a list of chunk dicts into ChromaDB.
    Each chunk needs: chunk_id, text, section, section_title (optional)

    Safe to re-run — skips chunks that are already stored.
    """
    collection   = _get_collection()
    model        = _get_model()
    existing_ids = set(collection.get(include=[])["ids"]) if collection.count() > 0 else set()
    new_chunks   = [c for c in chunks if c["chunk_id"] not in existing_ids]

    if not new_chunks:
        print(f"All {len(chunks)} chunks already in ChromaDB — nothing to do.")
        return

    print(f"Ingesting {len(new_chunks)} chunks (skipping {len(existing_ids)} already stored)...")

    for i in range(0, len(new_chunks), batch_size):
        batch      = new_chunks[i : i + batch_size]
        texts      = [c["text"] for c in batch]
        ids        = [c["chunk_id"] for c in batch]
        embeddings = model.encode(texts, normalize_embeddings=True).tolist()
        metadatas  = [
            {
                "section":       c.get("section", ""),
                "section_title": c.get("section_title", ""),
            }
            for c in batch
        ]

        collection.add(ids=ids, embeddings=embeddings, documents=texts, metadatas=metadatas)
        print(f"  {min(i + batch_size, len(new_chunks))}/{len(new_chunks)} stored...")

    print(f"Done. ChromaDB now has {collection.count()} chunks.")


def query_chunks(question: str, top_k: int = 5) -> list[dict]:
    """
    Find the most relevant chunks for a question.
    Returns a list of dicts with: text, section, section_title, score
    """
    collection = _get_collection()

    if collection.count() == 0:
        raise RuntimeError("ChromaDB is empty. Run ingest.py first.")

    model        = _get_model()
    query_vector = model.encode([question], normalize_embeddings=True).tolist()[0]

    results = collection.query(
        query_embeddings=[query_vector],
        n_results=min(top_k, collection.count()),
        include=["documents", "metadatas", "distances"],
    )

    output = []
    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        output.append({
            "text":          doc,
            "section":       meta.get("section", ""),
            "section_title": meta.get("section_title", ""),
            "score":         round(1 - dist, 4),
        })

    return output


def collection_size() -> int:
    """Return how many chunks are stored."""
    return _get_collection().count()
