"""Minimal JATS XML → Section list for RAG chunking.

Date: 2026-07-16 (system date of generation)
"""

import re
from pathlib import Path
from typing import List

from bs4 import BeautifulSoup

from ingest.models import Section


def _slug(text: str, fallback: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text[:60].lower()).strip("-")
    return slug or fallback


def jats_file_to_sections(path: Path) -> List[Section]:
    """Extract body sections (title + paragraphs) from a JATS XML file."""
    path = Path(path)
    soup = BeautifulSoup(path.read_text(encoding="utf-8", errors="ignore"), "xml")
    body = soup.find("body")
    if body is None:
        return []

    sections: List[Section] = []
    top_secs = body.find_all("sec", recursive=False)
    if not top_secs:
        # Flat body: all paragraphs as one section
        paragraphs = [
            p.get_text(" ", strip=True)
            for p in body.find_all("p")
            if p.get_text(" ", strip=True)
        ]
        if paragraphs:
            sections.append(
                Section(
                    text="\n\n".join(paragraphs),
                    section="body",
                    section_title="Body",
                )
            )
        return sections

    for index, sec in enumerate(top_secs):
        title_el = sec.find("title", recursive=False)
        title = (
            title_el.get_text(" ", strip=True)
            if title_el is not None
            else f"Section {index + 1}"
        )
        paragraphs = [
            p.get_text(" ", strip=True)
            for p in sec.find_all("p")
            if p.get_text(" ", strip=True)
        ]
        if not paragraphs:
            continue
        sections.append(
            Section(
                text="\n\n".join(paragraphs),
                section=_slug(title, f"sec-{index + 1}"),
                section_title=title,
            )
        )

    return sections
