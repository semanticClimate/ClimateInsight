"""
pipeline.py
-----------
Coordinates the ingestion workflow.

Supported modes
---------------
1. Single file  : load one HTML or XML file via the loader registry.
2. Directory    : auto-discover all supported documents under a directory
                  and ingest them all into the shared Chroma collection.
3. Manifest     : load a chatbot_manifest.json (semantic_corpus export).

The chunker is shared across all modes.  The caller in ingest.py selects
the appropriate mode via CLI flags.
"""

from __future__ import annotations

from pathlib import Path
from typing import List

from .chunker import chunk_records
from .loader_registry import SUPPORTED_EXTENSIONS, discover_documents, get_loader
from .models import Chunk, Section


# ─── Mode 1 & 2: file / directory ingestion ───────────────────────────────────


def build_chunks_from_file(
    path: Path,
    chunk_size: int,
    overlap: int,
) -> List[Chunk]:
    """
    Parse a single supported document and return its chunks.

    The correct parser is selected automatically from the loader registry
    based on the file extension — no hardcoding of HTML or XML.
    """
    loader = get_loader(path)
    sections: List[Section] = loader(path)

    if not sections:
        raise RuntimeError(
            f"No sections were extracted from '{path}'. "
            "Check that the file is valid and non-empty."
        )

    return chunk_records(sections, chunk_size, overlap)


def build_chunks_from_directory(
    directory: Path,
    chunk_size: int,
    overlap: int,
) -> List[Chunk]:
    """
    Discover all supported documents under *directory* and return all chunks.

    Newly added files are automatically picked up on the next run without
    any code changes.  The caller (ingest.py) deduplicates against the
    existing Chroma collection via chunk_id.

    Supported extensions: .html, .htm, .xml  (see loader_registry.LOADERS).
    """
    directory = Path(directory)
    files = discover_documents(directory)

    if not files:
        exts = ", ".join(sorted(SUPPORTED_EXTENSIONS))
        raise RuntimeError(
            f"No supported documents found under '{directory}'. "
            f"Supported extensions: {exts}"
        )

    print(f"Discovered {len(files)} document(s) under '{directory}'.")

    all_chunks: List[Chunk] = []
    failed: List[str] = []

    for path in files:
        try:
            chunks = build_chunks_from_file(path, chunk_size, overlap)
            all_chunks.extend(chunks)
        except Exception as exc:  # noqa: BLE001
            print(f"  WARNING: skipping '{path.name}': {exc}")
            failed.append(path.name)

    if failed:
        print(f"\n  Skipped {len(failed)} file(s) due to errors: {failed}")

    return all_chunks


# ─── Mode 1 (legacy alias, used by ingest.py default HTML path) ──────────────


def build_chunks(
    html_path: Path,
    chunk_size: int,
    overlap: int,
) -> List[Chunk]:
    """
    Build chunks from the IPCC HTML reference file.

    Preserved for backwards compatibility: ingest.py calls this when run
    with no flags.  Internally it delegates to build_chunks_from_file so
    the HTML parser benefits from the same loader-registry machinery.
    """
    return build_chunks_from_file(html_path, chunk_size, overlap)


# ─── Mode 3: manifest ─────────────────────────────────────────────────────────


def build_chunks_from_manifest(
    manifest_path: Path,
    chunk_size: int,
    overlap: int,
) -> List[Chunk]:
    """Build chunks from a chatbot_manifest.json (semantic_corpus export)."""
    from .manifest_ingest.build_from_manifest import (
        build_chunks_from_manifest as _build,
    )

    return _build(manifest_path, chunk_size=chunk_size, overlap=overlap)
