from __future__ import annotations

import re
from pathlib import Path

from .models import Chunk, Section

WORD_RE = re.compile(r"\S+")


def _split_text(text: str, target_words: int = 180, max_words: int = 260) -> list[tuple[str, int, int]]:
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks: list[tuple[str, int, int]] = []
    current: list[str] = []
    start = 0
    word_cursor = 0

    for para in paragraphs:
        para_words = WORD_RE.findall(para)
        if not para_words:
            continue
        if current and len(WORD_RE.findall(" ".join(current))) + len(para_words) > max_words:
            joined = " ".join(current).strip()
            end = start + len(WORD_RE.findall(joined))
            chunks.append((joined, start, end))
            start = end
            current = []
        current.append(para)
        current_words = len(WORD_RE.findall(" ".join(current)))
        if current_words >= target_words:
            joined = " ".join(current).strip()
            end = start + current_words
            chunks.append((joined, start, end))
            start = end
            current = []
        word_cursor += len(para_words)

    if current:
        joined = " ".join(current).strip()
        end = start + len(WORD_RE.findall(joined))
        chunks.append((joined, start, end))

    return chunks


def chunk_sections(sections: list[Section], target_words: int = 180, max_words: int = 260) -> list[Chunk]:
    out: list[Chunk] = []
    counters: dict[str, int] = {}
    for section in sections:
        if not section.pmcid:
            raise ValueError(f"Missing PMCID for {section.source_file}")
        pieces = _split_text(section.text, target_words, max_words)
        for local_index, (text, start, end) in enumerate(pieces):
            section_key = "__".join(section.section_path) or section.section_title
            stable_id = f"{section.pmcid}::{section_key}::chunk_{local_index:03d}"
            counters[section.pmcid] = counters.get(section.pmcid, 0) + 1
            out.append(Chunk(
                chunk_id=stable_id,
                pmcid=section.pmcid,
                doi=section.doi,
                title=section.title,
                section_title=section.section_title,
                section_path=section.section_path,
                text=text,
                source_file=section.source_file,
                chunk_index=local_index,
                word_start=start,
                word_end=end,
            ))
    return out
