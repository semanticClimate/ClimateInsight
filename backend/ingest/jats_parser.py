from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

from bs4 import BeautifulSoup, Tag

from .models import Section

MIN_PARAGRAPH_CHARS = 40

SKIP_SEC_TYPES = {
    "ref-list", "references", "bibliography", "ack", "acknowledgments",
    "acknowledgements", "fn-group", "footnotes", "associated-data",
    "supplementary-materials", "supplementary-material", "data-availability-statement",
    "competing-interests", "author-notes", "history", "kwd-group",
    "funding-statement", "funding",
}

SKIP_HEADINGS = {
    "references", "bibliography", "acknowledgements", "acknowledgments",
    "supplementary information", "supplementary material", "supplementary materials",
    "supporting information", "associated data", "data availability",
    "data availability statement", "source data", "code availability",
    "competing interests", "author contributions", "author contribution",
    "peer review", "peer review information", "open peer review",
    "reporting summary", "statistical and reproducibility", "funding statement", "funding",
}

DROP_TAGS = {"xref", "label"}
SKIP_CONTENT_TAGS = {"fig", "table-wrap", "supplementary-material", "media", "disp-formula", "code"}


def _clean_inline(tag: Tag) -> str:
    clone = BeautifulSoup(str(tag), "xml").find()
    if clone is None:
        return ""
    for el in clone.find_all(DROP_TAGS):
        el.decompose()
    text = clone.get_text(" ", strip=True)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _article_meta(soup: BeautifulSoup) -> tuple[str, str, str]:
    meta = soup.find("article-meta")
    if meta is None:
        return "", "", ""
    title = meta.find("article-title")
    title_text = title.get_text(" ", strip=True) if title else ""
    doi = ""
    pmcid = ""
    for ident in meta.find_all("article-id"):
        typ = (ident.get("pub-id-type") or "").lower()
        value = ident.get_text(strip=True)
        if typ == "doi":
            doi = value
        elif typ in {"pmcid", "pmc", "pmcaid", "pmcaiid"} and not pmcid:
            pmcid = value
    return title_text, doi, pmcid


def _skip_section(sec: Tag) -> bool:
    sec_type = (sec.get("sec-type") or "").lower()
    if sec_type in SKIP_SEC_TYPES:
        return True
    title = sec.find("title", recursive=False)
    heading = title.get_text(" ", strip=True).lower() if title else ""
    return heading in SKIP_HEADINGS


def _paragraphs_from_section(sec: Tag) -> list[str]:
    paragraphs: list[str] = []
    for child in sec.children:
        if not isinstance(child, Tag) or child.name in {"title", "label", "sec"}:
            continue
        if child.name in SKIP_CONTENT_TAGS:
            continue
        if child.name == "p":
            text = _clean_inline(child)
            if len(text) >= MIN_PARAGRAPH_CHARS:
                paragraphs.append(text)
        elif child.name == "list":
            items = [_clean_inline(li) for li in child.find_all("list-item", recursive=False)]
            items = [x for x in items if len(x) >= MIN_PARAGRAPH_CHARS]
            if items:
                paragraphs.append("; ".join(items))
    return paragraphs


def _walk(sec: Tag, ancestors: tuple[str, ...], counter: list[int], meta: tuple[str, str, str], source_file: str) -> list[Section]:
    if _skip_section(sec):
        return []
    title, doi, pmcid = meta
    title_el = sec.find("title", recursive=False)
    section_title = title_el.get_text(" ", strip=True) if title_el else f"Section {counter[0]}"
    counter[0] += 1
    path = ancestors + (section_title,)
    out: list[Section] = []
    text = "\n\n".join(_paragraphs_from_section(sec))
    if text:
        out.append(Section(pmcid, doi, title, section_title, path, text, source_file, counter[0]))
    for child in sec.find_all("sec", recursive=False):
        out.extend(_walk(child, path, counter, meta, source_file))
    return out


def parse_jats(path: Path) -> list[Section]:
    raw = path.read_text(encoding="utf-8", errors="ignore")
    soup = BeautifulSoup(raw, "xml")
    title, doi, pmcid = _article_meta(soup)
    source_file = str(path.resolve())
    sections: list[Section] = []

    for abstract in soup.find_all("abstract"):
        if (abstract.get("abstract-type") or "").lower() in {"web-summary", "graphical"}:
            continue
        paragraphs = [_clean_inline(p) for p in abstract.find_all("p")]
        paragraphs = [p for p in paragraphs if p]
        text = "\n\n".join(paragraphs)
        if len(text) >= MIN_PARAGRAPH_CHARS:
            sections.append(Section(pmcid, doi, title, "Abstract", ("Abstract",), text, source_file, 0))
            break

    body = soup.find("body")
    if body:
        counter = [1]
        for sec in body.find_all("sec", recursive=False):
            sections.extend(_walk(sec, (), counter, (title, doi, pmcid), source_file))

    if not sections and body:
        paragraphs = [_clean_inline(p) for p in body.find_all("p")]
        text = "\n\n".join(p for p in paragraphs if len(p) >= MIN_PARAGRAPH_CHARS)
        if text:
            sections.append(Section(pmcid, doi, title, "Article body", ("Article body",), text, source_file, 1))

    if not pmcid:
        pmcid = path.stem
        sections = [
            Section(s.pmcid or pmcid, s.doi, s.title, s.section_title, s.section_path, s.text, s.source_file, s.order)
            for s in sections
        ]
    return sections
