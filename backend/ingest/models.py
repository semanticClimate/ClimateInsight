"""
models.py
----------
Dataclasses used throughout the ingestion pipeline.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Section:
    """
    One logical section extracted from the source HTML.
    """

    text: str
    section: str
    section_title: str
    html_id: str = ""


@dataclass(frozen=True)
class Chunk:
    """
    Final chunk stored in ChromaDB.
    """

    chunk_id: str
    text: str
    section: str
    section_title: str
    html_id: str = ""