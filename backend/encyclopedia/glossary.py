"""Convert the AR6 SYR glossary and merge its definitions into the vocabulary.

The PDF's bold term headings are authoritative. Model phrases supplement them;
they never become definitions unless they match a glossary term. This module
does not ingest documents or open the chatbot's vector store.
"""

from __future__ import annotations

from copy import deepcopy
from html import escape
import hashlib
import json
from pathlib import Path
import re
import unicodedata

from lxml import html, etree


GLOSSARY_LABEL = "IPCC AR6 SYR Glossary"
OFFICIAL_URL = "https://www.ipcc.ch/report/ar6/syr/downloads/report/IPCC_AR6_SYR_Annex-I.pdf"


def identity(term):
    value = unicodedata.normalize("NFKC", term).casefold()
    value = re.sub(r"[\u2010-\u2015]", "-", value)
    return " ".join(value.split()).strip()


def term_aliases(term):
    """Keep literal headings and expand their explicit acronym/qualifier form."""
    aliases = {term}
    match = re.fullmatch(r"(.+?)\s*\(([^()]+)\)", term)
    if match:
        base, qualifier = match.groups()
        aliases.add(base.strip())
        if re.fullmatch(r"[A-Z][A-Za-z0-9+\-]*", qualifier) and any(c.isupper() for c in qualifier[1:]):
            aliases.add(qualifier)
    return sorted(aliases, key=str.casefold)


def _join_lines(lines):
    # Only repair an actual soft hyphen, retaining ordinary hyphenated terms.
    return " ".join(lines).replace("\u00ad ", "").replace("\u00ad", "").strip()


def convert_glossary(pdf_path, output_path, *, source_file=None, source_url=OFFICIAL_URL):
    """Read the single-column SYR Annex I layout, preserving cross-page entries."""
    import fitz

    pdf_path, output_path = Path(pdf_path), Path(output_path)
    entries = []
    current = None
    paragraph = []
    started = False

    def flush_paragraph():
        if current is not None and paragraph:
            current["paragraphs"].append(_join_lines(paragraph))
        paragraph.clear()

    with fitz.open(pdf_path) as document:
        for page in document:
            lines = [line for block in page.get_text("dict")["blocks"]
                     for line in block.get("lines", [])]
            body = sorted((line for line in lines if 50 <= line["bbox"][1] < page.rect.height - 57),
                          key=lambda line: (round(line["bbox"][1], 1), line["bbox"][0]))
            if not any(any(s["text"].strip() for s in line["spans"]) for line in body):
                raise ValueError(f"Glossary PDF page {page.number + 1} has no readable text; obtain an intact PDF")
            for line in body:
                spans = [span for span in line["spans"] if span["text"].strip()]
                text = "".join(span["text"] for span in line["spans"]).strip()
                if not text:
                    flush_paragraph()
                    continue
                heading = bool(spans) and all(span["flags"] & 16 for span in spans)
                # The first page has a title/editorial preamble above the terms.
                if not started and page.number == 0 and line["bbox"][1] < 350:
                    continue
                if heading:
                    flush_paragraph()
                    started = True
                    current = {"term": text, "page": page.number + 1, "pages": [page.number + 1],
                               "subterm": line["bbox"][0] > 80, "paragraphs": []}
                    current["html_id"] = "term-" + hashlib.sha256(identity(text).encode()).hexdigest()[:12]
                    entries.append(current)
                elif current is not None:
                    if page.number + 1 not in current["pages"]:
                        current["pages"].append(page.number + 1)
                    paragraph.append(text)
        flush_paragraph()
        page_count = len(document)
    if not entries or any(not entry["paragraphs"] for entry in entries):
        raise ValueError("Glossary conversion did not produce complete term-definition pairs")

    # Cross-reference headings can recur as fully defined subterms. Keep one
    # HTML anchor per term and prefer the full definition to a 'See:' entry.
    groups = {}
    for entry in entries:
        entry["definition"] = "\n\n".join(entry["paragraphs"])
        key = identity(entry["term"])
        prior = groups.get(key)
        if prior is None or (prior["definition"].startswith("See:") and not entry["definition"].startswith("See:")):
            groups[key] = entry
    records = list(groups.values())
    source = source_file or pdf_path.as_posix()
    parts = ['<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">',
             '<meta name="viewport" content="width=device-width,initial-scale=1">',
             f'<title>{GLOSSARY_LABEL}</title>',
             '<style>body{font:18px/1.65 Georgia,serif;max-width:850px;margin:2rem auto;padding:0 1.2rem;color:#222}'
             'h1,h2{font-family:system-ui,sans-serif;line-height:1.3}h2{font-size:1.3rem}'
             'section{padding:1rem 0;border-bottom:1px solid #ddd;scroll-margin-top:1rem}'
             '.source{font:14px/1.5 system-ui,sans-serif;color:#555}a{color:#1b4f9b}</style></head><body>',
             f'<h1>{GLOSSARY_LABEL}</h1><p class="source">Annex I, 2023. '
             f'<a href="{escape(source_url, quote=True)}">Official IPCC PDF</a>. '
             'The source edition is marked “Subject to copyedit”. '
             'Definitions and cross-references are transcribed from the PDF; '
             'page numbers refer to its glossary pages.</p>']
    for entry in records:
        parts.append(f'<section class="glossary-entry" id="{entry["html_id"]}" '
                     f'data-term="{escape(entry["term"], quote=True)}" data-page="{entry["page"]}">')
        parts.append(f'<h2>{escape(entry["term"])}</h2>')
        parts.extend(f'<p class="definition">{escape(value)}</p>' for value in entry["paragraphs"])
        parts.append(f'<p class="source"><a href="{escape(source_url, quote=True)}#page={entry["page"]}">'
                     f'IPCC glossary, page {entry["page"]}</a></p></section>')
    parts.append('</body></html>')
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(parts) + "\n", encoding="utf-8")
    return records, {"source_file": source, "source_sha256": hashlib.sha256(pdf_path.read_bytes()).hexdigest(),
                     "source_url": source_url, "pages": page_count, "defined_terms": len(records)}


