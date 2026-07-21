"""
Ingestion package.

Public API:
    build_chunks               — ingest a single HTML or XML file.
    build_chunks_from_directory — ingest all supported docs under a directory.
    build_chunks_from_manifest  — ingest from a chatbot_manifest.json.
"""

from .pipeline import build_chunks, build_chunks_from_directory, build_chunks_from_manifest

__all__ = [
    "build_chunks",
    "build_chunks_from_directory",
    "build_chunks_from_manifest",
]