"""Build RAG chunks from a semantic_corpus chatbot_manifest.json.

Date: 2026-07-16 (system date of generation)
"""

from pathlib import Path
from typing import List, Union

from ingest.chunker import chunk_records
from ingest.manifest_ingest.jats_to_sections import jats_file_to_sections
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

        sections: List[Section] = []
        if xml_path_raw and Path(xml_path_raw).is_file():
            sections = jats_file_to_sections(Path(xml_path_raw))

        if not sections:
            if not abstract:
                continue
            sections = [
                Section(
                    text=abstract,
                    section="abstract",
                    section_title="Abstract",
                )
            ]

        paper_chunks = chunk_records(sections, chunk_size, overlap)
        citation_label = paper.get("citation_label") or ""
        doi = paper.get("doi") or ""
        pmcid = paper.get("pmcid") or ""

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
                    doi=doi,
                    pmcid=pmcid,
                )
            )

    return all_chunks
