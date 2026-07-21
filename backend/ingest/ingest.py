"""
ingest.py
----------
Entry point for building the Chroma knowledge base.

Modes
-----
Default (no flags)
    Ingest the IPCC AR6 HTML reference file only.

--xml-dir  <directory>
    Ingest all XML files under the given directory (plus any HTML files
    found there).  New files are picked up automatically on the next run.

--dir <directory>
    Ingest ALL supported documents (HTML + XML) under a directory.

--manifest <path>
    Load a chatbot_manifest.json (semantic_corpus export).

All modes write to the same Chroma collection so IPCC and research-paper
chunks are retrieved seamlessly by a single query.

Date: 2026-07-20 (refactored)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .pipeline import (
    build_chunks,
    build_chunks_from_directory,
    build_chunks_from_manifest,
)

# ─── Paths ────────────────────────────────────────────────────────────────────

# Anchor from this file's location: backend/ingest/ingest.py → go up two levels
# to reach the project root regardless of what the checkout folder is named.
# The old "while ROOT.name != 'ClimateInsight'" loop would crash if the repo
# was cloned under any other name (e.g. CI_Claude).
ROOT = Path(__file__).resolve().parent.parent.parent  # …/backend/ingest → project root

HTML_FILE = ROOT / "data" / "raw" / "ipcc_reference.html"
XML_DIR   = ROOT / "data" / "raw" / "ocean_heatwaves_2026"

CHUNK_SIZE = 400
OVERLAP    = 50


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _chunk_to_dict(chunk) -> dict:
    return chunk if isinstance(chunk, dict) else chunk.__dict__


# ─── Run functions ────────────────────────────────────────────────────────────


def run_from_html(html_path: Path) -> list:
    """Ingest the IPCC HTML reference (default mode)."""
    if not html_path.exists():
        print(f"ERROR: {html_path} not found.")
        sys.exit(1)
    return build_chunks(html_path, CHUNK_SIZE, OVERLAP)


def run_from_directory(directory: Path) -> list:
    """Ingest all supported documents under a directory."""
    if not directory.is_dir():
        print(f"ERROR: '{directory}' is not a directory.")
        sys.exit(1)
    return build_chunks_from_directory(directory, CHUNK_SIZE, OVERLAP)


def run_from_manifest(manifest_path: Path) -> list:
    """Ingest from a semantic_corpus chatbot_manifest.json."""
    if not manifest_path.is_file():
        print(f"ERROR: manifest not found: {manifest_path}")
        sys.exit(1)
    return build_chunks_from_manifest(manifest_path, CHUNK_SIZE, OVERLAP)


def run(
    manifest_path: Path | None = None,
    directory: Path | None = None,
    xml_dir: Path | None = None,
) -> None:
    """
    Select ingestion mode, build chunks, and write to ChromaDB.

    Priority: manifest > directory / xml_dir > HTML default.
    """
    if manifest_path is not None:
        chunks = run_from_manifest(Path(manifest_path))
    elif directory is not None:
        chunks = run_from_directory(Path(directory))
    elif xml_dir is not None:
        chunks = run_from_directory(Path(xml_dir))
    else:
        chunks = run_from_html(HTML_FILE)

    from vectorstore import collection_size, ingest_chunks

    ingest_chunks([_chunk_to_dict(c) for c in chunks])
    print(f"\nDone. ChromaDB now contains {collection_size()} chunks.")


# ─── CLI ──────────────────────────────────────────────────────────────────────


def main(argv: list | None = None) -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Ingest documents into the ClimateInsight Chroma knowledge base.\n\n"
            "Default: IPCC HTML reference.\n"
            "Use --xml-dir or --dir to ingest research papers (XML).\n"
            "Use --manifest for a semantic_corpus export."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--manifest",
        type=str,
        default=None,
        help="Path to chatbot_manifest.json (semantic_corpus export).",
    )
    parser.add_argument(
        "--dir",
        type=str,
        default=None,
        dest="directory",
        help="Ingest ALL supported documents under this directory (HTML + XML).",
    )
    parser.add_argument(
        "--xml-dir",
        type=str,
        default=None,
        dest="xml_dir",
        help=(
            "Ingest all supported documents under this directory. "
            f"Defaults to: {XML_DIR}"
        ),
    )

    args = parser.parse_args(argv)

    run(
        manifest_path=Path(args.manifest) if args.manifest else None,
        directory=Path(args.directory) if args.directory else None,
        xml_dir=Path(args.xml_dir) if args.xml_dir else None,
    )


if __name__ == "__main__":
    main()