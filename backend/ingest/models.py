from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Section:
    pmcid: str
    doi: str
    title: str
    section_title: str
    section_path: tuple[str, ...]
    text: str
    source_file: str
    order: int


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    pmcid: str
    doi: str
    title: str
    section_title: str
    section_path: tuple[str, ...]
    text: str
    source_file: str
    chunk_index: int
    word_start: int
    word_end: int
