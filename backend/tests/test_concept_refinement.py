"""Source-grounded vocabulary refinement and local-evidence graph behavior."""

from types import SimpleNamespace

import pytest

from backend.encyclopedia.concepts import concept_key, noise_reason, refine_concepts
from backend.encyclopedia.importer import merge_manual_and_imported
from backend.knowledge_graph.topics import association_weight, relation_units
import backend.knowledge_graph.engine as kg


def record(name, aliases=(), definition=None, qid=None):
    item = {"canonical_name": name, "synonyms": list(aliases), "description": definition,
            "wikidata_id": qid, "wikipedia_url": None, "source_file": "report.html"}
    if definition:
        item["definition_source"] = {"term": name, "page": 1, "html_id": "test"}
        item["description_source"] = "IPCC AR6 SYR Glossary"
    return item


def test_reference_and_uncertainty_noise_is_removed_without_dropping_real_science():
    records = [record(name) for name in ["WGII SPM", "AR 5", "SPM", "Analytic confidence", "medium confidence", "Global",
                                        "confidence interval", "radiative forcing", "Climate change"]]
    cleaned, audit = refine_concepts(records)
    assert {c["canonical_name"] for c in cleaned} == {"confidence interval", "radiative forcing", "Climate change"}
    assert {r["reason"] for r in audit["removed"]} == {"report_reference", "calibrated_uncertainty", "generic_expression"}
    assert not noise_reason("global warming")
    assert not noise_reason("low-carbon energy")
    assert not noise_reason("Lock-in")
    assert not noise_reason("Lock‐in")


def test_observed_plural_spelling_and_hyphen_variants_merge_with_ipcc_definition_priority():
    records = [record("Carbon budget", definition="Official budget definition."), record("carbon budgets"),
               record("sea-level rise"), record("sea level rise"), record("decarbonisation"), record("decarbonization")]
    cleaned, _ = refine_concepts(records)
    aliases, metadata, _ = merge_manual_and_imported({}, cleaned)
    assert aliases["carbon budget"] == aliases["carbon budgets"] == "Carbon budget"
    assert aliases["sea-level rise"] == aliases["sea level rise"]
    assert aliases["decarbonisation"] == aliases["decarbonization"]
    assert metadata["Carbon budget"]["description"] == "Official budget definition."
    assert concept_key("analysis") == "analysis"
    assert concept_key("greenhouse gases") == concept_key("greenhouse gas")


def test_explicit_source_abbreviations_restore_core_terms_and_reject_cross_clause_expansions():
    sources = [("report.html", '<p id="gases">Carbon dioxide (CO2), nitrous oxide (N2O), and methane (CH4) cause warming.</p>'
                '<p>Nationally determined contributions (NDCs) set targets.</p>'
                '<p>IMP-LD, a focus on sustainable development (IMP-SP), and extreme weather events (RFC2).</p>')]
    cleaned, audit = refine_concepts([record("NDCs")], sources)
    aliases, _, _ = merge_manual_and_imported({}, cleaned)
    assert aliases["co2"] == "Carbon dioxide"
    assert aliases["ch4"] == "Methane"
    assert aliases["n2o"] == "Nitrous oxide"
    assert aliases["ndcs"] == "Nationally determined contributions"
    assert all("methane" not in c["canonical_name"].casefold() or c["canonical_name"] == "Methane" for c in cleaned)
    assert not any(a["alias"] in {"IMP-SP", "RFC2"} for a in audit["source_abbreviations"])
    carbon = next(c for c in cleaned if c["canonical_name"] == "Carbon dioxide")
    assert carbon["alias_sources"][0]["html_id"] == "gases"
    assert carbon["description"] is None  # no invented definition
    again, _ = refine_concepts(cleaned, sources)
    assert again == cleaned


def test_shared_alias_cannot_transitively_merge_distinct_definitions_or_entities():
    climate = record("Climate change", definition="Climate definition.")
    warming = record("Global warming", definition="Warming definition.")
    bridge = record("ambiguous phrase", ["Climate change", "Global warming"])
    cleaned, _ = refine_concepts([climate, bridge, warming])
    assert sum(bool(c.get("definition_source")) for c in cleaned) == 2
    first, second = record("same name", qid="Q1"), record("same names", qid="Q2")
    cleaned, _ = refine_concepts([first, second])
    assert len(cleaned) == 2
    entries = [record("Just transition", definition="See Transition."),
               record("Just transitions", definition="The full official definition.")]
    cleaned, _ = refine_concepts(entries)
    assert len(cleaned) == 2  # preserve separately worded official source entries


