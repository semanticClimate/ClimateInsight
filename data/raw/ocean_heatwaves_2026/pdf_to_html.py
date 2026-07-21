"""
pdf_to_html.py  (v2 — PDF → Word → HTML pipeline)
---------------------------------------------------
Place this script in:  data/raw/ocean_heatwaves_2026/

Install dependencies first:
    pip install pdf2docx mammoth

Run:
    # single PDF
    python pdf_to_html.py PMC7653907.pdf

    # whole directory
    python pdf_to_html.py .

What it does:
  1. Converts each PDF → .docx  (saved alongside the PDF so you can inspect it)
  2. Converts each .docx → HTML  via mammoth (preserves headings, bold, tables)
  3. Wraps the HTML in the project's CSS styling (header banner, abstract box, etc.)
  4. Outputs <pmcid>.html in the same folder

After confirming the output looks good, you can delete the .docx files manually.
"""

from __future__ import annotations

import re
import sys
import tempfile
from pathlib import Path

# ── Dependency checks ─────────────────────────────────────────────────────────
try:
    from pdf2docx import Converter as PDFConverter
except ImportError:
    sys.exit("Missing dependency: run  pip install pdf2docx")

try:
    import mammoth
except ImportError:
    sys.exit("Missing dependency: run  pip install mammoth")


# ── Sections to strip from the final HTML ────────────────────────────────────
# mammoth gives us headings as <h1>/<h2> etc; we match their text content.
SKIP_HEADINGS = {
    "references", "bibliography", "acknowledgements", "acknowledgments",
    "supplementary information", "supplementary material",
    "supplementary materials", "competing interests", "data availability",
    "code availability", "author contributions", "peer review",
    "peer review information", "footnotes", "conflict of interest",
    "ethics statement", "financial support", "funding",
    "list of abbreviations", "abbreviations", "additional information",
    "publisher's note", "open access",
}


# ── CSS ───────────────────────────────────────────────────────────────────────
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

  /* ── Tables ── */
  .paper-body table {
    width: 100%;
    border-collapse: collapse;
    margin: 18px 0;
    font-size: 0.85rem;
  }
  .paper-body th {
    background: var(--blue);
    color: #fff;
    padding: 8px 12px;
    text-align: left;
    font-weight: 600;
  }
  .paper-body td {
    padding: 7px 12px;
    border-bottom: 1px solid var(--border);
    vertical-align: top;
  }
  .paper-body tr:nth-child(even) td { background: #F0F7F4; }

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


# ── Slug helper ───────────────────────────────────────────────────────────────

def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text[:60].lower()).strip("-") or "sec"


# ── Step 1: PDF → docx ────────────────────────────────────────────────────────

def pdf_to_docx(pdf_path: Path, docx_path: Path) -> None:
    """Convert PDF to Word using pdf2docx."""
    print(f"  [1/3] PDF → Word ...", end=" ", flush=True)
    cv = PDFConverter(str(pdf_path))
    cv.convert(str(docx_path), start=0, end=None)
    cv.close()
    print("done")


# ── Step 2: docx → raw HTML via mammoth ──────────────────────────────────────

def docx_to_raw_html(docx_path: Path) -> str:
    """Convert Word doc to HTML using mammoth."""
    print(f"  [2/3] Word → HTML ...", end=" ", flush=True)

    # mammoth style map: map Word heading styles to h2/h3/h4
    style_map = """
        p[style-name='Heading 1'] => h2:fresh
        p[style-name='Heading 2'] => h3:fresh
        p[style-name='Heading 3'] => h4:fresh
        p[style-name='Heading 4'] => h4:fresh
        p[style-name='Title']     => h1:fresh
    """

    with open(docx_path, "rb") as f:
        result = mammoth.convert_to_html(f, style_map=style_map)

    if result.messages:
        for msg in result.messages[:5]:  # show first 5 warnings only
            print(f"\n    [mammoth] {msg}")

    print("done")
    return result.value


# ── Step 3: Post-process HTML ─────────────────────────────────────────────────

def _extract_meta_from_html(html: str, pmcid: str) -> dict:
    """
    Pull title, DOI, year from the raw mammoth HTML.
    The first <h1> or <h2> is usually the paper title.
    """
    meta = {"title": "", "doi": "", "year": "", "pmcid": pmcid}

    # Title: first h1 or h2
    m = re.search(r"<h[12][^>]*>(.*?)</h[12]>", html, re.IGNORECASE | re.DOTALL)
    if m:
        meta["title"] = re.sub(r"<[^>]+>", "", m.group(1)).strip()

    # DOI
    m = re.search(r"10\.\d{4,}/\S+", html)
    if m:
        meta["doi"] = m.group(0).rstrip(".,;)<>\"'")

    # Year
    m = re.search(r"\b(19[9]\d|20[0-2]\d)\b", html)
    if m:
        meta["year"] = m.group(1)

    return meta


def _should_skip_section(heading_text: str) -> bool:
    lower = re.sub(r"<[^>]+>", "", heading_text).strip().lower().rstrip(".:")
    return lower in SKIP_HEADINGS


