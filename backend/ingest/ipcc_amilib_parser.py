"""
ipcc_amilib_parser.py
---------------------
Read IPCC AR6 chapters that have been cleaned by semanticClimate's amilib.

Why this exists
---------------
semanticClimate already turns raw IPCC web pages into clean, semantic HTML.
amilib's IPCC tools (``IPCCGatsby`` / ``IPCCWordpress``) strip the site's
navigation, wrap every heading in a nested ``div.hN-container`` whose ``id``
is the section number, and give every body paragraph a stable id such as
``2.1.1_p3``. The result is published as ``html_with_ids.html`` for each
chapter (49 AR6 chapters, including the SYR Longer Report, are in amilib's
``test/resources/ipcc/cleaned_content``).

ClimateInsight should not re-clean those pages with its own heuristics.
This module only *reads* amilib's format and maps it onto our ``Section``
model. ``loader_registry`` uses it for every HTML file in amilib's IPCC
format, including ``data/raw/ipcc_reference.html`` and chapters fetched
by ``scripts/fetch_ipcc_from_amilib.py``.

amilib format, as relied on here
--------------------------------
    <div class="h2-container" id="2.1">
      <h2>2.1 Observed Changes, Impacts and Attribution</h2>
      <div class="h2-siblings">
        <p class="Body" id="2.1_p1">...</p>
        <div class="h3-container" id="2.1.1"> ... </div>
      </div>
    </div>

* A section is a ``div`` whose class includes ``h1-container`` ..
  ``h6-container``; its heading is its first ``h1``-``h6`` child.
* A paragraph is a ``p`` with an ``id`` (plus id-less body ``p``/``li``);
  it belongs to its nearest enclosing container.
* Section numbers are read from the heading text, not the container id:
  the IPCC site occasionally repeats an id (the SYR has two ``2.2.3``
  containers), while the heading number is always right.

If amilib changes this format, ``tests/test_ipcc_amilib_parser.py`` fails
and this file is the only place to update.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable, List, Optional

from lxml import etree, html

from .models import Section

SOURCE_TYPE = "ipcc_report"

_CONTAINER_XPATH = "self::div[re:test(@class, '(^|\\s)h[1-6]-container(\\s|$)')]"
_NS = {"re": "http://exslt.org/regular-expressions"}

# Paragraph classes amilib ids but which are not prose for retrieval:
# the bibliography and the chapter's table of contents.
_SKIP_PARAGRAPH_CLASS = re.compile(r"References|Chapter-contents", re.IGNORECASE)

# Containers whose paragraphs are not prose: figures, captions, footnotes,
# author lists and the recommended citation.
_NON_PROSE_CONTAINER = re.compile(
    r"figure|caption|footnote|chapter-authors|chapter-citation", re.IGNORECASE
)
_FOOTNOTE_TEXT = re.compile(r"^(\d{1,3}\s+(See|Based on|Ibid)|\*)")
MIN_UNIDENTIFIED_LENGTH = 40  # same threshold as parser.py

# Sections whose whole content is the bibliography.
_SKIP_SECTION_TITLES = {"references"}

_HEADING_TAGS = ("h1", "h2", "h3", "h4", "h5", "h6")
_SECTION_NUMBER = re.compile(r"^(\d+(?:\.\d+)*)\.?\s*(.*)$")


# ─── Detection ────────────────────────────────────────────────────────────────


def is_amilib_ipcc_html(root: etree._Element) -> bool:
    """True when *root* is amilib's ``html_with_ids`` IPCC format."""
    has_container = bool(root.xpath(
        "//div[re:test(@class, '(^|\\s)h1-container(\\s|$)')]", namespaces=_NS
    ))
    has_para_ids = bool(root.xpath("//p[@id]"))
    return has_container and has_para_ids


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _element_text(elem: etree._Element) -> str:
    """
    Paragraph text in the same form as parser.py produces: text pieces
    joined by single spaces (so "CO<sub>2</sub>" becomes "CO 2", which the
    concept matcher expects).
    """
    # itertext() includes text after inline children but not elem's own tail.
    pieces = (s.strip() for s in elem.itertext() if s and s.strip())
    return re.sub(r"\s{2,}", " ", " ".join(pieces)).strip()


def _is_container(elem: etree._Element) -> bool:
    return bool(elem.xpath(_CONTAINER_XPATH, namespaces=_NS))


def _nearest_container(elem: etree._Element) -> Optional[etree._Element]:
    for ancestor in elem.iterancestors("div"):
        if _is_container(ancestor):
            return ancestor
    return None


