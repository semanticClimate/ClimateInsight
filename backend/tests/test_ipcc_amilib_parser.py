"""Tests for the reader of semanticClimate amilib IPCC HTML (html_with_ids).

The synthetic fixture pins the amilib format this reader depends on. The
later groups check that data/raw/ipcc_reference.html is still read by
the previous reader, and run the real SYR (amilib's cleaned output)
through the amilib reader as a fetched chapter would be.
"""

import shutil
from pathlib import Path

import pytest
from lxml import html

from ingest.ipcc_amilib_parser import _element_text, is_amilib_ipcc_html, parse_ipcc_amilib
from ingest.loader_registry import get_loader
from ingest.parser import parse_html

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "ipcc_amilib" / "html_with_ids.html"
SYR = Path(__file__).resolve().parents[2] / "data" / "raw" / "ipcc_reference.html"
RESEARCH_HTML = Path(__file__).resolve().parents[2] / "data" / "raw" / "ocean_heatwaves_2026" / "10011364.html"


@pytest.fixture(scope="module")
def sections():
    return parse_ipcc_amilib(FIXTURE)


def _by_section(sections):
    return {s.section: s for s in sections}


# ─── Format contract (synthetic fixture) ──────────────────────────────────────


def test_detects_amilib_format():
    assert is_amilib_ipcc_html(html.parse(str(FIXTURE)).getroot())


def test_one_section_per_container_in_document_order(sections):
    assert [s.section for s in sections] == ["1", "1.1", "1.1.1", "1.1.2", "box-1-1-key-terms", "1.2.3"]


def test_section_number_comes_from_heading_not_repeated_container_id(sections):
    by = _by_section(sections)
    assert by["1.1.2"].section_title == "Observed Impacts"
    assert by["1.1.2"].html_id == "1.2.3_p1"  # amilib's anchor is kept for linking
    assert by["1.2.3"].section_title == "Adaptation Actions"


def test_paragraphs_grouped_under_nearest_container(sections):
    by = _by_section(sections)
    assert by["1"].text.startswith("The first introductory paragraph")
    assert "second introductory paragraph" in by["1"].text
    assert "Observed warming" in by["1.1"].text
    assert "Global surface temperature" not in by["1.1"].text  # belongs to 1.1.1


def test_html_id_is_first_amilib_paragraph_id(sections):
    assert _by_section(sections)["1.1.1"].html_id == "1.1.1_p1"


def test_hierarchy_lists_enclosing_headings(sections):
    assert _by_section(sections)["1.1.1"].section_hierarchy == ("1 Introduction", "1.1 Observed Changes")
    assert _by_section(sections)["1"].section_hierarchy == ()


def test_excludes_non_prose(sections):
    text = " ".join(s.text for s in sections)
    for unwanted in ("Author One", "Figure 1.1", "footnote with no", "A cited paper", "Introduction to the Test Report"):
        assert unwanted not in text


def test_document_metadata(sections):
    assert {s.document_title for s in sections} == {"Test Longer Report"}
    assert {s.source_type for s in sections} == {"ipcc_report"}


def test_registry_routes_amilib_html_to_this_reader():
    assert [s.section for s in get_loader(FIXTURE)(FIXTURE)][:2] == ["1", "1.1"]


def test_registry_falls_back_for_other_html():
    if not RESEARCH_HTML.exists():
        pytest.skip("research HTML sample not present")
    root = html.parse(str(RESEARCH_HTML)).getroot()
    assert not is_amilib_ipcc_html(root)
    assert get_loader(RESEARCH_HTML)(RESEARCH_HTML)


# ─── Existing data must read exactly as before ───────────────────────────────


@pytest.mark.skipif(not SYR.exists(), reason="data/raw/ipcc_reference.html not present")
def test_existing_ipcc_reference_still_uses_previous_reader():
    """No SOURCES.json beside it, so the chatbot's index is unchanged."""
    assert get_loader(SYR)(SYR) == parse_html(SYR)


# ─── Real AR6 data through the amilib reader ──────────────────────────────────


@pytest.fixture(scope="module")
def fetched_syr(tmp_path_factory):
    """The SYR Longer Report laid out as fetch_ipcc_from_amilib.py saves it."""
    if not SYR.exists():
        pytest.skip("data/raw/ipcc_reference.html not present")
    d = tmp_path_factory.mktemp("ipcc")
    target = d / "syr_longer-report.html"
    shutil.copy(SYR, target)
    (d / "SOURCES.json").write_text("{}")
    return target


def test_fetched_syr_routes_to_amilib_reader(fetched_syr):
    assert get_loader(fetched_syr)(fetched_syr) == parse_ipcc_amilib(fetched_syr)


def test_fetched_syr_keeps_every_amilib_paragraph(fetched_syr):
    root = html.parse(str(fetched_syr)).getroot()
    paragraphs = {p for s in parse_ipcc_amilib(fetched_syr) for p in s.text.split("\n\n")}
    missing = [
        p.get("id") for p in root.xpath("//p[@id]")
        if (t := _element_text(p)) and t not in paragraphs
    ]
    assert missing == []


def test_fetched_syr_text_matches_previous_reader_format(fetched_syr):
    """Same text form as parser.py (e.g. "CO 2"), so concept matching is unchanged."""
    old = {p for s in parse_html(SYR) for p in s.text.split("\n\n")}
    new = [p for s in parse_ipcc_amilib(fetched_syr) for p in s.text.split("\n\n")]
    assert sum(p in old for p in new) >= len(new) - 2


def test_fetched_syr_sections_are_unique_and_titled(fetched_syr):
    secs = parse_ipcc_amilib(fetched_syr)
    labels = [s.section for s in secs]
    assert len(labels) == len(set(labels))
    assert {"1", "2.1", "2.1.2", "2.2.3", "4.9"} <= set(labels)
    assert {s.document_title for s in secs} == {"SYR Longer Report"}
