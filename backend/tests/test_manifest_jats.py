"""Tests for minimal JATS XML → Section conversion.

Date: 2026-07-16 (system date of generation)
"""

from pathlib import Path

import pytest

pytest.importorskip(
    "ingest.manifest_ingest.jats_to_sections",
    reason="manifest adapter not implemented yet",
)

from ingest.manifest_ingest.jats_to_sections import jats_file_to_sections  # noqa: E402
from ingest.models import Section  # noqa: E402


def test_jats_to_sections_extracts_body_paragraphs(sample_xml_path: Path):
    sections = jats_file_to_sections(sample_xml_path)
    assert len(sections) >= 1, (
        f"Expected at least one Section from fixture XML, got {len(sections)}"
    )
    assert all(isinstance(s, Section) for s in sections), (
        "jats_file_to_sections must return ingest.models.Section instances"
    )
    combined = "\n".join(s.text for s in sections)
    assert "Marine heatwaves disrupt ocean circulation" in combined
    assert "Observed warming exceeded historical baselines" in combined


def test_jats_to_sections_preserves_section_titles(sample_xml_path: Path):
    sections = jats_file_to_sections(sample_xml_path)
    titles = {s.section_title for s in sections}
    assert "Introduction" in titles or any("Introduction" in t for t in titles), (
        f"Expected Introduction among section titles, got {titles}"
    )