def merge_glossary(concepts, entries, phrases, source_file):
    """Preserve existing identities and prefer exact IPCC definitions to Wikipedia."""
    concepts = deepcopy(concepts)
    for concept in concepts:
        concept.setdefault("source_files", [concept["source_file"]])
        concept.setdefault("description_source", "Wikipedia" if concept.get("description") else None)
    for entry in entries:
        aliases = term_aliases(entry["term"])
        literal = identity(entry["term"])
        base = identity(re.sub(r"\s*\([^()]+\)$", "", entry["term"]))
        # Prefer the spelled-out term to an acronym: Wikipedia's "SIDS"
        # describes infant death, whereas this glossary means island states.
        candidates = [c for c in concepts if identity(c["canonical_name"]) == literal]
        if not candidates:
            candidates = [c for c in concepts if identity(c["canonical_name"]) == base]
        if not candidates:
            candidates = [c for c in concepts if not c.get("definition_source") and
                          {literal, base}.intersection(identity(a) for a in c.get("synonyms", []))]
        concept = candidates[0] if len(candidates) == 1 else None
        if concept is None:
            concept = {"canonical_name": entry["term"],
                       "synonyms": [], "description": None, "wikidata_id": None,
                       "wikipedia_url": None, "source_file": source_file, "source_files": []}
            concepts.append(concept)
        if concept.get("description_source") == "Wikipedia" and concept.get("description"):
            concept["wikipedia_description"] = concept["description"]
        concept["synonyms"] = sorted(set(concept.get("synonyms", []) + aliases) - {concept["canonical_name"]}, key=str.casefold)
        concept["description"] = entry["definition"]
        concept["description_source"] = GLOSSARY_LABEL
        concept["definition_source"] = {"source_file": source_file, "page": entry["page"],
                                        "pages": entry["pages"], "html_id": entry["html_id"], "term": entry["term"]}
        concept["source_files"] = sorted(set(concept["source_files"] + [source_file]))

    # A defined heading owns its alias. For example the glossary distinguishes
    # Global warming from Climate change even if Wikipedia redirects the former.
    owners = {}
    for concept in concepts:
        if concept.get("definition_source"):
            for alias in term_aliases(concept["definition_source"]["term"]):
                owners[identity(alias)] = concept["canonical_name"]
    for concept in concepts:
        concept["synonyms"] = [a for a in concept["synonyms"]
                               if owners.get(identity(a), concept["canonical_name"]) == concept["canonical_name"]]
    retained = []
    by_name = {c["canonical_name"]: c for c in concepts}
    for concept in concepts:
        owner = owners.get(identity(concept["canonical_name"]))
        if owner and owner != concept["canonical_name"] and not concept.get("definition_source"):
            target = by_name[owner]
            target["source_files"] = sorted(set(target["source_files"] + concept["source_files"]))
            for field in ("term_sources", "alias_sources", "source_excerpts"):
                for proof in concept.get(field, []):
                    if proof not in target.setdefault(field, []):
                        target[field].append(proof)
            target.setdefault("replaced_report_identities", []).append({
                field: concept.get(field) for field in ("canonical_name", "wikidata_id", "wikipedia_url")})
        else:
            retained.append(concept)
    concepts = retained

    for phrase in phrases:
        key = identity(phrase)
        matches = [c for c in concepts if key in {identity(c["canonical_name"]), *(identity(a) for a in c["synonyms"])}]
        if len(matches) == 1:
            matches[0]["source_files"] = sorted(set(matches[0]["source_files"] + [source_file]))
        elif not matches:
            concepts.append({"canonical_name": phrase, "synonyms": [], "description": None,
                             "description_source": None, "wikidata_id": None, "wikipedia_url": None,
                             "source_file": source_file, "source_files": [source_file]})
    return sorted(concepts, key=lambda c: (c["canonical_name"].casefold(), c["canonical_name"]))


