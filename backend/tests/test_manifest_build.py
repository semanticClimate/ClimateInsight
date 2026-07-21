"""End-to-end (no Chroma) tests: manifest → chunks with paper metadata.

Date: 2026-07-16 (system date of generation)
"""

from pathlib import Path

import pytest

pytest.importorskip(
    "ingest.manifest_ingest.build_from_manifest",
    reason="manifest adapter not implemented yet",
)

from ingest.manifest_ingest.build_from_manifest import (  # noqa: E402
    build_chunks_from_manifest,
)


def test_build_from_manifest_creates_chunks(chatbot_manifest_path: Path):
    chunks = build_chunks_from_manifest(
        chatbot_manifest_path,
        chunk_size=400,
        overlap=50,
    )
    assert len(chunks) >= 2, (
        f"Expected chunks from XML + abstract papers, got {len(chunks)}"
    )


def test_build_from_manifest_chunk_ids_prefixed_by_source_id(
    chatbot_manifest_path: Path,
):
    chunks = build_chunks_from_manifest(
        chatbot_manifest_path,
        chunk_size=400,
        overlap=50,
    )
    # Chunk may be dataclass or dict — normalize
    def chunk_id(c):
        return c["chunk_id"] if isinstance(c, dict) else c.chunk_id

    ids = [chunk_id(c) for c in chunks]
    assert any(i.startswith("europe_pmc_PMC_FIXTURE_XML") for i in ids), (
        f"Expected chunk_id prefixed with XML source_id, got {ids[:5]}"
    )
    assert any(i.startswith("europe_pmc_PMC_FIXTURE_ABS") for i in ids), (
        f"Expected chunk_id prefixed with abstract source_id, got {ids[:5]}"
    )


def test_build_from_manifest_attaches_citation_metadata(
    chatbot_manifest_path: Path,
):
    chunks = build_chunks_from_manifest(
        chatbot_manifest_path,
        chunk_size=400,
        overlap=50,
    )

    def as_dict(c):
        return c if isinstance(c, dict) else c.__dict__

    dicts = [as_dict(c) for c in chunks]
    xml_chunks = [
        d for d in dicts if d.get("source_id") == "europe_pmc_PMC_FIXTURE_XML"
    ]
    abs_chunks = [
        d for d in dicts if d.get("source_id") == "europe_pmc_PMC_FIXTURE_ABS"
    ]
    assert xml_chunks, "Expected at least one chunk from XML paper"
    assert abs_chunks, "Expected at least one chunk from abstract-only paper"

    sample = xml_chunks[0]
    assert sample.get("citation_label"), (
        f"citation_label missing on chunk: {sample.keys()}"
    )
    assert "Fixture" in sample["citation_label"]
    assert sample.get("doi") == "10.example/fixture-xml"
    assert sample.get("pmcid") == "PMC_FIXTURE_XML"


def test_build_from_manifest_reuses_section_fields(chatbot_manifest_path: Path):
    """Chunks must still expose section / section_title for existing citation UI."""
    chunks = build_chunks_from_manifest(
        chatbot_manifest_path,
        chunk_size=400,
        overlap=50,
    )

    def as_dict(c):
        return c if isinstance(c, dict) else c.__dict__

    for c in chunks:
        d = as_dict(c)
        assert "section" in d, f"Missing section on chunk {d.get('chunk_id')}"
        assert "section_title" in d, (
            f"Missing section_title on chunk {d.get('chunk_id')}"
        )
        assert d.get("text"), f"Empty text on chunk {d.get('chunk_id')}"
