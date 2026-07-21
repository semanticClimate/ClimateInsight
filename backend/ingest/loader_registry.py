"""
loader_registry.py
------------------
Central registry mapping file extensions to their parser functions.

Usage
-----
    from ingest.loader_registry import get_loader, SUPPORTED_EXTENSIONS

    loader = get_loader(path)   # returns the right parse_* function
    sections = loader(path)     # returns list[Section]

Extending
---------
To add a new document type (PDF, Markdown, plain text, etc.):

    1. Implement a parser function with the signature:
           def parse_xyz(path: Path) -> list[Section]: ...
       Make sure every returned Section is fully populated (source_path,
       document_title, source_type, doi, pmcid, section_hierarchy).

    2. Register it here:
           from .xyz_parser import parse_xyz
           LOADERS[".xyz"] = parse_xyz

That is the ONLY change required — no changes to chunker, indexer, or
ingest.py entry point.
"""

from pathlib import Path
from typing import Callable, Dict, List

from .models import Section
from .parser import parse_html
from .xml_parser import parse_xml

# ─── Registry ─────────────────────────────────────────────────────────────────

LoaderFn = Callable[[Path], List[Section]]

LOADERS: Dict[str, LoaderFn] = {
    ".html": parse_html,
    ".htm": parse_html,
    ".xml": parse_xml,
    # Future:
    # ".md":  parse_markdown,
    # ".txt": parse_plaintext,
    # ".pdf": parse_pdf,
}

SUPPORTED_EXTENSIONS: frozenset = frozenset(LOADERS.keys())


# ─── Public helpers ───────────────────────────────────────────────────────────


def get_loader(path: Path) -> LoaderFn:
    """
    Return the appropriate parser function for *path* based on its suffix.

    Raises
    ------
    ValueError
        If the file extension is not registered in LOADERS.
    """
    ext = path.suffix.lower()
    if ext not in LOADERS:
        supported = ", ".join(sorted(SUPPORTED_EXTENSIONS))
        raise ValueError(
            f"No loader registered for '{ext}' (file: {path.name}). "
            f"Supported extensions: {supported}"
        )
    return LOADERS[ext]


def discover_documents(root: Path) -> List[Path]:
    """
    Recursively discover all supported documents under *root*.

    Returns a sorted list so processing order is deterministic and
    newly added files are automatically included on the next run.
    """
    root = Path(root)
    found: List[Path] = []
    for ext in SUPPORTED_EXTENSIONS:
        found.extend(root.rglob(f"*{ext}"))
    return sorted(set(found))
