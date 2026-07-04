"""
ingest.py
----------
Entry point for building the Chroma database.
"""

import sys
from pathlib import Path

from .pipeline import build_chunks

ROOT = Path(__file__).resolve()

while ROOT.name != "ClimateInsight":
    ROOT = ROOT.parent

HTML_FILE = ROOT / "data" / "raw" / "ipcc_reference.html"

CHUNK_SIZE = 400
OVERLAP = 50


def run():

    if not HTML_FILE.exists():

        print(f"ERROR: {HTML_FILE} not found.")
        sys.exit(1)

    chunks = build_chunks(
        HTML_FILE,
        CHUNK_SIZE,
        OVERLAP,
    )

    from vectorstore import ingest_chunks, collection_size
    
    ingest_chunks(
        [chunk.__dict__ for chunk in chunks]
    )

    print(f"\nDone. ChromaDB now contains {collection_size()} chunks.")


if __name__ == "__main__":
    run()