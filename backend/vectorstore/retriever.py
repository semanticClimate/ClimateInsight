"""
retriever.py
------------
Queries ChromaDB for the most relevant chunks.
"""

from .chroma_client import get_collection
from .embedder import embed


def query_chunks(question: str, top_k: int = 5) -> list[dict]:
    """
    Retrieve the most relevant chunks for a question.
    """

    collection = get_collection()

    if collection.count() == 0:
        raise RuntimeError(
            "ChromaDB is empty. Run ingest.py first."
        )

    query_vector = embed([question])[0]

    results = collection.query(
        query_embeddings=[query_vector],
        n_results=min(top_k, collection.count()),
        include=[
            "documents",
            "metadatas",
            "distances",
        ],
    )

    output = []

    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        output.append(
            {
                "text": doc,
                "section": meta.get("section", ""),
                "section_title": meta.get("section_title", ""),
                "source_id": meta.get("source_id", ""),
                "citation_label": meta.get("citation_label", ""),
                "doi": meta.get("doi", ""),
                "pmcid": meta.get("pmcid", ""),
                "score": round(1 - dist, 4),
            }
        )

    return output


def collection_size():
    """
    Return the number of stored chunks.
    """

    return get_collection().count()