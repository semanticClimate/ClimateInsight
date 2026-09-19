"""Regression tests for citations when papers reuse section names."""

import pytest

from retrieval.citation_parser import extract_citations
from retrieval.context_builder import build_context


def _chunk(chunk_id: str, pmcid: str, text: str) -> dict:
    return {
        "chunk_id": chunk_id,
        "section": "introduction",
        "section_title": "Introduction",
        "text": text,
        "pmcid": pmcid,
        "source_type": "research_article",
        "document_title": f"Paper {pmcid}",
    }


def test_context_uses_unique_chunk_ids_for_same_named_sections():
    chunks = [
        _chunk("PMC111__introduction__chunk_0", "PMC111", "Text from paper one."),
        _chunk("PMC222__introduction__chunk_0", "PMC222", "Text from paper two."),
    ]

    context = build_context(chunks)

    assert "[PMC111__introduction__chunk_0]" in context
    assert "[PMC222__introduction__chunk_0]" in context
    assert "[introduction]" not in context


def test_citation_lookup_selects_the_correct_paper_for_reused_section_name():
    chunks = [
        _chunk("PMC111__introduction__chunk_0", "PMC111", "Text from paper one."),
        _chunk("PMC222__introduction__chunk_0", "PMC222", "Text from paper two."),
    ]
    answer = "The second paper makes this claim [PMC222__introduction__chunk_0]."

    citations = extract_citations(answer, chunks)

    assert citations == [
        {
            "citation_id": "PMC222__introduction__chunk_0",
            "section": "introduction",
            "title": "Introduction",
            "text": "Text from paper two.",
            "pmcid": "PMC222",
            "source_type": "research_article",
            "document_title": "Paper PMC222",
        }
    ]


def test_citation_lookup_selects_the_exact_chunk_within_the_same_section():
    chunks = [
        _chunk("PMC111__results__chunk_0", "PMC111", "First results passage."),
        _chunk("PMC111__results__chunk_1", "PMC111", "Second results passage."),
    ]
    for chunk in chunks:
        chunk["section"] = "results"
        chunk["section_title"] = "Results"

    citations = extract_citations(
        "Claim [PMC111__results__chunk_0].",
        chunks,
    )

    assert len(citations) == 1
    assert citations[0]["text"] == "First results passage."


def test_hallucinated_or_legacy_section_only_citations_are_rejected():
    chunks = [
        _chunk("PMC111__introduction__chunk_0", "PMC111", "Paper text."),
    ]

    assert extract_citations("Unsupported [introduction].", chunks) == []
    assert extract_citations("Unsupported [made-up-id].", chunks) == []


def test_context_rejects_chunks_without_a_unique_id():
    chunk = _chunk("temporary", "PMC111", "Paper text.")
    del chunk["chunk_id"]

    with pytest.raises(ValueError, match="missing chunk_id"):
        build_context([chunk])
