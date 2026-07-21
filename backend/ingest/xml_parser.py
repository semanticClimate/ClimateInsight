"""
xml_parser.py
--------------
Parse JATS XML scientific articles into Section objects.

JATS (Journal Article Tag Suite) is the PMC standard for research articles.
This parser:
  - Extracts article-level metadata: title, DOI, PMCID.
  - Walks the <body> recursively through nested <sec> elements.
  - Preserves the section hierarchy (ancestor titles) for context.
  - Extracts the abstract as a dedicated section.
  - Strips references, bibliography, acknowledgements, footnotes, figures,
    tables, and supplementary-material blocks — content not useful for RAG.
  - Returns Section objects identical to those produced by parse_html so the
    shared chunker is completely agnostic to the source format.

Registered in LOADER_REGISTRY as the handler for .xml files.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import List

from bs4 import BeautifulSoup, Tag

from .models import Section

# ─── Tuning ───────────────────────────────────────────────────────────────────

MIN_PARAGRAPH_LENGTH = 40  # characters; shorter paragraphs are noise

# ── sec-type values that should be excluded entirely ──────────────────────────
# Sourced by auditing all sec-type attributes across the full corpus.
SKIP_SEC_TYPES = {
    # References / bibliography
    "ref-list",
    "references",
    "bibliography",
    # Acknowledgements
    "ack",
    "acknowledgments",
    "acknowledgements",
    # Footnotes
    "fn-group",
    "footnotes",
    # Supplementary / supporting material
    "associated-data",
    "supplementary-materials",
    "supplementary-material",
    # Data / code availability
    "data-availability-statement",
    # Author / editorial metadata
    "competing-interests",
    "author-notes",
    "history",
    "kwd-group",
    # Funding
    "funding-statement",
    "funding",
}

# ── Heading text patterns to skip (for secs without a sec-type attribute) ─────
# Lower-cased; matched exactly against the section's direct <title> text.
SKIP_HEADINGS = {
    # References / bibliography
    "references",
    "bibliography",
    # Acknowledgements
    "acknowledgements",
    "acknowledgments",
    # Supplementary / supporting material
    "supplementary information",
    "supplementary material",
    "supplementary materials",
    "supporting information",
    "associated data",
    # Data / code availability
    "data availability",
    "data availability statement",
    "source data",
    "code availability",
    # Author / editorial metadata
    "competing interests",
    "author contributions",
    "author contribution",
    "peer review",
    "peer review information",
    "open peer review",
    "reporting summary",
    "statistical and reproducibility",
    # Funding
    "funding statement",
    "funding",
    # Footnotes
    "footnotes",
    # Impact / plain-language summaries (not scientific prose)
    "impact statements",
    "knowledge gaps",
}

# Tags whose text content to discard (in-line noise within paragraphs)
INLINE_NOISE_TAGS = {"xref", "sup", "sub", "fn", "label"}


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _slug(text: str, fallback: str = "sec") -> str:
    """Produce a URL-safe slug from a heading string."""
    slug = re.sub(r"[^a-z0-9]+", "-", text[:60].lower()).strip("-")
    return slug or fallback


def _clean_text(tag: Tag) -> str:
    """
    Extract clean prose text from a BeautifulSoup tag.

    Inline citation markers (<xref>, <sup>, etc.) are stripped so that
    paragraph text contains only prose without numeric reference noise.
    """
    # Work on a copy so we don't mutate the tree
    clone = BeautifulSoup(str(tag), "xml").find()
    if clone is None:
        return ""
    for noise in clone.find_all(INLINE_NOISE_TAGS):
        noise.decompose()
    text = clone.get_text(separator=" ", strip=True)
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip()


def _extract_metadata(soup: BeautifulSoup) -> dict:
    """
    Pull article-level metadata from <front><article-meta>.

    Returns a dict with keys: title, doi, pmcid.
    """
    meta: dict = {"title": "", "doi": "", "pmcid": ""}

    article_meta = soup.find("article-meta")
    if article_meta is None:
        return meta

    # Title
    title_tag = article_meta.find("article-title")
    if title_tag:
        meta["title"] = title_tag.get_text(" ", strip=True)

    # IDs
    for id_tag in article_meta.find_all("article-id"):
        pub_type = id_tag.get("pub-id-type", "")
        value = id_tag.get_text(strip=True)
        if pub_type == "doi":
            meta["doi"] = value
        elif pub_type in ("pmcid", "pmc"):
            meta["pmcid"] = value
        elif pub_type in ("pmcaid", "pmcaiid") and not meta["pmcid"]:
            # Some JATS files use pmcaid/pmcaiid instead of pmcid
            meta["pmcid"] = value

    return meta


def _extract_abstract(soup: BeautifulSoup, **section_kwargs) -> List[Section]:
    """
    Extract the primary abstract as a Section.

    JATS can have multiple <abstract> elements; we take the first one
    that is not a 'web-summary' (which is a short editorial blurb).
    """
    sections: List[Section] = []

    for abstract in soup.find_all("abstract"):
        if abstract.get("abstract-type") in {"web-summary", "graphical"}:
            continue
        paragraphs = [
            _clean_text(p)
            for p in abstract.find_all("p", recursive=True)
            if _clean_text(p)
        ]
        text = "\n\n".join(paragraphs)
        if len(text) < MIN_PARAGRAPH_LENGTH:
            continue
        sections.append(
            Section(
                text=text,
                section="abstract",
                section_title="Abstract",
                section_hierarchy=("Abstract",),
                **section_kwargs,
            )
        )
        break  # only the primary abstract

    return sections


def _should_skip_sec(sec: Tag) -> bool:
    """Return True if this <sec> should be excluded from RAG content."""
    sec_type = (sec.get("sec-type") or "").lower()
    if sec_type in SKIP_SEC_TYPES:
        return True
    # Detect by heading text for sections without sec-type attributes
    title_el = sec.find("title", recursive=False)
    if title_el:
        heading = title_el.get_text(" ", strip=True).lower()
        if heading in SKIP_HEADINGS:
            return True
    return False


def _walk_sec(
    sec: Tag,
    ancestor_titles: tuple,
    parent_slug: str,
    section_index: list,
    **section_kwargs,
) -> List[Section]:
    """
    Recursively walk a JATS <sec> element and produce Section objects.

    For nested <sec> elements, ancestor_titles accumulates the heading
    breadcrumb so each leaf section knows its full hierarchy.

    Parameters
    ----------
    sec             : The <sec> BeautifulSoup element.
    ancestor_titles : Tuple of heading strings for all ancestor sections.
    parent_slug     : Slug prefix inherited from ancestor sections.
    section_index   : Single-element list used as a mutable counter
                      (avoids nonlocal in Python 3.8 compatibility).
    **section_kwargs: Extra keyword args forwarded to every Section constructor
                      (source_path, document_title, source_type, doi, pmcid).
    """
    if _should_skip_sec(sec):
        return []

    sections: List[Section] = []

    # ── Section heading ──────────────────────────────────────────────────────
    title_el = sec.find("title", recursive=False)
    if title_el:
        heading = title_el.get_text(" ", strip=True)
    else:
        heading = f"Section {section_index[0]}"

    current_slug = _slug(heading, f"sec-{section_index[0]}")
    if parent_slug:
        current_slug = f"{parent_slug}__{current_slug}"

    section_index[0] += 1
    current_hierarchy = ancestor_titles + (heading,)

    # ── Direct child paragraphs (not inside child <sec>) ─────────────────────
    direct_paragraphs: List[str] = []
    for child in sec.children:
        if not isinstance(child, Tag):
            continue
        if child.name == "sec":
            continue                          # handled by recursion
        if child.name in {"fig", "table-wrap", "supplementary-material",
                          "media", "disp-formula", "code"}:
            continue                          # visual / non-prose content
        if child.name in {"title", "label"}:
            continue                          # already captured above
        if child.name == "p":
            text = _clean_text(child)
            if len(text) >= MIN_PARAGRAPH_LENGTH:
                direct_paragraphs.append(text)
        elif child.name == "list":
            # Flatten list items into prose
            items = [
                _clean_text(li)
                for li in child.find_all("list-item")
                if _clean_text(li)
            ]
            if items:
                direct_paragraphs.append("; ".join(items))

    if direct_paragraphs:
        sections.append(
            Section(
                text="\n\n".join(direct_paragraphs),
                section=current_slug,
                section_title=heading,
                section_hierarchy=current_hierarchy,
                **section_kwargs,
            )
        )

    # ── Recurse into child <sec> elements ─────────────────────────────────────
    for child_sec in sec.find_all("sec", recursive=False):
        sections.extend(
            _walk_sec(
                child_sec,
                current_hierarchy,
                current_slug,
                section_index,
                **section_kwargs,
            )
        )

    return sections


# ─── Public API ───────────────────────────────────────────────────────────────


def parse_xml(path: Path) -> List[Section]:
    """
    Parse a JATS XML research article and return a list of Section objects.

    Parsing strategy:
    1. Extract article-level metadata from <front>.
    2. Extract the abstract as a dedicated Section.
    3. Walk the <body> recursively through nested <sec> elements.
    4. Skip references, bibliography, acknowledgements, and other non-prose.

    Each returned Section is fully populated with:
      - text            : Paragraph prose for that section.
      - section         : Hierarchical slug (e.g. "results__subsection-a").
      - section_title   : Human-readable heading.
      - section_hierarchy: Full breadcrumb tuple.
      - source_path     : Absolute path to the XML file.
      - document_title  : Article title from <article-title>.
      - source_type     : Always "research_article".
      - doi             : DOI from <article-id pub-id-type="doi">.
      - pmcid           : PMCID from <article-id pub-id-type="pmcid">.

    Registered in LOADER_REGISTRY for .xml extension.
    """
    path = Path(path)
    print(f"Parsing XML: {path.name}...", end=" ", flush=True)

    raw = path.read_text(encoding="utf-8", errors="ignore")
    soup = BeautifulSoup(raw, "xml")

    # ── Metadata ──────────────────────────────────────────────────────────────
    metadata = _extract_metadata(soup)
    source_path = str(path.resolve())
    document_title = metadata["title"] or path.stem

    section_kwargs = dict(
        source_path=source_path,
        document_title=document_title,
        source_type="research_article",
        doi=metadata["doi"],
        pmcid=metadata["pmcid"],
    )

    sections: List[Section] = []

    # ── Abstract ──────────────────────────────────────────────────────────────
    sections.extend(_extract_abstract(soup, **section_kwargs))

    # ── Body ──────────────────────────────────────────────────────────────────
    body = soup.find("body")
    if body is not None:
        section_index = [1]  # mutable counter shared across recursive calls
        top_secs = body.find_all("sec", recursive=False)

        if top_secs:
            for sec in top_secs:
                sections.extend(
                    _walk_sec(
                        sec,
                        ancestor_titles=(),
                        parent_slug="",
                        section_index=section_index,
                        **section_kwargs,
                    )
                )
        else:
            # Flat body without <sec> structure: treat all paragraphs as one section
            flat_paragraphs = [
                _clean_text(p)
                for p in body.find_all("p")
                if _clean_text(p)
            ]
            if flat_paragraphs:
                sections.append(
                    Section(
                        text="\n\n".join(flat_paragraphs),
                        section="body",
                        section_title="Body",
                        section_hierarchy=("Body",),
                        **section_kwargs,
                    )
                )

    print(f"→ {len(sections)} sections  ('{document_title[:55]}{'...' if len(document_title)>55 else ''}')")
    return sections