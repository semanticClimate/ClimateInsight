"""Tests for encyclopedia concept matching and citation clean-up."""

import json
from pathlib import Path

import pytest

from backend.encyclopedia.importer import (
    build_normalized_vocabulary,
    merge_manual_and_imported,
)
from backend.knowledge_graph.engine import ConceptMatcher, load_encyclopedia, load_manual_encyclopedia, ENCYCLOPEDIA_JS
from backend.retrieval.citation_parser import strip_ghost_citations
import backend.knowledge_graph.engine as kg


@pytest.fixture(scope="module")
def matcher():
    return ConceptMatcher(load_manual_encyclopedia())


def test_ordinary_words_are_not_acronyms(matcher):
    found = matcher.find("There is no evidence. No change, and co-benefits.")
    assert "Nitric oxide" not in found
    assert "Carbon monoxide" not in found


def test_acronyms_match_in_capitals(matcher):
    found = matcher.find("NO emissions, NDCs and PV panels.")
    assert {"Nitric oxide", "Nationally determined contribution", "Photovoltaics"} <= set(found)


def test_flattened_subscripts_are_formulas(matcher):
    # HTML extraction turns CO<sub>2</sub> into "CO 2"
    found = matcher.find("Atmospheric CO 2 and CH 4 and N 2 O rose.")
    assert {"Carbon dioxide", "Methane", "Nitrous oxide"} <= set(found)
    assert "Carbon monoxide" not in found


def test_short_real_words_still_match(matcher):
    found = matcher.find("flood risk, ozone, coal and oil")
    assert {"Flood", "Ozone"} <= set(found)


def test_likelihood_language_is_not_a_concept(matcher):
    assert "Likelihood" not in matcher.find("It is very likely that warming continues.")


def test_strip_ghost_citations_keeps_only_retrieved_refs():
    chunks = [{"ref": "3.3.1"}, {"ref": "P1"}]
    text = "Budget is 500 GtCO2 [2.1]. Pathways [3.3.1] and a paper [P1] [P9]."
    assert strip_ghost_citations(text, chunks) == "Budget is 500 GtCO2. Pathways [3.3.1] and a paper [P1]."


def test_extracts_real_representative_ami_entry(tmp_path):
    fixture = Path(__file__).parent / "fixtures" / "encyclopedia_carbon_dioxide.html"
    output, details = build_normalized_vocabulary(fixture)

    concept = output["concepts"][0]
    assert concept["canonical_name"] == "carbon dioxide"
    assert concept["wikidata_id"] == "Q1997"
    assert concept["wikipedia_url"] == "https://en.wikipedia.org/wiki/Carbon_dioxide"
    assert concept["description"].startswith("Carbon dioxide is a chemical compound")
    assert output["summary"]["raw_entries_discovered"] == 1
    assert len(details["raw_entries"]) == 1


def test_missing_fields_are_preserved_as_none():
    output_path = Path(__file__).parent / "fixtures" / "nonexistent.html"
    output, _ = build_normalized_vocabulary(output_path)
    assert output["concepts"] == []
    assert output["summary"]["source_files_processed"] == 0


def test_duplicate_wikidata_entries_are_deduplicated(tmp_path):
    html = """<html><body>
    <div role="ami_entry" term="first name" wikidataID="Q123"><a href="https://en.wikipedia.org/wiki/First_name">First name</a></div>
    <div role="ami_entry" term="second name" wikidataID="Q123"><p class="wpage_first_para">A real description.</p></div>
    </body></html>"""
    source = tmp_path / "duplicate.html"
    source.write_text(html, encoding="utf-8")
    output, _ = build_normalized_vocabulary(source)
    assert output["summary"]["raw_entries_discovered"] == 2
    assert output["summary"]["unique_concepts_exported"] == 1
    assert output["concepts"][0]["wikidata_id"] == "Q123"
    assert output["concepts"][0]["description"] == "A real description."


