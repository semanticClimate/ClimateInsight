"""
db.py — DEPRECATED
-------------------
ChromaDB logic now lives in vectorstore/.
This file exists only to prevent import errors during the transition.
Delete it once you've confirmed nothing imports from here directly.
"""

import warnings

warnings.warn(
    "db.py is deprecated — import from vectorstore instead: "
    "from vectorstore import query_chunks, ingest_chunks",
    DeprecationWarning,
    stacklevel=2,
)

from vectorstore.indexer import ingest_chunks
from vectorstore.retriever import query_chunks
from vectorstore.chroma_client import get_collection as _get_collection


def collection_size() -> int:
    return _get_collection().count()