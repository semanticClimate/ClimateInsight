"""Load and validate chatbot_manifest.json (semantic_corpus export contract).

Date: 2026-07-16 (system date of generation)
"""

import json
from pathlib import Path
from typing import Any, Dict

SUPPORTED_EXPORT_VERSION = "1.0"


class ManifestError(Exception):
    """Invalid or unreadable chatbot manifest."""


def load_manifest(path: Path) -> Dict[str, Any]:
    """Read chatbot_manifest.json and validate export_version 1.0 shape."""
    path = Path(path)
    if not path.is_file():
        raise ManifestError(f"Manifest file not found: {path}")

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ManifestError(f"Cannot read manifest {path}: {exc}") from exc

    if not isinstance(data, dict):
        raise ManifestError(f"Manifest must be a JSON object: {path}")

    version = data.get("export_version")
    if version != SUPPORTED_EXPORT_VERSION:
        raise ManifestError(
            f"Unsupported export_version {version!r}; "
            f"expected {SUPPORTED_EXPORT_VERSION!r}"
        )

    papers = data.get("papers")
    if not isinstance(papers, list):
        raise ManifestError(f"Manifest 'papers' must be a list: {path}")

    paper_count = data.get("paper_count")
    if paper_count != len(papers):
        raise ManifestError(
            f"paper_count {paper_count} does not match len(papers)={len(papers)}"
        )

    return data