def test_json_generation_is_deterministic(tmp_path):
    fixture = Path(__file__).parent / "fixtures" / "encyclopedia_carbon_dioxide.html"
    first, _ = build_normalized_vocabulary(fixture)
    second, _ = build_normalized_vocabulary(fixture)
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


def test_manual_vocabulary_precedence_and_imported_concept_recognition():
    manual = load_manual_encyclopedia()
    original_climate = len(set(manual.values()))
    merged, _, conflicts = merge_manual_and_imported(
        manual,
        [{
            "canonical_name": "Planetary health",
            "synonyms": ["health of human civilization", "weather"],
            "description": "An interdisciplinary health concept.",
            "wikidata_id": "Q30589121",
            "wikipedia_url": "https://en.wikipedia.org/wiki/Planetary_health",
            "source_file": "Examples/ar6-wg2-ch18_encyclopedia.html",
        }],
    )
    assert "planetary health" in merged
    assert merged["planetary health"] == "Planetary health"
    assert "weather" not in merged
    assert any(item["reason"] == "ambiguous_common_or_short_term" for item in conflicts)
    assert len(set(manual.values())) == original_climate

    imported_matcher = ConceptMatcher(merged)
    assert "Planetary health" in imported_matcher.find(
        "Planetary health links environmental change and human health."
    )


def test_legacy_mode_keeps_manual_matcher_working(monkeypatch):
    monkeypatch.setenv("CLIMATEINSIGHT_ENCYCLOPEDIA_MODE", "legacy")
    wiki_map = load_encyclopedia(
        ENCYCLOPEDIA_JS,
        Path("/definitely/missing/generated.json"),
    )
    matcher = ConceptMatcher(wiki_map)
    assert {"Carbon dioxide", "Methane"} <= set(matcher.find(
        "Carbon dioxide and methane are greenhouse gases."
    ))


def test_manual_alias_conflicts_keep_manual_title():
    manual = {"wind energy": "Wind power"}
    merged, _, conflicts = merge_manual_and_imported(
        manual,
        [{
            "canonical_name": "Imported concept",
            "synonyms": ["wind energy"],
            "description": None,
            "wikidata_id": "Q999999",
            "wikipedia_url": None,
            "source_file": "fixture.html",
        }],
    )
    assert merged["wind energy"] == "Wind power"
    assert any(
        item["reason"] == "manual_vocabulary_precedence"
        and item["alias"] == "wind energy"
        for item in conflicts
    )


def test_vocabulary_merge_does_not_change_passage_cooccurrence_weights():
    import itertools
    from collections import Counter

    manual = ConceptMatcher({"climate change": "Climate change", "carbon dioxide": "Carbon dioxide"})
    expanded_map, _, _ = merge_manual_and_imported(
        {"climate change": "Climate change", "carbon dioxide": "Carbon dioxide"},
        [{
            "canonical_name": "Carbon dioxide",
            "synonyms": [],
            "description": None,
            "wikidata_id": "Q1997",
            "wikipedia_url": "https://en.wikipedia.org/wiki/Carbon_dioxide",
            "source_file": "fixture.html",
        }],
    )
    expanded = ConceptMatcher(expanded_map)

    text = "Climate change and carbon dioxide are discussed together."
    manual_concepts = sorted(manual.find(text))
    expanded_concepts = sorted(expanded.find(text))
    manual_weights = Counter(tuple(sorted(pair)) for pair in itertools.combinations(manual_concepts, 2))
    expanded_weights = Counter(tuple(sorted(pair)) for pair in itertools.combinations(expanded_concepts, 2))
    assert manual_weights == expanded_weights == Counter({("Carbon dioxide", "Climate change"): 1})


