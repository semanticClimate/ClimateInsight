"""
ingest.py
----------
Entry point for building the Chroma database.

Default: IPCC HTML reference.
Optional: --manifest chatbot_manifest.json from semantic_corpus.

Date: 2026-07-16 (system date of generation)
"""

import argparse
import sys
from pathlib import Path

from .pipeline import build_chunks

ROOT = Path(__file__).resolve()

while ROOT.name != "ClimateInsight":
    ROOT = ROOT.parent

HTML_FILE = Path(ROOT, "data", "raw", "ipcc_reference.html")

CHUNK_SIZE = 400
OVERLAP = 50


def _chunk_to_dict(chunk) -> dict:
    return chunk if isinstance(chunk, dict) else chunk.__dict__


def run_from_html(html_path: Path) -> list:
    if not html_path.exists():
        print(f"ERROR: {html_path} not found.")
        sys.exit(1)
    return build_chunks(html_path, CHUNK_SIZE, OVERLAP)


def run_from_manifest(manifest_path: Path) -> list:
    from ingest.manifest_ingest.build_from_manifest import build_chunks_from_manifest

    if not manifest_path.is_file():
        print(f"ERROR: manifest not found: {manifest_path}")
        sys.exit(1)
    return build_chunks_from_manifest(
        manifest_path,
        chunk_size=CHUNK_SIZE,
        overlap=OVERLAP,
    )


def run(manifest_path: Path = None) -> None:
    if manifest_path is not None:
        chunks = run_from_manifest(Path(manifest_path))
    else:
        chunks = run_from_html(HTML_FILE)

    from vectorstore import collection_size, ingest_chunks

    ingest_chunks([_chunk_to_dict(chunk) for chunk in chunks])
    print(f"\nDone. ChromaDB now contains {collection_size()} chunks.")


def main(argv: list = None) -> None:
    parser = argparse.ArgumentParser(
        description="Ingest IPCC HTML or a semantic_corpus chatbot_manifest.json"
    )
    parser.add_argument(
        "--manifest",
        type=str,
        default=None,
        help="Path to chatbot_manifest.json (semantic_corpus export)",
    )
    args = parser.parse_args(argv)
    run(manifest_path=Path(args.manifest) if args.manifest else None)


if __name__ == "__main__":
    main()