def _post_process(raw_html: str, pmcid: str) -> tuple[str, str, dict]:
    """
    Parse mammoth's flat HTML and:
      - Extract metadata
      - Pull the abstract into its own box
      - Add id slugs to headings
      - Strip unwanted sections (references, acknowledgements, etc.)
      - Return (abstract_html, body_html, meta)
    """
    meta = _extract_meta_from_html(raw_html, pmcid)

    # Split into blocks on heading boundaries
    # We'll walk tag by tag using a simple state machine
    blocks = re.split(r"(?=<h[1-6][\s>])", raw_html)

    abstract_html = ""
    body_parts: list[str] = []
    skipping = False
    first_h1_seen = False

    for block in blocks:
        block = block.strip()
        if not block:
            continue

        # Check if this block starts with a heading
        heading_match = re.match(r"<(h[1-6])[^>]*>(.*?)</h[1-6]>", block, re.IGNORECASE | re.DOTALL)

        if heading_match:
            tag = heading_match.group(1).lower()
            heading_inner = heading_match.group(2)
            heading_text = re.sub(r"<[^>]+>", "", heading_inner).strip()
            heading_lower = heading_text.lower().rstrip(".:")

            # Skip the first h1 (it's the paper title — already in our header)
            if tag == "h1" and not first_h1_seen:
                first_h1_seen = True
                # Get content after this h1 (authors, affiliations — skip it)
                skipping = False
                continue

            # Should we skip this section entirely?
            if _should_skip_section(heading_text):
                skipping = True
                continue

            skipping = False

            # Abstract gets special treatment
            if heading_lower == "abstract":
                # Grab the paragraph content after the heading
                after_heading = block[heading_match.end():].strip()
                # Strip any nested headings (some papers have abstract subsections)
                after_heading = re.sub(r"<h[1-6][^>]*>.*?</h[1-6]>", "", after_heading, flags=re.DOTALL)
                if after_heading:
                    abstract_html = (
                        f'<div class="abstract-box"><h2>Abstract</h2>'
                        f'{after_heading}'
                        f'</div>'
                    )
                continue

            # Normal section: add id slug to heading
            slug = _slug(heading_text)
            after_heading = block[heading_match.end():].strip()

            body_parts.append(f'<{tag} id="{slug}">{heading_inner}</{tag}>')
            if after_heading:
                body_parts.append(after_heading)

        else:
            # Plain content block (no leading heading)
            if not skipping and not first_h1_seen is False:
                body_parts.append(block)

    body_html = '<div class="paper-body">\n' + "\n".join(body_parts) + "\n</div>"
    return abstract_html, body_html, meta


# ── Assemble final page ───────────────────────────────────────────────────────

def _assemble(abstract_html: str, body_html: str, meta: dict) -> str:
    title_escaped = meta["title"].replace("<", "&lt;").replace(">", "&gt;") or meta["pmcid"]
    pmcid = meta["pmcid"]

    meta_chips: list[str] = []
    if meta["year"]:
        meta_chips.append(f'<span>{meta["year"]}</span>')
    if meta["doi"]:
        doi = meta["doi"].replace("<", "&lt;").replace(">", "&gt;")
        meta_chips.append(
            f'<a href="https://doi.org/{doi}" target="_blank">DOI: {doi}</a>'
        )
    if pmcid:
        meta_chips.append(
            f'<a href="https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{pmcid}/" target="_blank">PMC{pmcid}</a>'
        )
    meta_bar = f'<div class="paper-meta">{"".join(meta_chips)}</div>' if meta_chips else ""

    header_html = f"""<div class="paper-header">
  <h1>{title_escaped}</h1>
  {meta_bar}
</div>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title_escaped}</title>
  {STYLE}
</head>
<body>
{header_html}
{abstract_html}
{body_html}
</body>
</html>"""


# ── Main converter ────────────────────────────────────────────────────────────

def convert(pdf_path: Path, out_dir: Path) -> Path:
    pdf_path = Path(pdf_path)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    stem = pdf_path.stem                        # e.g. "PMC7653907"
    pmcid = re.sub(r"^PMC", "", stem)           # e.g. "7653907"

    # .docx saved next to the PDF so you can inspect/delete it
    docx_path = pdf_path.parent / f"{stem}.docx"
    out_path  = out_dir / f"{pmcid}.html"

    print(f"\n── {pdf_path.name} ──")

    # Step 1: PDF → docx
    pdf_to_docx(pdf_path, docx_path)

    # Step 2: docx → raw HTML
    raw_html = docx_to_raw_html(docx_path)

    # Step 3: post-process + wrap
    print(f"  [3/3] Post-processing ...", end=" ", flush=True)
    abstract_html, body_html, meta = _post_process(raw_html, pmcid)
    page = _assemble(abstract_html, body_html, meta)
    out_path.write_text(page, encoding="utf-8")
    print("done")

    print(f"  ✓  {out_path.name}  (Word file: {docx_path.name})")
    return out_path


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print("Usage: python pdf_to_html.py <file.pdf | directory>  [output_dir]")
        sys.exit(1)

    target = Path(sys.argv[1])

    # Default output: same folder as this script
    default_out = Path(__file__).resolve().parent
    out_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else default_out

    if target.is_dir():
        pdfs = sorted(target.glob("*.pdf"))
        if not pdfs:
            print(f"No .pdf files found in {target}")
            sys.exit(1)
        for pdf in pdfs:
            convert(pdf, out_dir)
        print(f"\n✓ Done — {len(pdfs)} files written to {out_dir}/")

    elif target.is_file() and target.suffix.lower() == ".pdf":
        convert(target, out_dir)

    else:
        print(f"Not a .pdf file or directory: {target}")
        sys.exit(1)


if __name__ == "__main__":
    main()