def _heading_text(container: etree._Element) -> str:
    for child in container:
        if isinstance(child.tag, str) and child.tag.lower() in _HEADING_TAGS:
            return _clean(child.text_content())
    return ""


def _section_id_and_title(container: etree._Element) -> tuple[str, str]:
    """('2.1.1', 'Observed Warming and its Causes') from the heading text."""
    heading = _heading_text(container)
    match = _SECTION_NUMBER.match(heading)
    if match:
        return match.group(1), match.group(2).strip() or heading
    fallback = heading or container.get("id", "") or "section"
    slug = re.sub(r"[^a-z0-9]+", "-", fallback.lower()).strip("-")
    return slug or "section", heading or fallback


def _hierarchy(container: etree._Element) -> tuple[str, ...]:
    """Headings of the enclosing containers, outermost first, excluding self."""
    titles = [
        _heading_text(a)
        for a in container.iterancestors("div")
        if _is_container(a)
    ]
    return tuple(t for t in reversed(titles) if t)


def _document_title(root: etree._Element, path: Path) -> str:
    """
    The chapter heading (first ``h1``), widened to the page ``<title>`` when
    that title contains it (WG chapters: "Chapter 1: ... | Climate Change
    2021: ..."). The SYR page's <title> is wrongly "Summary for
    Policymakers", which this rule ignores.
    """
    first_h1 = root.xpath("//h1")
    h1_text = _clean(first_h1[0].text_content()) if first_h1 else ""
    title_text = _clean(root.findtext(".//title") or "")
    if h1_text and h1_text in title_text:
        return title_text
    return h1_text or title_text or path.stem


def _is_skipped(container: etree._Element) -> bool:
    for c in [container, *[a for a in container.iterancestors("div") if _is_container(a)]]:
        if _heading_text(c).lower() in _SKIP_SECTION_TITLES:
            return True
    return False


def _inside_non_prose(p: etree._Element) -> bool:
    """Figures, captions, footnotes and author lists amilib leaves in place."""
    for a in p.iterancestors():
        cls = a.get("class") or ""
        if _NON_PROSE_CONTAINER.search(cls):
            return True
    return False


def _paragraphs(root: etree._Element) -> Iterable[etree._Element]:
    """
    amilib's id'd paragraphs, plus body paragraphs and list items amilib
    left without an id (e.g. the SYR's headline statements and risk lists),
    in document order.
    """
    for p in root.iter("p", "li"):
        if p.tag == "li" and p.find(".//p") is not None:
            continue  # its <p> children are yielded themselves
        if _SKIP_PARAGRAPH_CLASS.search(p.get("class") or ""):
            continue
        text = _element_text(p)
        if not text:
            continue
        if not p.get("id"):
            if len(text) < MIN_UNIDENTIFIED_LENGTH or _inside_non_prose(p):
                continue
            if _FOOTNOTE_TEXT.match(text) or _NON_PROSE_CONTAINER.search(p.get("class") or ""):
                continue
        yield p


# ─── Public API ───────────────────────────────────────────────────────────────


def parse_root(root: etree._Element, path: Path) -> List[Section]:
    """Map an already-parsed amilib IPCC document onto Section objects."""
    source_path = str(Path(path).resolve())
    document_title = _document_title(root, Path(path))

    # Group paragraphs by their nearest container, keeping document order.
    groups: dict[int, tuple[etree._Element, list[etree._Element]]] = {}
    order: list[int] = []
    for p in _paragraphs(root):
        container = _nearest_container(p)
        if container is None or _is_skipped(container):
            continue
        key = id(container)
        if key not in groups:
            groups[key] = (container, [])
            order.append(key)
        groups[key][1].append(p)

    sections: List[Section] = []
    for key in order:
        container, paras = groups[key]
        section_id, title = _section_id_and_title(container)
        first_id = next((p.get("id") for p in paras if p.get("id")), "")
        sections.append(
            Section(
                text="\n\n".join(_element_text(p) for p in paras),
                section=section_id,
                section_title=title,
                html_id=first_id,
                source_path=source_path,
                document_title=document_title,
                source_type=SOURCE_TYPE,
                section_hierarchy=_hierarchy(container),
            )
        )
    return sections


def parse_ipcc_amilib(path: Path) -> List[Section]:
    """Parse one amilib ``html_with_ids`` IPCC chapter into Sections."""
    path = Path(path)
    root = html.parse(str(path)).getroot()
    if not is_amilib_ipcc_html(root):
        raise ValueError(f"{path} is not amilib html_with_ids IPCC HTML")
    sections = parse_root(root, path)
    print(f"Parsed amilib IPCC HTML {path.name}: {len(sections)} sections.")
    return sections