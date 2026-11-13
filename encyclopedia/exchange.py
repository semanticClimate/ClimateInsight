"""Read and render portable ami_entry HTML without live Wikipedia lookups.

Applications can use this boundary without importing amilib, extraction models,
or the Encyclopedia chatbot. Descriptions and document evidence stay separate.
"""

from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from html import escape
from pathlib import Path
from urllib.parse import quote, urljoin, urlparse

from lxml import html


_QID = re.compile(r"^[QP]\d+$", re.I)
_SKIP = {"footnote", "foot-note", "reference", "caption", "charoverride"}


def _text(value):
    return " ".join(str(value or "").split())


def wikipedia_url(value):
    """An English Wikipedia article URL, or None for other destinations."""
    value = urljoin("https://en.wikipedia.org", str(value or "").strip())
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or parsed.hostname != "en.wikipedia.org":
        return None
    if not parsed.path.startswith("/wiki/") or ":" in parsed.path[len("/wiki/"):]:
        return None
    return "https://en.wikipedia.org" + parsed.path


def read_entries(path):
    """Read term entries, aliases and descriptions from an Encyclopedia export."""
    root = html.fromstring(Path(path).read_bytes())
    entries = []
    for entry in root.xpath("//*[@role='ami_entry']"):
        if entry.get("data-hidden", "").lower() == "true":
            continue
        canonical = entry.xpath(".//li[contains(concat(' ',normalize-space(@class),' '),' canonical_synonym ')]")
        name = _text(canonical[0].text_content()) if canonical else _text(entry.get("term") or entry.get("name"))
        name = re.sub(r"\s*\(canonical\)\s*$", "", name, flags=re.I)
        if not name or name == "No Wikipedia article":
            continue
        aliases = [name, entry.get("term"), entry.get("name")]
        aliases += [node.text_content() for node in entry.xpath(".//ul[contains(concat(' ',normalize-space(@class),' '),' synonym_list ')]/li")]
        aliases = [re.sub(r"\s*\(canonical\)\s*$", "", _text(value), flags=re.I) for value in aliases]
        descriptions = entry.xpath(".//p[contains(concat(' ',normalize-space(@class),' '),' wpage_first_para ')]")
        own_links = entry.xpath("./a[contains(concat(' ',normalize-space(@class),' '),' wikipedia-link ')]/@href")
        if not own_links:
            own_links = entry.xpath("./a/@href")
        own_url = next((url for value in own_links if (url := wikipedia_url(value))), None)
        identifier = entry.get("wikidataID") or entry.get("wikidataid") or entry.get("data-entry-id") or ""
        entries.append({
            "canonical_name": name,
            "synonyms": sorted({a for a in aliases if a and a.casefold() != name.casefold()}, key=lambda a: (a.casefold(), a)),
            "description": _text(descriptions[0].text_content()) if descriptions else None,
            "wikidata_id": identifier.upper() if _QID.fullmatch(identifier) else None,
            "wikipedia_url": own_url,
            "source_file": Path(path).as_posix(),
        })
    return entries


def _paragraph_anchors(root):
    """Keep original IDs and disambiguate repeated IDs in the served view."""
    occurrences = defaultdict(int)
    for paragraph in root.xpath("//p[@id]"):
        if paragraph.xpath("ancestor::*[@role='ami_encyclopedia']"):
            continue
        original = paragraph.get("id")
        occurrences[original] += 1
        anchor = original
        if occurrences[original] > 1:
            key = f"{original}\0{occurrences[original]}"
            anchor = "ci-source-" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
        yield paragraph, anchor


def report_contexts(report_html, find_concepts, limit=3):
    """Find known concepts in anchored report paragraphs; retain source IDs."""
    root = html.fromstring(report_html)
    found = defaultdict(list)
    for paragraph, anchor in _paragraph_anchors(root):
        classes = {value.lower() for value in paragraph.get("class", "").split()}
        ancestors = paragraph.xpath("ancestor::*[contains(@class, '_idFootnotes') or @role='ami_encyclopedia']")
        if classes & _SKIP or ancestors:
            continue
        text = _text(paragraph.text_content())
        if not text:
            continue
        for concept in sorted(set(find_concepts(text))):
            if len(found[concept]) < limit:
                found[concept].append({"html_id": anchor, "text": text})
    return dict(found)


