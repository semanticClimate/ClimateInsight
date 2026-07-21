"""
parser.py
----------
Extract logical sections from the IPCC HTML document.

Groups all paragraphs under a heading into one Section,
then lets the chunker split if needed.
Preserves paragraph-level html_id for citation linking.

This parser is registered in the LOADER_REGISTRY as the handler for
.html / .htm files. It returns Section objects that share the same
interface as the XML parser so the chunker is format-agnostic.
"""

import re
from pathlib import Path

from bs4 import BeautifulSoup

from .models import Section

SKIP_CLASSES = {"footnote", "Footnote", "foot-note", "reference", "caption", "CharOverride"}
MIN_PARAGRAPH_LENGTH = 40


def _is_noise(tag) -> bool:
    """Return True for footnotes, figure captions, and HTML artefacts we don't want indexed."""
    tag_classes = set(tag.get("class") or [])
    if tag_classes & SKIP_CLASSES:
        return True
    text = tag.get_text(separator=" ", strip=True)
    # Footnote-style: starts with a number followed by "See" or short reference
    if re.match(r"^\d{1,3}\s+(See|Based on|Ibid)", text):
        return True
    return False


def _section_id_from_heading(text: str) -> tuple[str, str]:
    """Parse a heading into (section_id, title). Works for numeric and non-numeric headings."""
    match = re.match(r"^(\d[\d\.]*)\s*[\.\:]?\s*(.*)", text)
    if match:
        return match.group(1).rstrip("."), match.group(2).strip()
    slug = re.sub(r"[^a-z0-9]+", "-", text[:60].lower()).strip("-")
    return slug or "intro", text[:80]


def parse_html(path: Path) -> list[Section]:
    """
    Parse an IPCC-style HTML file and return a list of Section objects.

    Each Section covers all paragraphs beneath one heading.  The caller
    (chunker) is responsible for splitting long sections.

    Registered in LOADER_REGISTRY for .html / .htm extensions.
    """
    print(f"Parsing HTML: {path}...")
    source_path = str(path.resolve())

    soup = BeautifulSoup(
        path.read_text(encoding="utf-8", errors="ignore"),
        "html.parser",
    )

    # Extract a document-level title from <title> or first <h1> as fallback.
    doc_title_tag = soup.find("title")
    if doc_title_tag and doc_title_tag.get_text(strip=True):
        document_title = doc_title_tag.get_text(strip=True)
    else:
        first_h1 = soup.find("h1")
        document_title = first_h1.get_text(strip=True) if first_h1 else path.stem

    # ── KEY FIX: remove the entire footnotes block before walking the tree ──
    # The HTML wraps all footnotes in <div class="_idFootnotes">.
    # Without this, every footnote <p> inherits the last real section heading
    # (4.9), causing the "[4.9] flooding" bug.
    for footnotes_div in soup.find_all("div", class_="_idFootnotes"):
        footnotes_div.decompose()

    # Also strip figure captions — they pollute retrieval without adding meaning
    for caption in soup.find_all(class_="Caption"):
        caption.decompose()

    records: list[Section] = []

    current_section = "intro"
    current_title = ""
    # Accumulate (text, html_id) pairs for the current heading
    current_paragraphs: list[tuple[str, str]] = []

    def flush():
        """Bundle accumulated paragraphs into one Section and append to records."""
        if not current_paragraphs:
            return
        combined_text = "\n\n".join(t for t, _ in current_paragraphs)
        # Use the id of the first paragraph as the anchor for citations
        first_html_id = current_paragraphs[0][1]
        records.append(
            Section(
                text=combined_text,
                section=current_section,
                section_title=current_title,
                html_id=first_html_id,
                source_path=source_path,
                document_title=document_title,
                source_type="ipcc_report",
            )
        )

    for tag in soup.find_all(["h1", "h2", "h3", "h4", "p", "li"]):

        if tag.name in ("h1", "h2", "h3", "h4"):
            # New heading → flush whatever was accumulating
            flush()
            current_paragraphs = []

            heading_text = tag.get_text(separator=" ", strip=True)
            if not heading_text:
                continue
            current_section, current_title = _section_id_from_heading(heading_text)
            continue

        # --- paragraph / list item ---

        if _is_noise(tag):
            continue

        text = tag.get_text(separator=" ", strip=True)

        # Strip residual HTML tags that crept into the text
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s{2,}", " ", text).strip()

        if len(text) < MIN_PARAGRAPH_LENGTH:
            continue

        html_id = tag.get("id", "")
        current_paragraphs.append((text, html_id))

    # Don't forget the last section
    flush()

    print(f"Extracted {len(records)} sections from HTML.")
    return records