def render_entries(exchange, concepts, contexts=None, **options):
    """Add accurate definition attribution to the shared portable renderer."""
    fragment = html.fromstring(exchange.render_entries(concepts, contexts, **options))
    by_name = {c["canonical_name"]: c for c in concepts}
    for element in fragment.xpath(".//*[@role='ami_entry']"):
        concept = by_name[element.get("term")]
        if concept.get("source_excerpts"):
            heading = etree.SubElement(element, "h3")
            heading.text = "Evidence from the approved documents"
            for example in concept["source_excerpts"]:
                quote = etree.SubElement(element, "blockquote")
                quote.text = example["text"][:700] + ("…" if len(example["text"]) > 700 else "")
                link = etree.SubElement(element, "a", href=example["url"], attrib={"class": "corpus-source-link"})
                link.text = "Read the source: " + example["title"]
                label = etree.SubElement(element, "p", attrib={"class": "source-file"})
                label.text = example["source_file"]
        definition = concept.get("definition_source")
        if not definition:
            continue
        labels = element.xpath("./p[@class='definition-source']")
        if labels:
            label = labels[0]
            label.text = f"Definition: {GLOSSARY_LABEL}, page {definition['page']}. "
            link = html.Element("a", href="/ipcc-glossary#" + definition["html_id"])
            link.text = "Read the glossary entry"
            label.append(link)
    return html.tostring(fragment, encoding="unicode")


def enrich_artifact(artifact, pdf_path, output_dir, *, root, top_n=500, max_terms=300, min_count=1):
    """Convert, extract with the existing model adapter, then merge an artifact."""
    from backend.encyclopedia.pipeline import extract_report_wordlist

    root, pdf_path, output_dir = Path(root), Path(pdf_path).resolve(), Path(output_dir)
    try:
        source_file = pdf_path.relative_to(root.resolve()).as_posix()
    except ValueError:
        source_file = pdf_path.as_posix()
    converted = output_dir / "IPCC_AR6_SYR_Glossary.html"
    entries, provenance = convert_glossary(pdf_path, converted, source_file=source_file)
    # Extract only the glossary term/definition content, without page furniture
    # or conversion provenance, while retaining a readable HTML deliverable.
    extraction_html = output_dir / "extraction.html"
    document = html.fromstring(converted.read_text(encoding="utf-8"))
    for node in document.xpath("//p[@class='source']|//h1"):
        node.drop_tree()
    extraction_html.write_text(html.tostring(document, encoding="unicode"), encoding="utf-8")
    terms, wordlist, prepared = extract_report_wordlist(extraction_html, output_dir / "extraction",
                                                       top_n=top_n, max_terms=max_terms, min_count=min_count)
    source_text = identity(document.text_content())
    accepted = [term for term in terms if re.search(r"(?<!\w)" + re.escape(identity(term)) + r"(?!\w)", source_text)]
    result = deepcopy(artifact)
    result["concepts"] = merge_glossary(result["concepts"], entries, accepted, source_file)
    provenance.update({"extractor": "txt2phrases", "top_n": top_n, "max_terms": max_terms,
                       "min_count": min_count, "selected_keyphrases": len(terms),
                       "accepted_keyphrases": len(accepted),
                       "rejected_nonliteral_keyphrases": [term for term in terms if term not in accepted],
                       "wordlist_sha256": hashlib.sha256(wordlist.read_bytes()).hexdigest(),
                       "html_sha256": hashlib.sha256(converted.read_bytes()).hexdigest(),
                       "converted_html": "encyclopedia_assets/generated/glossary/IPCC_AR6_SYR_Glossary.html"})
    result["provenance"]["glossary"] = provenance
    result["summary"].update({"source_files_processed": 2, "unique_concepts_exported": len(result["concepts"]),
                             "raw_entries_discovered": artifact["summary"].get("raw_entries_discovered", len(artifact["concepts"])) + len(entries) + len(terms),
                             "glossary_defined_terms": len(entries),
                             "concepts_with_ipcc_definitions": sum(bool(c.get("definition_source")) for c in result["concepts"]),
                             "concepts_with_descriptions": sum(bool(c.get("description")) for c in result["concepts"]),
                             "concepts_with_synonyms": sum(bool(c.get("synonyms")) for c in result["concepts"]),
                             "concepts_with_wikidata_ids": sum(bool(c.get("wikidata_id")) for c in result["concepts"])})
    (output_dir / "entries.json").write_text(json.dumps(entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    # Stable paths are used by provenance validation and rebuilds.
    (output_dir / "wordlist.csv").write_bytes(wordlist.read_bytes())
    (output_dir / "IPCC_AR6_SYR_Glossary.txt").write_bytes(prepared.read_bytes())
    return result
