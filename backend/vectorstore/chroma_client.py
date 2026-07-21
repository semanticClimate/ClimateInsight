"""
chroma_client.py
----------------
Creates and manages the ChromaDB client and collection.
"""

from pathlib import Path

import chromadb

CHROMA_DIR = str(Path(__file__).parent.parent / "chroma_db")
COLLECTION_NAME = "ipcc"

_collection = None


def get_collection():
    """
    Return the Chroma collection.
    Creates it if it doesn't already exist.
    """

    global _collection

    if _collection is None:
        client = chromadb.PersistentClient(path=CHROMA_DIR)

        _collection = client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

    return _collection