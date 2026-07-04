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

    for tag in soup.find_all(["h1", "h2", "h3", "h4", "p", "li"]):

        text = tag.get_text(separator=" ", strip=True)

        if not text or len(text) < 20:
            continue

        if tag.name in ("h1", "h2", "h3", "h4"):

            match = re.match(r"^(\d[\d\.]*)\s*(.*)", text)

            if match:
                current_section = match.group(1).rstrip(".")
                current_title = match.group(2).strip()
            else:
                current_title = text[:80]

            continue

        records.append(
            Section(
                text=text,
                section=current_section,
                section_title=current_title,
            )
        )

    print(f"Extracted {len(records)} sections.")

    return records