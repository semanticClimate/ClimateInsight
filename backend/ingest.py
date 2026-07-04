"""
ingest.py — Load IPCC HTML into ChromaDB
------------------------------------------
Run once (or whenever you want to re-index):
    python ingest.py

What it does:
  1. Parses the IPCC HTML file
  2. Splits it into chunks
  3. Stores chunks in ChromaDB with embeddings

After this runs successfully, start the server: python app.py
"""

import sys
import re
from pathlib import Path
from bs4 import BeautifulSoup

# ── Settings ──────────────────────────────────────────────────────────────────

HTML_FILE  = Path(__file__).parent.parent / "data" / "raw" / "ipcc_reference.html"
CHUNK_SIZE = 400   # target words per chunk
OVERLAP    = 50    # words of overlap between chunks


# ── Step 1: Parse HTML ────────────────────────────────────────────────────────

def parse_html(path: Path) -> list[dict]:
    """
    Extract paragraphs from the IPCC HTML file.
    Returns a list of dicts: {text, section, section_title}
    """
    print(f"Parsing {path}...")
    soup = BeautifulSoup(path.read_text(encoding="utf-8", errors="ignore"), "html.parser")

    records = []
    current_section       = ""
    current_section_title = ""

    for tag in soup.find_all(["h1", "h2", "h3", "h4", "p", "li"]):
        text = tag.get_text(separator=" ", strip=True)
        if not text or len(text) < 20:
            continue

        # Update current section when we hit a heading
        if tag.name in ("h1", "h2", "h3", "h4"):
            # Try to extract a section number like "2.1.1" from the heading
            match = re.match(r"^(\d[\d\.]*)\s*(.*)", text)
            if match:
                current_section       = match.group(1).rstrip(".")
                current_section_title = match.group(2).strip()
            else:
                current_section_title = text[:80]
            continue

        records.append({
            "text":          text,
            "section":       current_section,
            "section_title": current_section_title,
        })

    print(f"  Extracted {len(records)} paragraphs.")
    return records


# ── Step 2: Chunk ─────────────────────────────────────────────────────────────

def chunk_records(records: list[dict]) -> list[dict]:
    """
    Split paragraphs into fixed-size word chunks with overlap.
    """
    chunks = []
    chunk_index = 0

    for rec in records:
        words = rec["text"].split()

        # If the paragraph is short enough, keep it as one chunk
        if len(words) <= CHUNK_SIZE:
            chunks.append({
                "chunk_id":      f"{rec['section'] or 'nosec'}__chunk_{chunk_index}",
                "text":          rec["text"],
                "section":       rec["section"],
                "section_title": rec["section_title"],
            })
            chunk_index += 1
            continue

        # Otherwise split into overlapping windows
        start = 0
        while start < len(words):
            end        = min(start + CHUNK_SIZE, len(words))
            chunk_text = " ".join(words[start:end])
            chunks.append({
                "chunk_id":      f"{rec['section'] or 'nosec'}__chunk_{chunk_index}",
                "text":          chunk_text,
                "section":       rec["section"],
                "section_title": rec["section_title"],
            })
            chunk_index += 1
            start += CHUNK_SIZE - OVERLAP

    print(f"  Created {len(chunks)} chunks.")
    return chunks


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if not HTML_FILE.exists():
        print(f"ERROR: HTML file not found at {HTML_FILE}")
        print("Make sure ipcc_reference.html is in the data/raw/ folder.")
        sys.exit(1)

    # Parse
    records = parse_html(HTML_FILE)
    if not records:
        print("ERROR: No paragraphs extracted. Check the HTML file.")
        sys.exit(1)

    # Chunk
    chunks = chunk_records(records)

    # Ingest into ChromaDB
    from db import ingest_chunks, collection_size
    ingest_chunks(chunks)

    print(f"\nAll done! ChromaDB has {collection_size()} chunks ready.")
    print("Now run: python app.py")
