"""Tests for resolving paper text from xml_path or abstract.

Date: 2026-07-16 (system date of generation)
"""

from pathlib import Path

import pytest

pytest.importorskip(
    "ingest.manifest_ingest.text_loader",
    reason="manifest adapter not implemented yet",
)

from ingest.manifest_ingest.text_loader import (  # noqa: E402
    TextLoadError,
    load_paper_text,
)


def test_text_loader_prefers_xml_over_abstract(sample_xml_path: Path):
    paper = {
        "source_id": "europe_pmc_PMC_FIXTURE_XML",
        "xml_path": str(sample_xml_path),
        "abstract": "Abstract only text should not be used when body XML is present.",
    }
    text, source = load_paper_text(paper)
    assert source == "xml", f"Expected source 'xml', got {source!r}"
    assert "AMOC modulates regional heat" in text, (
        f"Expected body paragraph in XML text, got: {text[:200]!r}"
    )
    assert "Abstract only text should not be used" not in text, (
        "Abstract must not be preferred when XML body exists"
    )


def test_text_loader_falls_back_to_abstract():
    paper = {
        "source_id": "europe_pmc_PMC_FIXTURE_ABS",
        "xml_path": "",
        "abstract": (
            "This paper has no XML full text; the adapter must index "
            "this abstract for RAG."
        ),
    }
    text, source = load_paper_text(paper)
    assert source == "abstract", f"Expected source 'abstract', got {source!r}"
    assert "no XML full text" in text


def test_text_loader_missing_xml_and_abstract_raises():
    paper = {
        "source_id": "europe_pmc_EMPTY",
        "xml_path": "",
        "abstract": "",
    }
    with pytest.raises(TextLoadError):
        load_paper_text(paper)


def test_text_loader_missing_xml_file_falls_back_or_raises(tmp_path: Path):
    """If xml_path is set but file missing, fall back to abstract when present."""
    paper = {
        "source_id": "europe_pmc_MISSING_XML",
        "xml_path": str(Path(tmp_path, "absent.xml")),
        "abstract": "Fallback abstract when XML path is broken.",
    }
    text, source = load_paper_text(paper)
    assert source == "abstract", f"Expected abstract fallback, got {source!r}"
    assert "Fallback abstract" in text