def test_ipcc_sources_keep_identical_section_numbers_in_different_reports_separate():
    common = {"source_type": "ipcc_report", "section": "1.1", "section_title": "Introduction"}
    key, info = kg._source_of(common)
    assert key == "ipcc:1.1"
    assert info["label"] == "IPCC AR6 1.1 Introduction"
    assert info["document"] == "ipcc_reference"
    keys = {key}
    for document in ("wg1_Chapter01", "wg2_Chapter01"):
        key, info = kg._source_of({**common, "source_path": f"data/raw/{document}.html", "document_title": document})
        keys.add(key)
        assert document in info["label"]
        assert info["document"] == document
    assert len(keys) == 3


@pytest.mark.parametrize("metadata,expected", [
    ({"section": "2.1.2", "html_id": "paragraph-2.2.3-p1"}, "/ipcc-reference#paragraph-2.2.3-p1"),
    ({"section": "2.1.2"}, "/ipcc-reference#2.1.2"),
    ({"html_id": "paragraph with space"}, "/ipcc-reference#paragraph%20with%20space"),
    ({"source_path": "data/raw/wg1_Chapter01.html", "html_id": "p1"}, "/ipcc-reference?doc=wg1_Chapter01#p1"),
    ({}, ""),
])
def test_ipcc_links_prefer_real_paragraph_anchors(metadata, expected):
    assert kg._link_for({"source_type": "ipcc_report", **metadata}) == expected


def test_paper_links_are_preserved():
    assert kg._link_for({"pmcid": "PMC123"}) == "/paper/123"
    assert kg._link_for({"doi": "10.example/paper"}) == "https://doi.org/10.example/paper"


def test_same_section_number_in_distinct_reports_does_not_create_a_source_bridge(monkeypatch):
    from types import SimpleNamespace
    vocabulary = {"ocean warming": "Ocean warming", "coral reefs": "Coral reefs", "flood risk": "Flood risk"}
    monkeypatch.setattr(kg, "load_encyclopedia", lambda: vocabulary)
    monkeypatch.setattr(kg, "get_collection", lambda: SimpleNamespace(get=lambda **kwargs: {
        "documents": ["Ocean warming damages coral reefs.", "Flood risk increases."],
        "metadatas": [
            {"source_type": "ipcc_report", "section": "1.1", "source_path": "data/raw/wg1.html"},
            {"source_type": "ipcc_report", "section": "1.1", "source_path": "data/raw/wg2.html"},
        ],
    }))
    graph = kg._build()["graph"]
    assert graph["stats"]["source_bridges"] == 0
    assert graph["stats"]["components"] == 2


def test_question_sources_keep_report_identity_and_paragraph_links_when_llm_is_unavailable(monkeypatch):
    from backend.knowledge_graph import question
    chunks = [
        {"text": "Ocean warming is observed.", "source_type": "ipcc_report", "section": "1.1", "html_id": "syr-p1"},
        {"text": "Ocean warming is observed.", "source_type": "ipcc_report", "section": "1.1", "html_id": "wg1-p1",
         "source_path": "data/raw/wg1.html", "document_title": "Working Group I"},
    ]
    monkeypatch.setattr(question, "query_chunks", lambda *args, **kwargs: chunks)
    monkeypatch.setattr(kg, "focus_concepts", lambda *args: [])
    monkeypatch.setattr(kg, "main_concepts", lambda *args: [])
    monkeypatch.setattr(kg, "subgraph", lambda *args: {"nodes": [], "edges": []})
    def unavailable(*args, **kwargs):
        raise RuntimeError("Ollama unavailable")
    monkeypatch.setattr(question, "ask_llm", unavailable)
    result = question.generate_concept_graph("Ocean warming?")
    assert [source["ref"] for source in result["sources"]] == ["1.1", "wg1:1.1"]
    assert [source["link"] for source in result["sources"]] == ["/ipcc-reference#syr-p1", "/ipcc-reference?doc=wg1#wg1-p1"]
    assert "Working Group I" in result["sources"][1]["label"]
    assert len(result["citations"]) == 2
