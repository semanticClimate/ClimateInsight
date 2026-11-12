"""Build-boundary regressions; real entry export with a fake expensive extractor."""

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import backend.encyclopedia.build as builder
import backend.knowledge_graph.engine as kg


def test_report_build_exports_wikipedia_identity_and_retains_unresolved_model_terms(tmp_path, monkeypatch):
    import backend.encyclopedia.pipeline as report

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
    monkeypatch.setattr(builder, "version", lambda *a: "1.0.6")
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
    saved = json.loads((tmp_path / "backend/generated_artifacts/encyclopedia_concepts.json").read_text())
    assert saved == result
    glossary = (tmp_path / "encyclopedia_assets/generated/ipcc_encyclopedia.html").read_text(encoding="utf-8")
    assert 'role="ami_entry"' in glossary and '/ipcc-reference#p1' in glossary
    assert source.read_bytes() == original


def test_failed_rebuild_retains_previous_vocabulary(tmp_path, monkeypatch):
    import backend.encyclopedia.pipeline as report

    source = tmp_path / "source.html"
    source.write_text("<p>Source report.</p>")
    artifact = tmp_path / "backend/generated_artifacts/encyclopedia_concepts.json"
    artifact.parent.mkdir(parents=True)
    artifact.write_text("previous build")

    def fail(*args, **kwargs):
        raise RuntimeError("Extractor failed")

    monkeypatch.setattr(builder, "ROOT", tmp_path)
    monkeypatch.setattr(report, "build_report_encyclopedia", fail)
    with pytest.raises(RuntimeError, match="Extractor failed"):
        builder.build(source)
    assert artifact.read_text() == "previous build"


def test_enrich_existing_reuses_selected_model_terms_and_extraction_provenance(tmp_path, monkeypatch):
    from encyclopedia.pipeline import query_to_encyclopedia as pipeline

    source = tmp_path / "data/raw/ipcc_reference.html"
    source.parent.mkdir(parents=True)
    source.write_text('<p id="p1">Climate change and an unresolved report phrase.</p>', encoding="utf-8")
    output = tmp_path / "encyclopedia_assets/generated"
    output.mkdir(parents=True)
    wordlist = b'term,count,selected\nclimate change,8,Yes\nunresolved report phrase,2,Yes\nnot selected,1,No\n'
    (output / "wordlist.csv").write_bytes(wordlist)
    (output / "ipcc_reference.txt").write_text("Prepared extraction input", encoding="utf-8")
    previous = {
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "extractor": "txt2phrases", "extractor_version": "1.0.6", "model": "original-model",
        "top_n": 500, "max_terms": 300, "min_count": 2, "selected_keyphrases": 2,
        "generated_at": "2026-11-03T18:16:58+00:00", "wikipedia_requested": False,
    }
    artifact = tmp_path / "backend/generated_artifacts/encyclopedia_concepts.json"
    artifact.parent.mkdir(parents=True)
    artifact.write_text(json.dumps({"provenance": previous}), encoding="utf-8")

    def create(terms, title, target, **options):
        assert terms == ["climate change", "unresolved report phrase"]
        assert options == {"add_wikipedia": True}
        return SimpleNamespace(entries=[{
            "term": terms[0], "wikipedia_url": "https://en.wikipedia.org/wiki/Climate_change",
            "wikidata_id": "Q125928", "description_html": "<p>A real article description.</p>",
        }, {"term": terms[1], "content_note": "No description: no Wikipedia article"}])

    monkeypatch.setattr(pipeline, "create_encyclopedia_from_terms", create)
    monkeypatch.setattr(builder, "ROOT", tmp_path)
    monkeypatch.setattr(builder, "version", lambda *a: pytest.fail("Extractor dependency was loaded"))
    monkeypatch.setattr(kg, "get_collection", lambda: pytest.fail("Enrichment opened ChromaDB"))
    result = builder.build(source, enrich_existing=True)
    provenance = result["provenance"]
    assert provenance["wikipedia_requested"] is True
    assert provenance["extractor_version"] == previous["extractor_version"]
    assert provenance["model"] == "original-model"
    assert provenance["extracted_at"] == previous["generated_at"]
    assert provenance["wordlist_sha256"] == hashlib.sha256(wordlist).hexdigest()
    assert (output / "wordlist.csv").read_bytes() == wordlist
    concepts = {item["canonical_name"]: item for item in result["concepts"]}
    assert concepts["Climate change"]["description"] == "A real article description."
    assert concepts["Climate change"]["wikidata_id"] == "Q125928"
    assert concepts["unresolved report phrase"]["wikipedia_url"] is None


def test_enrich_existing_rejects_a_stale_source_before_wikipedia_lookup(tmp_path, monkeypatch):
    source = tmp_path / "source.html"
    source.write_text("<p>Changed report.</p>", encoding="utf-8")
    artifact = tmp_path / "backend/generated_artifacts/encyclopedia_concepts.json"
    artifact.parent.mkdir(parents=True)
    previous = json.dumps({"provenance": {"extractor": "txt2phrases", "source_sha256": "old"}})
    artifact.write_text(previous, encoding="utf-8")
    monkeypatch.setattr(builder, "ROOT", tmp_path)
    with pytest.raises(ValueError, match="rebuild the extraction first"):
        builder.build(source, enrich_existing=True)
    assert artifact.read_text(encoding="utf-8") == previous


def test_failed_wikipedia_enrichment_retains_previous_vocabulary(tmp_path, monkeypatch):
    import backend.encyclopedia.pipeline as report

    source = tmp_path / "source.html"
    source.write_text("<p>Climate change.</p>", encoding="utf-8")
    artifact = tmp_path / "backend/generated_artifacts/encyclopedia_concepts.json"
    artifact.parent.mkdir(parents=True)
    artifact.write_text("previous build", encoding="utf-8")
    monkeypatch.setattr(builder, "ROOT", tmp_path)
    monkeypatch.setattr(report, "build_report_encyclopedia", lambda *a, **kw: (
        SimpleNamespace(entries=[{"term": "climate change", "content_note": "No description: no Wikipedia article"}]), {}))
    with pytest.raises(RuntimeError, match="no article descriptions"):
        builder.build(source)
    assert artifact.read_text(encoding="utf-8") == "previous build"