def render_entries(concepts, contexts=None, title="Report Encyclopedia", source_url="/ipcc-reference"):
    """A portable ami_encyclopedia fragment, with separately labelled evidence."""
    contexts = contexts or {}
    parts = [f'<div role="ami_encyclopedia" title="{escape(title, quote=True)}" id="ci-encyclopedia">']
    for concept in sorted(concepts, key=lambda item: item["canonical_name"].casefold()):
        name = concept["canonical_name"]
        identifier = str(concept.get("wikidata_id") or "")
        qid = identifier.upper() if _QID.fullmatch(identifier) else ""
        entry_id = qid or "term_" + hashlib.sha256(name.casefold().encode("utf-8")).hexdigest()[:16]
        attrs = f'role="ami_entry" term="{escape(name, quote=True)}" data-entry-id="{escape(entry_id, quote=True)}"'
        if qid:
            attrs += f' wikidataID="{qid}"'
        parts.append(f'<div {attrs}><h2>{escape(name)}</h2>')
        own_url = wikipedia_url(concept.get("wikipedia_url"))
        if own_url:
            parts.append(f'<a class="wikipedia-link" href="{escape(own_url, quote=True)}" target="_blank" rel="noopener">{escape(name)}</a>')
        if qid:
            parts.append(f' <a class="wikidata-link" href="https://www.wikidata.org/wiki/{qid}" target="_blank" rel="noopener">{qid}</a>')
        synonyms = sorted(set(concept.get("synonyms") or []) - {name}, key=str.casefold)
        if synonyms:
            parts.append('<ul class="synonym_list">')
            parts.append(f'<li class="canonical_synonym">{escape(name)} (canonical)</li>')
            parts += [f'<li>{escape(alias)}</li>' for alias in synonyms]
            parts.append('</ul>')
        description = concept.get("description")
        if description:
            parts.append('<p class="definition-source">Description: Wikipedia, via Encyclopedia.</p>')
            parts.append(f'<p class="wpage_first_para">{escape(description)}</p>')
        else:
            parts.append('<p class="no-description">No imported Wikipedia description is available.</p>')
        if contexts.get(name):
            parts.append('<h3>In the IPCC report</h3><ul class="source-examples">')
            for context in contexts[name]:
                url = source_url + "#" + quote(context["html_id"], safe="")
                excerpt = context["text"][:700] + ("…" if len(context["text"]) > 700 else "")
                parts.append(f'<li><blockquote>{escape(excerpt)}</blockquote><a class="source-link" href="{escape(url, quote=True)}">Read the IPCC passage</a></li>')
            parts.append('</ul>')
        parts.append('</div>')
    parts.append('</div>')
    return "".join(parts)


def report_with_entries(report_html, fragment, glossary_url=None):
    """Append an expandable glossary; preserve original paragraphs and anchors."""
    root = html.document_fromstring(report_html)
    body = root.find("body")
    for paragraph, anchor in _paragraph_anchors(root):
        if anchor != paragraph.get("id") and not paragraph.xpath(".//*[@id=$anchor]", anchor=anchor):
            paragraph.insert(0, html.Element("span", id=anchor))
    existing = root.xpath("//*[@id='ci-report-encyclopedia']")
    for element in existing:
        element.getparent().remove(element)
    for element in root.xpath("//*[@id='ci-encyclopedia-link']"):
        element.getparent().remove(element)
    if glossary_url:
        navigation = html.Element("p", id="ci-encyclopedia-link")
        link = html.Element("a", href=glossary_url)
        link.text = "Explore the report Encyclopedia"
        navigation.append(link)
        headings = body.xpath(".//h1")
        if headings:
            headings[0].addnext(navigation)
        else:
            body.insert(0, navigation)
    details = html.Element("details", id="ci-report-encyclopedia")
    summary = html.Element("summary")
    summary.text = "Explore the Encyclopedia for this report"
    details.append(summary)
    details.append(html.fromstring(fragment))
    body.append(details)
    return html.tostring(root, encoding="unicode", doctype="<!DOCTYPE html>")
