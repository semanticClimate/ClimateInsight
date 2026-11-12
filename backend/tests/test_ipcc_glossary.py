"""Glossary conversion, identity, attribution and build-boundary regressions."""

import hashlib
import json

import fitz
from lxml import html
import pytest

import backend.encyclopedia.build as builder
import backend.encyclopedia.service as service
import backend.encyclopedia.pipeline as pipeline
from backend.encyclopedia.glossary import convert_glossary, GLOSSARY_LABEL, merge_glossary, render_entries


def make_pdf(path):
    document = fitz.open()
    first = document.new_page(width=595, height=842)
    first.insert_text((56, 38), "Annex I  Glossary  IPCC AR6 SYR", fontname="tiro", fontsize=10)
    first.insert_text((56, 375), "Climate change", fontname="tibo", fontsize=11)
    first.insert_text((56, 395), "A change in the climate that persists for", fontname="tiro", fontsize=11)
    first.insert_text((56, 800), "Subject to copyedit  Glossary-1", fontname="tibo", fontsize=10)
    second = document.new_page(width=595, height=842)
    second.insert_text((56, 38), "Annex I  Glossary  IPCC AR6 SYR", fontname="tiro", fontsize=10)
    second.insert_text((56, 70), "an extended period, typically decades or longer.", fontname="tiro", fontsize=11)
    second.insert_text((56, 110), "Adaptation gap", fontname="tibo", fontsize=11)
    second.insert_text((56, 130), "The difference between implemented adaptation and a goal.", fontname="tiro", fontsize=11)
    second.insert_text((56, 170), "Greenhouse gases (GHGs)", fontname="tibo", fontsize=11)
    second.insert_text((56, 190), "Gases that absorb and emit radiation.", fontname="tiro", fontsize=11)
    document.save(path)
    document.close()


