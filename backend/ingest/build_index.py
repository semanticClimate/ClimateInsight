from __future__ import annotations

import json
import shutil
from pathlib import Path

from ..config import CHROMA_DIR, COLLECTION_NAME, CORPUS_DIR, INDEX_CACHE_DIR
from ..vectorstore.chroma_store import build_collection, reset_collection
from ..vectorstore.embeddings import embed_texts
from .chunker import chunk_sections
from .jats_parser import parse_jats


def load_chunks() -> list:
    chunks = []
    for path in sorted(CORPUS_DIR.glob("*.xml")):
        sections = parse_jats(path)
        if not sections:
            raise RuntimeError(f"No content extracted from {path.name}")
        chunks.extend(chunk_sections(sections))
        print(f"{path.name}: {len(sections)} sections")
    return chunks


def main() -> None:
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    INDEX_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    chunks = load_chunks()
    if not chunks:
        raise SystemExit("No XML papers found in corpus/")

    if CHROMA_DIR.exists():
        shutil.rmtree(CHROMA_DIR)
    reset_collection()
    collection = build_collection(COLLECTION_NAME)

    for start in range(0, len(chunks), 64):
        batch = chunks[start:start+64]
        texts = [c.text for c in batch]
        embeddings = embed_texts(texts)
        collection.add(
            ids=[c.chunk_id for c in batch],
            documents=texts,
            embeddings=embeddings,
            metadatas=[{
                "pmcid": c.pmcid,
                "doi": c.doi,
                "title": c.title,
                "section_title": c.section_title,
                "section_path": json.dumps(c.section_path, ensure_ascii=False),
                "source_file": c.source_file,
                "chunk_index": c.chunk_index,
                "word_start": c.word_start,
                "word_end": c.word_end,
            } for c in batch],
        )
        print(f"Indexed {min(start+64, len(chunks))}/{len(chunks)}")

    with open(INDEX_CACHE_DIR / "chunks.json", "w", encoding="utf-8") as f:
        json.dump([c.__dict__ for c in chunks], f, ensure_ascii=False, indent=2)
    print(f"Done. {len(chunks)} chunks in {COLLECTION_NAME}.")


if __name__ == "__main__":
    main()
