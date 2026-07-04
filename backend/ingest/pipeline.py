"""
pipeline.py
-----------
Coordinates the ingestion workflow.
"""

from pathlib import Path

from .parser import parse_html
from .chunker import chunk_records


def build_chunks(
    html_path: Path,
    chunk_size: int,
    overlap: int,
):

    records = parse_html(html_path)

    if not records:
        raise RuntimeError("No records were extracted from the HTML document.")

    return chunk_records(
        records,
        chunk_size,
        overlap,
    )