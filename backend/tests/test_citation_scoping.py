"""Regression tests for citations when papers reuse section names.

Every retrieved chunk gets a per-answer citation key from
assign_citation_keys(): IPCC chunks keep their section ID ("2.1"), paper
chunks get P1, P2, ... in retrieval order. These tests check that a
citation always resolves to exactly one retrieved chunk, even when several
papers share a section name such as "introduction".
"""

import pytest

from retrieval.citation_parser import extract_citations
from retrieval.context_builder import assign_citation_keys, build_context


def _chunk(chunk_id: str, pmcid: str, text: str, section: str = "introduction") -> dict:
    return {
        "chunk_id": chunk_id,
        "section": section,
        "section_title": section.title(),
        "text": text,
        "pmcid": pmcid,
        "source_type": "research_article",
        "document_title": f"Paper {pmcid}",
    }


def test_context_gives_same_named_sections_distinct_refs():
    chunks = assign_citation_keys([
        _chunk("PMC111__introduction__chunk_0", "PMC111", "Text from paper one."),
        _chunk("PMC222__introduction__chunk_0", "PMC222", "Text from paper two."),
    ])

    context = build_context(chunks)

    assert "[P1] (Paper PMC111) Text from paper one." in context
    assert "[P2] (Paper PMC222) Text from paper two." in context
    assert "[introduction]" not in context


def test_ipcc_chunks_keep_their_section_id():
    chunks = assign_citation_keys([
        {"chunk_id": "ipcc__2.1__chunk_0", "section": "2.1", "text": "Warming is 1.1 C."},
    ])

    assert build_context(chunks) == "[2.1] Warming is 1.1 C."


def test_citation_lookup_selects_the_correct_paper_for_reused_section_name():
    chunks = assign_citation_keys([
        _chunk("PMC111__introduction__chunk_0", "PMC111", "Text from paper one."),
        _chunk("PMC222__introduction__chunk_0", "PMC222", "Text from paper two."),
    ])
    answer = "The second paper makes this claim [P2]."

    citations = extract_citations(answer, chunks)

    assert citations == [
        {
            "ref": "P2",
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
    chunks = assign_citation_keys([
        _chunk("PMC111__results__chunk_0", "PMC111", "First results passage.", "results"),
        _chunk("PMC111__results__chunk_1", "PMC111", "Second results passage.", "results"),
    ])

    citations = extract_citations("Claim [P2].", chunks)

    assert len(citations) == 1
    assert citations[0]["text"] == "Second results passage."
    assert citations[0]["citation_id"] == "PMC111__results__chunk_1"


def test_hallucinated_or_legacy_section_only_citations_are_rejected():
    chunks = assign_citation_keys([
        _chunk("PMC111__introduction__chunk_0", "PMC111", "Paper text."),
    ])

    assert extract_citations("Unsupported [introduction].", chunks) == []
    assert extract_citations("Unsupported [made-up-id].", chunks) == []
    assert extract_citations("Unsupported [P7].", chunks) == []


def test_context_rejects_chunks_without_a_ref():
    chunk = _chunk("PMC111__introduction__chunk_0", "PMC111", "Paper text.")

    with pytest.raises(ValueError, match="assign_citation_keys"):
        build_context([chunk])
