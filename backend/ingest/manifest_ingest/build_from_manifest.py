"""Build RAG chunks from a semantic_corpus chatbot_manifest.json.

This module is kept for backwards compatibility with the --manifest flag.
It uses the shared xml_parser and chunker so the output chunks have the
same metadata shape as directly-ingested XML files.

Date: 2026-07-20 (refactored)
"""

from pathlib import Path
from typing import List, Union

from ingest.chunker import chunk_records
from ingest.xml_parser import parse_xml
from ingest.manifest_ingest.load_manifest import load_manifest
from ingest.models import Chunk, Section


def build_chunks_from_manifest(
    manifest_path: Path,
    *,
    chunk_size: int = 400,
    overlap: int = 50,
) -> List[Union[Chunk, dict]]:
    """Load manifest, extract sections per paper, chunk, attach citation metadata."""
    data = load_manifest(Path(manifest_path))
    all_chunks: List[Chunk] = []

    for paper in data.get("papers") or []:
        source_id = str(paper.get("source_id") or "unknown")
        xml_path_raw = (paper.get("xml_path") or "").strip()
        abstract = (paper.get("abstract") or "").strip()
        citation_label = paper.get("citation_label") or ""
        doi = paper.get("doi") or ""
        pmcid = paper.get("pmcid") or ""

        sections: List[Section] = []

        # ── Prefer full XML body via the shared xml_parser ──────────────────
        if xml_path_raw and Path(xml_path_raw).is_file():
            try:
                sections = parse_xml(Path(xml_path_raw))
            except Exception as exc:  # noqa: BLE001
                print(f"  WARNING: failed to parse XML for {source_id!r}: {exc}")

        # ── Fall back to abstract text ─────────────────────────────────────
        if not sections:
            if not abstract:
                print(f"  SKIP: no XML body or abstract for {source_id!r}")
                continue
            sections = [
                Section(
                    text=abstract,
                    section="abstract",
                    section_title="Abstract",
                    source_type="research_article",
                    doi=doi,
                    pmcid=pmcid,
                )
            ]

        paper_chunks = chunk_records(sections, chunk_size, overlap)

        for chunk in paper_chunks:
            all_chunks.append(
                Chunk(
                    chunk_id=f"{source_id}__{chunk.chunk_id}",
                    text=chunk.text,
                    section=chunk.section,
                    section_title=chunk.section_title,
                    html_id=chunk.html_id,
                    source_id=source_id,
                    citation_label=citation_label,
                    source_path=chunk.source_path,
                    document_title=chunk.document_title,
                    source_type=chunk.source_type or "research_article",
                    doi=doi or chunk.doi,
                    pmcid=pmcid or chunk.pmcid,
                    section_hierarchy=chunk.section_hierarchy,
                )
            )

    return all_chunks
