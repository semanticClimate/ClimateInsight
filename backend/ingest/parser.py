"""
parser.py
----------
Extract logical sections from the IPCC HTML document.
"""

import re
from pathlib import Path

from bs4 import BeautifulSoup

from .models import Section


def parse_html(path: Path) -> list[Section]:

    print(f"Parsing {path}...")

    soup = BeautifulSoup(
        path.read_text(encoding="utf-8", errors="ignore"),
        "html.parser",
    )

    records = []

    current_section = ""
    current_title = ""
    heading_paragraph_index = 0   # counts paragraphs under the current heading

    for tag in soup.find_all(["h1", "h2", "h3", "h4", "p", "li"]):

        text = tag.get_text(separator=" ", strip=True)

        if not text or len(text) < 20:
            continue

        if tag.name in ("h1", "h2", "h3", "h4"):

            match = re.match(r"^(\d[\d\.]*)[\s\.\:]*(.*)", text)

            if match:
                current_section = match.group(1).rstrip(".")
                current_title = match.group(2).strip()
            else:
                # Non-numeric heading — derive a slug from the title text
                # so every heading gets its own namespace.
                slug = re.sub(r"[^a-z0-9]+", "-", text[:60].lower()).strip("-")
                current_section = slug if slug else "intro"
                current_title = text[:80]

            heading_paragraph_index = 0   # reset counter for new section
            continue

        # Give each paragraph a unique section ID:
        # "<section>.<paragraph_index>" so chunks under the same heading
        # are distinguishable and the LLM can cite them individually.
        paragraph_section = (
            f"{current_section}.{heading_paragraph_index}"
            if current_section
            else f"p{heading_paragraph_index}"
        )

        records.append(
            Section(
                text=text,
                section=paragraph_section,
                section_title=current_title,
            )
        )

        heading_paragraph_index += 1

    print(f"Extracted {len(records)} sections.")

    return records