def test_abbreviation_expansion_preserves_literal_source_punctuation():
    name = "Land use, land-use change and forestry"
    sources = [("glossary.html", '<p id="land">' + name + ' (LULUCF) describes land activities.</p>')]
    cleaned, audit = refine_concepts([record(name)], sources)
    assert len(cleaned) == 1
    assert cleaned[0]["canonical_name"] == name
    assert "LULUCF" in cleaned[0]["synonyms"]
    assert audit["source_abbreviations"][0]["term"] == name


def test_source_expansion_replaces_an_incorrect_acronym_wikipedia_meaning():
    wrong = record("PM", qid="Q217451")
    wrong.update({"description": "After midday.", "wikipedia_url": "https://en.wikipedia.org/wiki/PM"})
    cleaned, _ = refine_concepts([wrong], [("report.html", '<p id="p1">Particulate matter (PM) affects health.</p>')])
    assert len(cleaned) == 1
    entry = cleaned[0]
    assert entry["canonical_name"] == "Particulate matter"
    assert entry["description"] is None and entry["wikipedia_url"] is None
    assert entry["replaced_report_identities"][0]["wikidata_id"] == "Q217451"
    aliases, _, _ = merge_manual_and_imported({}, cleaned)
    assert kg.ConceptMatcher(aliases).find("PM affects health in the pm.") == {"Particulate matter": 1}


def test_matcher_recognises_hyphen_unicode_and_space_variants_and_handles_empty_vocabulary():
    matcher = kg.ConceptMatcher({"sea level rise": "Sea level rise", "co2": "Carbon dioxide"})
    assert matcher.find("CO₂ causes sea-level rise and sea–level rise.") == {"Carbon dioxide": 1, "Sea level rise": 2}
    assert kg.ConceptMatcher({"WGII SPM": "WGII SPM"}).find("WGII SPM") == {}


def test_local_windows_preserve_decimals_and_do_not_span_sentences():
    assert list(relation_units("Warming reached 1.5°C. Coastal flooding increased.")) == [
        "Warming reached 1.5°C.", "Coastal flooding increased."]
    assert len(list(relation_units("Carbon budgets, e.g. mitigation budgets, are finite."))) == 1
    assert all(len(unit.split()) <= 60 for unit in relation_units(" ".join(["term"] * 150)))


def build_graph(monkeypatch, docs):
    mapping = {"carbon budget": "Carbon budget", "mitigation": "Mitigation", "drought": "Drought", "flooding": "Flooding"}
    collection = SimpleNamespace(get=lambda **kw: {"documents": docs, "metadatas": [{"section": "2.1"}] * len(docs)})
    monkeypatch.setattr(kg, "get_collection", lambda: collection)
    monkeypatch.setattr(kg, "load_encyclopedia", lambda: mapping)
    return kg._build()


def test_unrelated_sentences_in_one_chunk_are_not_a_passage_relationship(monkeypatch):
    state = build_graph(monkeypatch, ["Carbon budget and mitigation belong together. Drought and flooding belong together."])
    graph = state["G"]
    assert graph["Carbon budget"]["Mitigation"]["kind"] == "passage"
    assert not graph.has_edge("Carbon budget", "Flooding") or graph["Carbon budget"]["Flooding"]["kind"] == "source"
    assert len(state["graph"]["groups"]) == 2
    assert len([1 for _, _, data in graph.edges(data=True) if data["kind"] == "source"]) == 1


def test_relationship_counts_and_excerpts_use_only_passages_with_local_evidence(monkeypatch):
    state = build_graph(monkeypatch, ["Carbon budget is finite. Mitigation matters.",
                                     "Carbon budget and mitigation are linked. Carbon budget and mitigation matter."])
    assert state["G"]["Carbon budget"]["Mitigation"]["weight"] == 1
    monkeypatch.setattr(kg, "_state", lambda: state)
    result = kg.link_resources("Mitigation", "Carbon budget")
    assert result["total"] == 1
    assert len(result["passages"]) == 1
    assert "Carbon budget and mitigation" in result["passages"][0]["snippet"]
    assert len(result["passages"][0]["highlights"]) == 2


def test_common_hubs_are_discounted_and_topic_names_describe_the_community(monkeypatch):
    assert association_weight(1, 1, 1, 100) > association_weight(1, 80, 1, 100)
    state = build_graph(monkeypatch, ["Carbon budget and mitigation are linked. Drought and flooding are linked."])
    names = {group["label"] for group in state["graph"]["groups"]}
    assert any("Carbon budget" in name and "Mitigation" in name for name in names)
    assert any("Drought" in name and "Flooding" in name for name in names)
    assert all(len(group["topics"]) == 2 for group in state["graph"]["groups"])
