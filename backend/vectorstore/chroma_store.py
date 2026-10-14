from __future__ import annotations

import chromadb

from ..config import CHROMA_DIR, COLLECTION_NAME

_client = None
_collection = None


def get_client():
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    return _client


def build_collection(name: str = COLLECTION_NAME):
    global _collection
    _collection = get_client().get_or_create_collection(name=name, metadata={"hnsw:space": "cosine"})
    return _collection


def get_collection():
    global _collection
    if _collection is None:
        _collection = build_collection(COLLECTION_NAME)
    return _collection


def reset_collection():
    global _collection
    client = get_client()
    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass
    _collection = None
