"""Build-boundary regressions; real entry export with a fake expensive extractor."""

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import build_ipcc_encyclopedia as builder
import knowledge_graph as kg


def test_report_build_exports_wikipedia_identity_and_retains_unresolved_model_terms(tmp_path, monkeypatch):
    import ipcc_encyclopedia_pipeline as report

    source = tmp_path / "data/raw/ipcc_reference.html"
    source.parent.mkdir(parents=True)
    source.write_text('<html><body><p id="p1">Green infrastructure, carbon tax and '
                      'greenhouse gas emissions.</p><p id="p2">Novel report phrase.</p></body></html>',
                      encoding="utf-8")
    original = source.read_bytes()
    cases = [("green infrastructure", "Green_infrastructure", "Q3427027"),
             ("carbon tax", "Carbon_tax", "Q288401"),
             ("greenhouse gas emissions", "Greenhouse_gas_emissions", "Q106358009")]
    entries = [{"term": term, "search_term": term,
                "wikipedia_url": "https://en.wikipedia.org/wiki/" + slug,
                "wikidata_id": qid, "description_html": "<p>A Wikipedia definition.</p>"}
               for term, slug, qid in cases]
    entries.append({"term": "Novel report phrase", "content_note": "No description: no Wikipedia article",
                    "description_html": "<p>No description: no Wikipedia article</p>"})

    def build(source_path, output_dir, **options):
        assert source_path == source
        output_dir.mkdir(exist_ok=True)
        paths = {"html": output_dir / "entries.html", "wordlist": output_dir / "wordlist.csv",
                 "text": output_dir / "report.txt"}
        for path in paths.values():
            path.write_text("generated", encoding="utf-8")
        return SimpleNamespace(entries=entries), paths

    monkeypatch.setattr(report, "build_report_encyclopedia", build)
    monkeypatch.setattr(builder, "ROOT", tmp_path)
    monkeypatch.setattr(kg, "get_collection", lambda: pytest.fail("Build opened ChromaDB"))
    result = builder.build(source)
    concepts = {r["canonical_name"]: r for r in result["concepts"]}
    for term, slug, qid in cases:
        title = slug.replace("_", " ")
        assert concepts[title]["wikidata_id"] == qid
        assert concepts[title]["description"] == "A Wikipedia definition."
        assert term in [title.casefold(), *concepts[title]["synonyms"]]
    unresolved = concepts["Novel report phrase"]
    assert unresolved["description"] is None and unresolved["wikipedia_url"] is None
    assert result["provenance"]["source_sha256"] == hashlib.sha256(original).hexdigest()
    assert result["provenance"]["source_file"] == "data/raw/ipcc_reference.html"
    saved = json.loads((tmp_path / "backend/data/generated/encyclopedia_concepts.json").read_text())
    assert saved == result
    glossary = (tmp_path / "encyclopedia/generated/ipcc_encyclopedia.html").read_text(encoding="utf-8")
    assert 'role="ami_entry"' in glossary and '/ipcc-reference#p1' in glossary
    assert source.read_bytes() == original


def test_failed_rebuild_retains_previous_vocabulary(tmp_path, monkeypatch):
    import ipcc_encyclopedia_pipeline as report

    source = tmp_path / "source.html"
    source.write_text("<p>Source report.</p>")
    artifact = tmp_path / "backend/data/generated/encyclopedia_concepts.json"
    artifact.parent.mkdir(parents=True)
    artifact.write_text("previous build")

    def fail(*args, **kwargs):
        raise RuntimeError("Extractor failed")

    monkeypatch.setattr(builder, "ROOT", tmp_path)
    monkeypatch.setattr(report, "build_report_encyclopedia", fail)
    with pytest.raises(RuntimeError, match="Extractor failed"):
        builder.build(source)
    assert artifact.read_text() == "previous build"
