"""
chunker.py
----------
Split Section objects into overlapping Chunk objects.

The chunker is completely agnostic to whether the source was HTML or XML.
It operates on the shared Section interface defined in models.py.

Strategy
--------
- Sections at or below chunk_size words are emitted as a single chunk.
- Longer sections are split with a sliding window and token overlap,
  ensuring no retrieval context is ever more than chunk_size tokens wide.
- All Section metadata (source_path, document_title, source_type, doi,
  pmcid, section_hierarchy) is propagated verbatim to every Chunk.
"""

from __future__ import annotations

import json
from pathlib import Path

from .models import Chunk, Section


def chunk_records(
    records: list[Section],
    chunk_size: int,
    overlap: int,
) -> list[Chunk]:
    """
    Convert a list of Section objects into overlapping Chunk objects.

    Parameters
    ----------
    records    : Sections produced by any registered parser.
    chunk_size : Target chunk length in words (≈ tokens for Latin text).
    overlap    : Number of words shared between consecutive chunks of the
                 same section.

    Returns
    -------
    list[Chunk]
        Chunks ready to be embedded and stored in ChromaDB.
    """
    chunks: list[Chunk] = []
    chunk_index = 0

    for record in records:
        words = record.text.split()

        # Serialise section_hierarchy to a JSON string because ChromaDB
        # metadata values must be scalar types (str / int / float / bool).
        hierarchy_json = json.dumps(list(record.section_hierarchy)) if record.section_hierarchy else "[]"

        # ── Stable per-document prefix so chunk_ids never collide across files ──
        # Use pmcid when available (XML), else the filename stem (HTML).
        # Without this, every XML article would emit "introduction__chunk_0",
        # "results__chunk_0", etc., and the indexer's dedup logic would silently
        # drop every document after the first one with that section name.
        doc_prefix = (
            record.pmcid.strip()
            or Path(record.source_path).stem
            or "doc"
        )

        # ── Common keyword args shared by every Chunk from this Section ──────
        common = dict(
            section=record.section,
            section_title=record.section_title,
            html_id=record.html_id,
            source_path=record.source_path,
            document_title=record.document_title,
            source_type=record.source_type,
            doi=record.doi,
            pmcid=record.pmcid,
            section_hierarchy=hierarchy_json,
        )

        if len(words) <= chunk_size:
            # Section fits in a single chunk — no splitting needed.
            chunks.append(
                Chunk(
                    chunk_id=f"{doc_prefix}__{record.section or 'nosec'}__chunk_{chunk_index}",
                    text=record.text,
                    **common,
                )
            )
            chunk_index += 1
            continue

        # ── Sliding-window split for long sections ───────────────────────────
        start = 0
        while start < len(words):
            end = min(start + chunk_size, len(words))
            chunk_text = " ".join(words[start:end])
            chunks.append(
                Chunk(
                    chunk_id=f"{doc_prefix}__{record.section or 'nosec'}__chunk_{chunk_index}",
                    text=chunk_text,
                    **common,
                )
            )
            chunk_index += 1
            start += chunk_size - overlap

    print(f"Created {len(chunks)} chunks from {len(records)} sections.")
    return chunks