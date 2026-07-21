"""
pdf_to_docx.py
--------------
Step 1: Convert PDFs to Word (.docx) files.

Place this script in:  data/raw/ocean_heatwaves_2026/

Install:
    pip install pdf2docx pypdf

Run:
    # single file
    python pdf_to_docx.py PMC7653907.pdf

    # whole directory
    python pdf_to_docx.py .
"""

import sys
from pathlib import Path

try:
    from pdf2docx import Converter
except ImportError:
    sys.exit("Missing: run  pip install pdf2docx")

try:
    from pypdf import PdfReader
except ImportError:
    sys.exit("Missing: run  pip install pypdf")


def pdf_page_count(pdf_path: Path) -> int:
    reader = PdfReader(str(pdf_path))
    return len(reader.pages)


def convert(pdf_path: Path) -> Path:
    pdf_path = Path(pdf_path)
    docx_path = pdf_path.with_suffix(".docx")

    pdf_pages = pdf_page_count(pdf_path)
    print(f"\n── {pdf_path.name}  ({pdf_pages} pages in PDF)")
    print(f"   Converting → {docx_path.name} ...", end=" ", flush=True)

    cv = Converter(str(pdf_path))
    cv.convert(str(docx_path), start=0, end=None)
    cv.close()

    # Verify page count in the docx via python-docx
    try:
        from docx import Document
        from docx.oxml.ns import qn

        doc = Document(str(docx_path))
        # Count page breaks as a proxy for page count
        # (pdf2docx inserts explicit page breaks between pages)
        page_breaks = 0
        for para in doc.paragraphs:
            for run in para.runs:
                for br in run._element.findall(f".//{qn('w:br')}"):
                    if br.get(qn("w:type")) == "page":
                        page_breaks += 1

        docx_pages = page_breaks + 1  # pages = breaks + 1
        status = "✓ MATCH" if docx_pages == pdf_pages else f"⚠ MISMATCH (docx ~{docx_pages})"
        print(f"done  →  PDF: {pdf_pages}p  |  Word: ~{docx_pages}p  |  {status}")

    except ImportError:
        # python-docx not available, skip verification
        print(f"done  (install python-docx to verify page count)")

    return docx_path


def main():
    if len(sys.argv) < 2:
        print("Usage: python pdf_to_docx.py <file.pdf | directory>")
        sys.exit(1)

    target = Path(sys.argv[1])

    if target.is_dir():
        pdfs = sorted(target.glob("*.pdf"))
        if not pdfs:
            print(f"No .pdf files found in {target}")
            sys.exit(1)
        for pdf in pdfs:
            convert(pdf)
        print(f"\n✓ Done — {len(pdfs)} files converted.")

    elif target.is_file() and target.suffix.lower() == ".pdf":
        convert(target)

    else:
        print(f"Not a .pdf file or directory: {target}")
        sys.exit(1)


if __name__ == "__main__":
    main()