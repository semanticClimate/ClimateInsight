"""
xml_to_html.py
--------------
Convert JATS XML research articles to styled, readable HTML files
that can be served by the Flask backend and rendered in the source iframe —
exactly like the IPCC HTML report is today.

Run once per XML file (or for the whole ocean_heatwaves_2026 directory):

    # single file
    python xml_to_html.py data/raw/ocean_heatwaves_2026/PMC7653907.xml

    # whole directory  (outputs to data/rendered/ by default)
    python xml_to_html.py data/raw/ocean_heatwaves_2026/

Output: data/rendered/<pmcid>.html  (one file per paper)

The Flask backend must then serve these files.  Add ONE route to app.py:

    @app.get("/paper/<pmcid>")
    def serve_paper(pmcid):
        from flask import send_from_directory
        rendered = Path(__file__).parent.parent / "data" / "rendered"
        return send_from_directory(rendered, f"{pmcid}.html")

Then update window.SOURCE_DOCS in index.html to set each paper's url to:
    `${_base}/paper/7653907`  etc.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup, Tag

# ── Sections we skip entirely ──────────────────────────────────────────────────
SKIP_SEC_TYPES = {
    "ref-list", "references", "bibliography", "ack", "acknowledgments",
    "acknowledgements", "fn-group", "footnotes", "supplementary-materials",
    "supplementary-material", "competing-interests", "author-notes",
    "associated-data", "data-availability-statement",
}

SKIP_HEADINGS = {
    "references", "bibliography", "acknowledgements", "acknowledgments",
    "supplementary information", "supplementary material",
    "supplementary materials", "competing interests", "data availability",
    "code availability", "author contributions", "peer review",
    "peer review information", "footnotes",
}

# Inline tags to strip (citation superscripts, etc.)
STRIP_INLINE = {"xref", "sup", "sub", "fn", "label", "inline-formula",
                "disp-formula", "tex-math", "mml:math", "graphic"}


# ── CSS embedded in every output file ─────────────────────────────────────────
STYLE = """
<style>
  :root {
    --blue:   #1B4F9B;
    --green:  #16A34A;
    --orange: #F59E0B;
    --bg:     #F8FAFB;
    --border: #D1E5D9;
    --text:   #111827;
    --muted:  #6B7280;
    --font:   'Jost', 'Segoe UI', Arial, sans-serif;
  }

  * { box-sizing: border-box; margin: 0; padding: 0; }

  body {
    font-family: var(--font);
    background: var(--bg);
    color: var(--text);
    font-size: 15px;
    line-height: 1.75;
    padding: 0 0 60px;
  }

  /* ── Header banner ── */
  .paper-header {
    background: var(--blue);
    color: #fff;
    padding: 28px 32px 22px;
    border-bottom: 4px solid var(--orange);
  }
  .paper-header .journal {
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    opacity: 0.75;
    margin-bottom: 6px;
  }
  .paper-header h1 {
    font-size: 1.25rem;
    font-weight: 700;
    line-height: 1.35;
    margin-bottom: 10px;
  }
  .paper-header .authors {
    font-size: 0.82rem;
    opacity: 0.85;
    margin-bottom: 8px;
  }
  .paper-meta {
    display: flex;
    gap: 14px;
    flex-wrap: wrap;
    margin-top: 10px;
  }
  .paper-meta a, .paper-meta span {
    font-size: 0.78rem;
    background: rgba(255,255,255,0.15);
    border-radius: 4px;
    padding: 3px 9px;
    color: #fff;
    text-decoration: none;
    font-weight: 600;
  }
  .paper-meta a:hover { background: rgba(255,255,255,0.25); }

  /* ── Abstract box ── */
  .abstract-box {
    margin: 22px 32px;
    background: #EEF6F1;
    border-left: 4px solid var(--green);
    border-radius: 6px;
    padding: 16px 20px;
  }
  .abstract-box h2 {
    font-size: 0.75rem;
    font-weight: 700;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: var(--green);
    margin-bottom: 8px;
  }
  .abstract-box p {
    font-size: 0.9rem;
    color: #1F3A2A;
    line-height: 1.7;
  }

  /* ── Body content ── */
  .paper-body {
    padding: 0 32px;
  }

  /* ── Section headings ── */
  .paper-body h2 {
    font-size: 1.05rem;
    font-weight: 700;
    color: var(--blue);
    margin: 28px 0 10px;
    padding-bottom: 5px;
    border-bottom: 2px solid var(--border);
  }
  .paper-body h3 {
    font-size: 0.95rem;
    font-weight: 600;
    color: #1F3A2A;
    margin: 20px 0 8px;
  }
  .paper-body h4 {
    font-size: 0.88rem;
    font-weight: 600;
    color: var(--muted);
    margin: 14px 0 6px;
  }

  /* ── Paragraphs ── */
  .paper-body p {
    margin-bottom: 14px;
    font-size: 0.92rem;
  }

  /* ── Lists ── */
  .paper-body ul, .paper-body ol {
    margin: 10px 0 14px 22px;
    font-size: 0.92rem;
  }
  .paper-body li { margin-bottom: 5px; }

  /* ── Section anchor highlight target ── */
  :target {
    background: #FFFBEB;
    outline: 2px solid var(--orange);
    border-radius: 4px;
    padding: 4px 6px;
  }

  /* ── Scrollbar ── */
  ::-webkit-scrollbar { width: 5px; }
  ::-webkit-scrollbar-track { background: transparent; }
  ::-webkit-scrollbar-thumb { background: #CBD5E1; border-radius: 4px; }
</style>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Jost:wght@400;600;700&display=swap" rel="stylesheet">
"""


# ── Helpers ───────────────────────────────────────────────────────────────────

def _slug(text: str, fallback: str = "sec") -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text[:60].lower()).strip("-")
    return s or fallback


def _clean_inline(tag: Tag) -> str:
    """Return readable prose text from a tag, stripping citation noise."""
    clone = BeautifulSoup(str(tag), "xml").find()
    if clone is None:
        return ""
    for noise in clone.find_all(list(STRIP_INLINE)):
        noise.decompose()
    text = clone.get_text(separator=" ", strip=True)
    return re.sub(r"\s{2,}", " ", text).strip()


def _tag(name: str, content: str, **attrs) -> str:
    attr_str = "".join(f' {k}="{v}"' for k, v in attrs.items())
    return f"<{name}{attr_str}>{content}</{name}>"


# ── Metadata extraction ────────────────────────────────────────────────────────

def _extract_metadata(soup: BeautifulSoup) -> dict:
    meta = {"title": "", "doi": "", "pmcid": "",
            "journal": "", "year": "", "authors": []}

    ameta = soup.find("article-meta")
    if not ameta:
        return meta

    t = ameta.find("article-title")
    if t:
        meta["title"] = t.get_text(" ", strip=True)

    for id_tag in ameta.find_all("article-id"):
        pt = id_tag.get("pub-id-type", "")
        v = id_tag.get_text(strip=True)
        if pt == "doi":
            meta["doi"] = v
        elif pt in ("pmcid", "pmc", "pmcaid", "pmcaiid") and not meta["pmcid"]:
            meta["pmcid"] = v.replace("PMC", "")

    jmeta = soup.find("journal-meta")
    if jmeta:
        jt = jmeta.find("journal-title")
        if jt:
            meta["journal"] = jt.get_text(strip=True)

    pub = ameta.find("pub-date")
    if pub:
        y = pub.find("year")
        if y:
            meta["year"] = y.get_text(strip=True)

    for contrib in ameta.find_all("contrib", {"contrib-type": "author"}):
        name = contrib.find("name")
        if name:
            sn = name.find("surname")
            gn = name.find("given-names")
            if sn:
                parts = [sn.get_text(strip=True)]
                if gn:
                    parts.append(gn.get_text(strip=True)[0] + ".")
                meta["authors"].append(" ".join(parts))

    return meta


# ── Abstract ──────────────────────────────────────────────────────────────────

def _render_abstract(soup: BeautifulSoup) -> str:
    for abstract in soup.find_all("abstract"):
        if abstract.get("abstract-type") in {"web-summary", "graphical"}:
            continue
        paras = [_clean_inline(p) for p in abstract.find_all("p", recursive=True)]
        paras = [p for p in paras if p]
        if not paras:
            continue
        inner = "\n".join(_tag("p", p) for p in paras)
        return f'<div class="abstract-box"><h2>Abstract</h2>{inner}</div>'
    return ""


# ── Body sections ─────────────────────────────────────────────────────────────

def _should_skip(sec: Tag) -> bool:
    sec_type = (sec.get("sec-type") or "").lower()
    if sec_type in SKIP_SEC_TYPES:
        return True
    title_el = sec.find("title", recursive=False)
    if title_el:
        heading = title_el.get_text(" ", strip=True).lower()
        if heading in SKIP_HEADINGS:
            return True
    return False


def _walk_sec(sec: Tag, depth: int = 2) -> str:
    """Recursively render a <sec> element to HTML."""
    if _should_skip(sec):
        return ""

    html_parts: list[str] = []

    # Heading
    title_el = sec.find("title", recursive=False)
    heading_text = title_el.get_text(" ", strip=True) if title_el else ""
    sec_id = sec.get("id") or _slug(heading_text, "sec")
    h_level = min(depth, 4)
    if heading_text:
        html_parts.append(f'<h{h_level} id="{sec_id}">{heading_text}</h{h_level}>')

    # Direct children (paragraphs, lists — not nested <sec>)
    for child in sec.children:
        if not isinstance(child, Tag):
            continue
        if child.name == "sec":
            continue
        if child.name in {"fig", "table-wrap", "supplementary-material",
                          "media", "disp-formula", "code", "title", "label"}:
            continue
        if child.name == "p":
            text = _clean_inline(child)
            if len(text) >= 30:
                html_parts.append(_tag("p", text))
        elif child.name == "list":
            items = [_clean_inline(li) for li in child.find_all("list-item")]
            items = [i for i in items if i]
            if items:
                lis = "".join(_tag("li", i) for i in items)
                list_tag = "ol" if child.get("list-type") == "order" else "ul"
                html_parts.append(_tag(list_tag, lis))

    # Recurse into child sections
    for child_sec in sec.find_all("sec", recursive=False):
        html_parts.append(_walk_sec(child_sec, depth + 1))

    return "\n".join(html_parts)


# ── Main converter ────────────────────────────────────────────────────────────

def convert(xml_path: Path, out_dir: Path) -> Path:
    xml_path = Path(xml_path)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Converting {xml_path.name} ...", end=" ", flush=True)
    raw = xml_path.read_text(encoding="utf-8", errors="ignore")
    soup = BeautifulSoup(raw, "xml")

    meta = _extract_metadata(soup)
    pmcid = meta["pmcid"] or xml_path.stem

    # ── Header ───────────────────────────────────────────────────────────────
    journal_line = f'<div class="journal">{meta["journal"]}</div>' if meta["journal"] else ""
    authors_str = ", ".join(meta["authors"][:6])
    if len(meta["authors"]) > 6:
        authors_str += " et al."
    authors_line = f'<div class="authors">{authors_str}</div>' if authors_str else ""

    meta_chips = []
    if meta["year"]:
        meta_chips.append(f'<span>{meta["year"]}</span>')
    if meta["doi"]:
        meta_chips.append(
            f'<a href="https://doi.org/{meta["doi"]}" target="_blank">DOI: {meta["doi"]}</a>'
        )
    if pmcid:
        meta_chips.append(
            f'<a href="https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{pmcid}/" target="_blank">PMC{pmcid}</a>'
        )
    meta_bar = f'<div class="paper-meta">{"".join(meta_chips)}</div>' if meta_chips else ""

    header_html = f"""
<div class="paper-header">
  {journal_line}
  <h1>{meta["title"] or xml_path.stem}</h1>
  {authors_line}
  {meta_bar}
</div>"""

    # ── Abstract ──────────────────────────────────────────────────────────────
    abstract_html = _render_abstract(soup)

    # ── Body ──────────────────────────────────────────────────────────────────
    body_parts: list[str] = []
    body = soup.find("body")
    if body:
        for sec in body.find_all("sec", recursive=False):
            body_parts.append(_walk_sec(sec, depth=2))

    body_html = f'<div class="paper-body">\n{"".join(body_parts)}\n</div>'

    # ── Assemble ──────────────────────────────────────────────────────────────
    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{meta["title"] or pmcid}</title>
  {STYLE}
</head>
<body>
{header_html}
{abstract_html}
{body_html}
</body>
</html>"""

    out_path = out_dir / f"{pmcid}.html"
    out_path.write_text(page, encoding="utf-8")
    print(f"→ {out_path.name}")
    return out_path


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print("Usage: python xml_to_html.py <file.xml | directory>  [output_dir]")
        sys.exit(1)

    target = Path(sys.argv[1])
    # Default output: project_root/data/rendered/
    default_out = Path(__file__).resolve().parent.parent / "data" / "rendered"
    out_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else default_out

    if target.is_dir():
        xmls = sorted(target.glob("*.xml"))
        if not xmls:
            print(f"No .xml files found in {target}")
            sys.exit(1)
        for xml in xmls:
            convert(xml, out_dir)
        print(f"\nDone — {len(xmls)} files written to {out_dir}/")
    elif target.is_file() and target.suffix == ".xml":
        convert(target, out_dir)
    else:
        print(f"Not a .xml file or directory: {target}")
        sys.exit(1)


if __name__ == "__main__":
    main()