"""Resolve paper text from xml_path (preferred) or abstract.

Date: 2026-07-16 (system date of generation)
"""

from pathlib import Path
from typing import Any, Dict, Tuple

from ingest.manifest_ingest.jats_to_sections import jats_file_to_sections


class TextLoadError(Exception):
    """No usable text for a manifest paper record."""


def load_paper_text(paper: Dict[str, Any]) -> Tuple[str, str]:
    """Return (text, source) where source is 'xml' or 'abstract'."""
    xml_path_raw = (paper.get("xml_path") or "").strip()
    abstract = (paper.get("abstract") or "").strip()
    source_id = paper.get("source_id") or "unknown"

    if xml_path_raw:
        xml_path = Path(xml_path_raw)
        if xml_path.is_file():
            sections = jats_file_to_sections(xml_path)
            text = "\n\n".join(s.text for s in sections if s.text.strip())
            if text.strip():
                return text, "xml"

    if abstract:
        return abstract, "abstract"

    raise TextLoadError(
        f"No XML body or abstract text for paper {source_id!r}"
    )
