"""
Public API for the vector store package.
"""

from .indexer import ingest_chunks
from .retriever import query_chunks, collection_size

__all__ = [
    "ingest_chunks",
    "query_chunks",
    "collection_size",
]