"""Tests for loading chatbot_manifest.json (export_version 1.0).

These tests define the adapter contract. They fail until
ingest.manifest_ingest.load_manifest is implemented.

Date: 2026-07-16 (system date of generation)
"""

from pathlib import Path

import pytest

pytest.importorskip(
    "ingest.manifest_ingest.load_manifest",
    reason="manifest adapter not implemented yet",
)

from ingest.manifest_ingest.load_manifest import (  # noqa: E402
    ManifestError,
    load_manifest,
)


def test_load_manifest_valid(chatbot_manifest_path: Path):
    data = load_manifest(chatbot_manifest_path)
    assert data["export_version"] == "1.0", (
        f"Expected export_version 1.0, got {data.get('export_version')!r}"
    )
    assert data["paper_count"] == 2, (
        f"Expected paper_count 2, got {data.get('paper_count')}"
    )
    assert len(data["papers"]) == 2, (
        f"Expected 2 papers, got {len(data.get('papers') or [])}"
    )
    first = data["papers"][0]
    assert first["source_id"] == "europe_pmc_PMC_FIXTURE_XML"
    assert Path(first["xml_path"]).is_file(), (
        f"xml_path must point to an existing file: {first['xml_path']}"
    )


def test_load_manifest_rejects_missing_file(tmp_path: Path):
    missing = Path(tmp_path, "no_such_manifest.json")
    with pytest.raises(ManifestError):
        load_manifest(missing)


def test_load_manifest_rejects_bad_version(tmp_path: Path, chatbot_manifest: dict):
    bad = dict(chatbot_manifest)
    bad["export_version"] = "9.9"
    path = Path(tmp_path, "bad_version.json")
    path.write_text(__import__("json").dumps(bad), encoding="utf-8")
    with pytest.raises(ManifestError):
        load_manifest(path)


def test_load_manifest_rejects_paper_count_mismatch(
    tmp_path: Path, chatbot_manifest: dict
):
    bad = dict(chatbot_manifest)
    bad["paper_count"] = 99
    path = Path(tmp_path, "bad_count.json")
    path.write_text(__import__("json").dumps(bad), encoding="utf-8")
    with pytest.raises(ManifestError):
        load_manifest(path)
