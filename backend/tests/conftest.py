"""Shared fixtures for manifest-ingest adapter tests.

Date: 2026-07-16 (system date of generation)
"""

import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).resolve().parent.joinpath("fixtures", "manifest")


@pytest.fixture
def manifest_fixture_dir() -> Path:
    return FIXTURES


@pytest.fixture
def sample_xml_path(manifest_fixture_dir: Path) -> Path:
    path = Path(manifest_fixture_dir, "sample_paper.xml")
    assert path.is_file(), f"Expected fixture XML at {path}"
    return path


@pytest.fixture
def chatbot_manifest_path(
    manifest_fixture_dir: Path,
    sample_xml_path: Path,
    tmp_path: Path,
) -> Path:
    """Copy manifest with xml_path rewritten to the real fixture XML."""
    raw = json.loads(
        Path(manifest_fixture_dir, "chatbot_manifest.json").read_text(encoding="utf-8")
    )
    assert raw["paper_count"] == len(raw["papers"]), (
        f"paper_count {raw['paper_count']} != len(papers) {len(raw['papers'])}"
    )
    raw["papers"][0]["xml_path"] = str(sample_xml_path)
    out = Path(tmp_path, "chatbot_manifest.json")
    out.write_text(json.dumps(raw, indent=2), encoding="utf-8")
    return out


@pytest.fixture
def chatbot_manifest(chatbot_manifest_path: Path) -> dict:
    return json.loads(chatbot_manifest_path.read_text(encoding="utf-8"))