def test_conversion_preserves_cross_page_definitions_and_source_anchors(tmp_path):
    source = tmp_path / "glossary.pdf"
    make_pdf(source)
    converted = tmp_path / "glossary.html"
    entries, provenance = convert_glossary(source, converted)
    assert [entry["term"] for entry in entries] == ["Climate change", "Adaptation gap", "Greenhouse gases (GHGs)"]
    assert entries[0]["definition"] == "A change in the climate that persists for an extended period, typically decades or longer."
    assert entries[0]["pages"] == [1, 2]
    assert provenance["source_sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()
    document = html.fromstring(converted.read_text(encoding="utf-8"))
    definitions = document.xpath("//p[@class='definition']/text()")
    assert not any("Subject to copyedit" in value or "Annex I" in value for value in definitions)
    assert all(document.xpath("//*[@id=$id]", id=entry["html_id"]) for entry in entries)


def definition(term, text, page=1):
    return {"term": term, "definition": text, "page": page, "pages": [page], "html_id": "test-" + term.replace(" ", "-")}


def test_ipcc_definitions_take_priority_without_conflating_distinct_terms():
    original = [{"canonical_name": "Climate change", "synonyms": ["global warming"],
                 "description": "Wikipedia description.", "wikidata_id": "Q125928",
                 "wikipedia_url": "https://en.wikipedia.org/wiki/Climate_change", "source_file": "report.html"},
                {"canonical_name": "Greenhouse gas", "synonyms": ["greenhouse gases", "GHGs"],
                 "description": "Gas description.", "wikidata_id": "Q167336",
                 "wikipedia_url": "https://en.wikipedia.org/wiki/Greenhouse_gas", "source_file": "report.html"}]
    result = merge_glossary(original, [definition("Climate change", "IPCC climate definition."),
                                      definition("Global warming", "IPCC warming definition."),
                                      definition("Greenhouse gases (GHGs)", "IPCC gas definition.")],
                            ["Climate change", "novel model phrase"], "glossary.pdf")
    by_name = {c["canonical_name"]: c for c in result}
    climate = by_name["Climate change"]
    assert climate["description"] == "IPCC climate definition."
    assert climate["wikipedia_description"] == "Wikipedia description."
    assert climate["wikidata_id"] == "Q125928"
    assert climate["source_files"] == ["glossary.pdf", "report.html"]
    assert not any(a.casefold() == "global warming" for a in climate["synonyms"])
    assert by_name["Global warming"]["description"] == "IPCC warming definition."
    assert by_name["Greenhouse gas"]["description"] == "IPCC gas definition."
    assert by_name["novel model phrase"]["description"] is None
    assert original[0]["description"] == "Wikipedia description."
    fragment = html.fromstring(render_entries(service.exchange_module(), result))
    assert GLOSSARY_LABEL in fragment.xpath(".//*[@term='Climate change']/p[@class='definition-source']")[0].text_content()
    assert fragment.xpath(".//*[@term='Climate change']//a[starts-with(@href,'/ipcc-glossary#')]")


def test_defined_term_disambiguates_an_incorrect_wikipedia_acronym():
    original = [{"canonical_name": "SIDS", "synonyms": [], "description": "Infant death.",
                 "wikidata_id": "Q161801", "wikipedia_url": "https://en.wikipedia.org/wiki/SIDS",
                 "source_file": "report.html"},
                {"canonical_name": "Small Island Developing States", "synonyms": [],
                 "description": "Island states.", "wikidata_id": "Q1434887",
                 "wikipedia_url": "https://en.wikipedia.org/wiki/Small_Island_Developing_States",
                 "source_file": "report.html"}]
    concepts = merge_glossary(original, [definition("Small Island Developing States (SIDS)", "IPCC island definition.")],
                              ["SIDS"], "glossary.pdf")
    assert len(concepts) == 1
    concept = concepts[0]
    assert concept["canonical_name"] == "Small Island Developing States"
    assert concept["wikidata_id"] == "Q1434887"
    assert concept["description"] == "IPCC island definition."
    assert "SIDS" in concept["synonyms"]
    assert concept["replaced_report_identities"][0]["wikidata_id"] == "Q161801"


@pytest.fixture
def installed_report(tmp_path, monkeypatch):
    source = tmp_path / "data/raw/ipcc_reference.html"
    source.parent.mkdir(parents=True)
    source.write_text('<p id="p1">Climate change and a retained report phrase.</p>', encoding="utf-8")
    output = tmp_path / "encyclopedia_assets/generated"
    output.mkdir(parents=True)
    wordlist = b'term,count,selected\nclimate change,8,Yes\nretained report phrase,2,Yes\n'
    (output / "wordlist.csv").write_bytes(wordlist)
    (output / "ipcc_reference.txt").write_text("Prepared original report.", encoding="utf-8")
    artifact = {"schema_version": 1, "summary": {"unique_concepts_exported": 2}, "concepts": [
        {"canonical_name": "Climate change", "synonyms": [], "description": "A Wikipedia definition.",
         "wikidata_id": "Q125928", "wikipedia_url": "https://en.wikipedia.org/wiki/Climate_change",
         "source_file": "data/raw/ipcc_reference.html"},
        {"canonical_name": "retained report phrase", "synonyms": [], "description": None,
         "wikidata_id": None, "wikipedia_url": None, "source_file": "data/raw/ipcc_reference.html"}],
        "provenance": {"source_file": "data/raw/ipcc_reference.html",
                       "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                       "extractor": "txt2phrases", "extractor_version": "1.0.6", "model": "original-model",
                       "top_n": 500, "max_terms": 300, "min_count": 2, "selected_keyphrases": 2,
                       "wordlist_sha256": hashlib.sha256(wordlist).hexdigest(),
                       "generated_at": "2026-11-03T00:00:00+00:00", "wikipedia_requested": True}}
    target = tmp_path / "backend/generated_artifacts/encyclopedia_concepts.json"
    target.parent.mkdir(parents=True)
    target.write_text(json.dumps(artifact), encoding="utf-8")
    monkeypatch.setattr(builder, "ROOT", tmp_path)
    monkeypatch.setattr(builder, "version", lambda *a: pytest.fail("Report extraction was rerun"))
    return source, output, artifact, target


def test_glossary_build_reuses_report_and_is_repeatable(installed_report, monkeypatch, tmp_path):
    source, output, previous, target = installed_report
    glossary = source.with_name("glossary.pdf")
    make_pdf(glossary)
    original_report = source.read_bytes()
    original_wordlist = (output / "wordlist.csv").read_bytes()

    def extractor(inputs, output_dir, top_n):
        text = inputs[0].read_text(encoding="utf-8")
        assert "an extended period" in text and "Adaptation gap" in text
        assert "Subject to copyedit" not in text and "Official IPCC PDF" not in text
        output_dir.mkdir()
        (output_dir / "glossary_keywords.csv").write_text('keyword,count\nClimate change,3\nimplemented adaptation,1\n', encoding="utf-8")

    monkeypatch.setattr(pipeline, "_extract_keywords_with_txt2phrases", extractor)
    first = builder.build(source, glossary=glossary, reuse_report=True)
    second = builder.build(source, glossary=glossary, reuse_report=True)
    assert first["concepts"] == second["concepts"]
    assert len(first["concepts"]) == 5
    assert first["summary"]["concepts_with_ipcc_definitions"] == 3
    assert first["provenance"]["glossary"]["extractor"] == "txt2phrases"
    assert first["provenance"]["model"] == "original-model"
    assert json.loads((output / "report_concepts.json").read_text(encoding="utf-8"))["concepts"] == previous["concepts"]
    assert source.read_bytes() == original_report
    assert (output / "wordlist.csv").read_bytes() == original_wordlist

    monkeypatch.setattr(service, "ROOT", tmp_path)
    monkeypatch.setattr(service, "source_path", lambda: source)
    monkeypatch.setattr(service, "glossary_path", lambda: glossary)
    monkeypatch.setattr(service, "settings", lambda: ("generated", tmp_path, ()))
    assert service.source_concepts(target)
    glossary.write_bytes(glossary.read_bytes() + b'\nchanged')
    with pytest.raises(ValueError, match="glossary.*stale"):
        service.source_concepts(target)


def test_unreadable_glossary_retains_installed_build(installed_report, tmp_path):
    source, output, _, target = installed_report
    original = target.read_bytes()
    pdf = tmp_path / "empty.pdf"
    document = fitz.open()
    document.new_page()
    document.save(pdf)
    document.close()
    with pytest.raises(ValueError, match="no readable text"):
        builder.build(source, glossary=pdf, reuse_report=True)
    assert target.read_bytes() == original
    assert not (output / "report_concepts.json").exists()
