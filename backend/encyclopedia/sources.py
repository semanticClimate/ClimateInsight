"""Read the explicit local Encyclopedia source list without following links."""

from collections import defaultdict
from dataclasses import dataclass
import hashlib
from pathlib import Path
import re
import tomllib
from urllib.parse import quote

from lxml import html

from backend.ingest.xml_parser import parse_xml


POLICY = "approved_corpus_with_wikipedia_enrichment"


def configuration(root):
    return tomllib.loads((Path(root) / "config.toml").read_text(encoding="utf-8"))["encyclopedia"]


def approved_paths(root):
    root = Path(root).resolve()
    config = configuration(root)
    names = [config["source"], config["glossary"], *config["papers"]]
    if len(names) != len(set(names)):
        raise ValueError("The Encyclopedia source list contains duplicate files")
    paths = tuple((root / name).resolve() for name in names)
    if any(not path.is_relative_to(root / "data" / "raw") for path in paths):
        raise ValueError("Encyclopedia sources must be explicit files inside data/raw")
    if paths[0].suffix != ".html" or paths[1].suffix != ".html":
        raise ValueError("The report and glossary sources must be HTML files")
    if any(not re.fullmatch(r"PMC\d+\.xml", path.name) for path in paths[2:]) or not paths[2:]:
        raise ValueError("Each paper must be an explicitly listed PMC XML file")
    return paths


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def text(value):
    return " ".join(value.split())


@dataclass
class Document:
    source_file: str
    sha256: str
    title: str
    kind: str
    url: str
    paragraphs: list
    headings: list
    definitions: list
    keywords: list

    @property
    def content(self):
        return "\n\n".join([*self.headings, *(p["text"] for p in self.paragraphs)])

    def manifest(self):
        return {"source_file": self.source_file, "sha256": self.sha256,
                "title": self.title, "kind": self.kind, "url": self.url,
                "paragraphs": len(self.paragraphs)}


def load_document(path, root, kind):
    path, root = Path(path), Path(root)
    source_hash = digest(path)
    relative = path.relative_to(root).as_posix()
    paragraphs, headings, definitions, keywords = [], [], [], []
    if kind == "research_article":
        sections = parse_xml(path)
        if not sections:
            raise ValueError(f"No scientific text found in {relative}")
        title = sections[0].document_title
        url = "/paper/" + path.stem
        for section in sections:
            headings.append(section.section_title)
            for paragraph in section.text.split("\n\n"):
                if paragraph.strip():
                    paragraphs.append({"text": text(paragraph), "section": section.section_title,
                                       "html_id": "", "url": url})
        from bs4 import BeautifulSoup
        article = BeautifulSoup(path.read_bytes(), "xml")
        keywords = [text(node.get_text(" ", strip=True)) for node in article.select("kwd-group kwd")]
        headings.extend(keywords)
    else:
        document = html.document_fromstring(path.read_bytes())
        for node in document.xpath("//script|//style|//nav|//noscript|//*[@role='ami_encyclopedia']"):
            node.drop_tree()
        title = text(" ".join(document.xpath("//title/text()"))) or path.stem
        url = "/ipcc-glossary" if kind == "ipcc_glossary" else "/ipcc-reference"
        if kind == "ipcc_glossary":
            for node in document.xpath("//section[contains(concat(' ', normalize-space(@class), ' '), ' glossary-entry ')]"):
                term = node.get("data-term") or text(" ".join(node.xpath("./h2//text()")))
                body = [text(p.text_content()) for p in node.xpath("./p[@class='definition']")]
                if not term or not body or not node.get("id"):
                    raise ValueError("The glossary HTML has an incomplete term/definition entry")
                page = int(node.get("data-page", "0"))
                entry = {"term": term, "definition": "\n\n".join(body), "html_id": node.get("id"),
                         "page": page, "pages": [page]}
                definitions.append(entry)
                headings.append(term)
                paragraphs.append({"text": entry["definition"], "section": term,
                                   "html_id": entry["html_id"], "url": url + "#" + quote(entry["html_id"])})
            if not definitions:
                raise ValueError("No term/definition entries found in the approved glossary HTML")
        else:
            for node in document.xpath("//*[contains(@class, '_idFootnotes')]|//*[@class='Caption']"):
                node.drop_tree()
            occurrences = defaultdict(int)
            section = ""
            for node in document.xpath("//h1|//h2|//h3|//h4|//p"):
                value = text(node.text_content())
                if node.tag != "p":
                    section = value
                    headings.append(value)
                    continue
                if not value or set(node.get("class", "").lower().split()) & {"footnote", "reference", "caption"}:
                    continue
                anchor = node.get("id", "")
                if anchor:
                    occurrences[anchor] += 1
                    if occurrences[anchor] > 1:
                        anchor = "ci-source-" + hashlib.sha256(f"{anchor}\0{occurrences[anchor]}".encode()).hexdigest()[:16]
                paragraphs.append({"text": value, "section": section, "html_id": anchor,
                                   "url": url + ("#" + quote(anchor) if anchor else "")})
    if not paragraphs:
        raise ValueError(f"No readable source paragraphs found in {relative}")
    return Document(relative, source_hash, title, kind, url, paragraphs, headings, definitions, keywords)


def load_documents(root):
    return [load_document(path, Path(root).resolve(),
                          "ipcc_report" if index == 0 else "ipcc_glossary" if index == 1 else "research_article")
            for index, path in enumerate(approved_paths(root))]
