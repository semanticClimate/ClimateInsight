"""
models.py
----------
Dataclasses used throughout the ingestion pipeline.

Both HTML and XML parsers return Section objects with the same fields so
the chunker is agnostic to the original document format.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Section:
    """
    One logical section extracted from any supported document format.

    Fields
    ------
    text            : Paragraph text for this section.
    section         : Machine-readable section identifier / slug.
    section_title   : Human-readable heading.
    html_id         : DOM anchor (IPCC HTML only; empty for XML).
    source_path     : Absolute path of the originating file.
    document_title  : Title of the parent document (article or report).
    source_type     : 'ipcc_report' | 'research_article' | ''.
    doi             : DOI extracted from document metadata (XML only).
    pmcid           : PubMed Central ID (XML only).
    section_hierarchy: List of ancestor section titles (for nested <sec>).
    """

    text: str
    section: str
    section_title: str
    html_id: str = ""
    source_path: str = ""
    document_title: str = ""
    source_type: str = ""          # 'ipcc_report' or 'research_article'
    doi: str = ""
    pmcid: str = ""
    section_hierarchy: tuple = field(default_factory=tuple)  # frozen-friendly


@dataclass(frozen=True)
class Chunk:
    """
    Final chunk stored in ChromaDB.

    Carries all metadata required for retrieval and citation rendering.
    """

    chunk_id: str
    text: str
    section: str
    section_title: str
    html_id: str = ""
    # Provenance
    source_id: str = ""
    citation_label: str = ""
    source_path: str = ""
    document_title: str = ""
    source_type: str = ""          # 'ipcc_report' or 'research_article'
    doi: str = ""
    pmcid: str = ""
    section_hierarchy: str = ""    # JSON-serialised list (Chroma requires str)
