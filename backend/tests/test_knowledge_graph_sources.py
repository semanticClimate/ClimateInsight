"""The knowledge graph must not depend on one IPCC file or one term-list file.

These tests pin the parts that let sources change without code changes:
term lists in several formats, several IPCC documents side by side, links
that point at the right document and paragraph, and concept matching that
does not depend on how a reader writes chemical formulas.
"""

import json

import pytest

import knowledge_graph as kg
from knowledge_graph import ConceptMatcher, load_encyclopedia


# ─── Term lists ───────────────────────────────────────────────────────────────


AMI_HTML = """<html><body><div role="ami_dictionary">
  <div role="ami_entry" term="marine heatwave">
    <a href="https://en.wikipedia.org/wiki/Marine_heatwave">Wikipedia</a>
    <ul class="synonym_list"><li>marine heat wave</li><li>MHW</li></ul>
  </div>
  <div role="ami_entry" name="ocean heat content">
    <p class="wpage_first_para">Ocean heat content is ...</p>
  </div>
  <div role="ami_entry"><p>an entry without a term is ignored</p></div>
</div></body></html>"""


def test_default_term_list_is_climate_wiki_js(monkeypatch):
    monkeypatch.delenv(kg.ENCYCLOPEDIA_ENV, raising=False)
    assert kg.encyclopedia_path() == kg.ENCYCLOPEDIA_JS
    terms = load_encyclopedia()
    assert terms and all(t == t.lower() for t in terms)


def test_semanticclimate_encyclopedia_html(tmp_path):
    path = tmp_path / "encyclopedia.html"
    path.write_text(AMI_HTML, encoding="utf-8")
    assert load_encyclopedia(path) == {
        "marine heatwave": "Marine heatwave",
        "marine heat wave": "Marine heatwave",
        "mhw": "Marine heatwave",
        "ocean heat content": "ocean heat content",
    }


def test_json_mapping_and_concept_list(tmp_path):
    mapping = tmp_path / "terms.json"
    mapping.write_text(json.dumps({"Sea level rise": "Sea level rise"}))
    assert load_encyclopedia(mapping) == {"sea level rise": "Sea level rise"}

    concepts = tmp_path / "concepts.json"
    concepts.write_text(json.dumps({"concepts": [{
        "canonical_name": "carbon dioxide",
        "aliases": ["CO2"],
        "wikipedia_url": "https://en.wikipedia.org/wiki/Carbon_dioxide",
    }]}))
    assert load_encyclopedia(concepts) == {"carbon dioxide": "Carbon dioxide", "co2": "Carbon dioxide"}


def test_unsupported_term_list_is_an_error(tmp_path):
    path = tmp_path / "terms.txt"
    path.write_text("x")
    with pytest.raises(ValueError):
        load_encyclopedia(path)


def test_term_list_can_be_chosen_by_environment(tmp_path, monkeypatch):
    path = tmp_path / "terms.json"
    path.write_text(json.dumps({"permafrost": "Permafrost"}))
    monkeypatch.setenv(kg.ENCYCLOPEDIA_ENV, str(path))
    assert kg.encyclopedia_path() == path
    assert load_encyclopedia() == {"permafrost": "Permafrost"}


# ─── Concept matching does not depend on the reader's formula style ──────────


def test_flattened_and_joined_formulas_match_the_same():
    m = ConceptMatcher({"co2": "Carbon dioxide", "co": "Carbon monoxide"})
    assert m.find("Emissions of CO 2 rose.") == m.find("Emissions of CO2 rose.")
    assert "Carbon monoxide" not in m.find("Emissions of CO 2 rose.")


# ─── Several IPCC documents ───────────────────────────────────────────────────


def _ipcc(doc, section, html_id="", title="T", document_title="Doc"):
    return {
        "source_type": "ipcc_report",
        "source_path": f"/x/data/raw/{'ipcc/' if doc != 'ipcc_reference' else ''}{doc}.html",
        "section": section,
        "section_title": title,
        "html_id": html_id,
        "document_title": document_title,
    }


def test_default_report_keeps_its_source_key_and_label():
    key, info = kg._source_of(_ipcc("ipcc_reference", "2.1", title="Observed Changes"))
    assert key == "ipcc:2.1"
    assert info["label"] == "IPCC AR6 2.1 Observed Changes"


def test_same_section_in_two_chapters_stays_separate():
    a, ia = kg._source_of(_ipcc("wg1_Chapter01", "1.1", document_title="Chapter 1: Framing"))
    b, _ = kg._source_of(_ipcc("wg2_Chapter01", "1.1"))
    assert a != b
    assert ia["label"].startswith("IPCC AR6 Chapter 1: Framing 1.1")


def test_links_use_paragraph_id_and_document():
    assert kg._link_for(_ipcc("ipcc_reference", "2.1.2", html_id="2.2.3_p1")) == "/ipcc-reference#2.2.3_p1"
    assert kg._link_for(_ipcc("ipcc_reference", "2.1")) == "/ipcc-reference#2.1"
    assert kg._link_for(_ipcc("wg1_Chapter01", "1.1", html_id="1.1_p1")) == "/ipcc-reference?doc=wg1_Chapter01#1.1_p1"


class _FakeCollection:
    def __init__(self, documents, metadatas):
        self._data = {"documents": documents, "metadatas": metadatas}

    def get(self, include=None):
        return self._data

    def count(self):
        return len(self._data["documents"])


def test_graph_builds_across_several_ipcc_chapters(monkeypatch):
    docs = [
        "Marine heatwaves raise ocean heat content.",
        "Ocean heat content and marine heatwaves are linked.",
    ]
    metas = [_ipcc("wg1_Chapter09", "9.2", "9.2_p1"), _ipcc("wg2_Chapter03", "3.2", "3.2_p1")]
    monkeypatch.setattr(kg, "get_collection", lambda: _FakeCollection(docs, metas))
    monkeypatch.setattr(kg, "load_encyclopedia", lambda: {
        "marine heatwaves": "Marine heatwave", "ocean heat content": "Ocean heat content",
    })
    graph = kg._build()["graph"]
    assert {n["id"] for n in graph["nodes"]} == {"Marine heatwave", "Ocean heat content"}
    assert set(graph["sources"]) == {"ipcc:wg1_Chapter09:9.2", "ipcc:wg2_Chapter03:3.2"}


# ─── The index keeps what the graph's links need ──────────────────────────────


def test_indexer_stores_paragraph_anchor(monkeypatch):
    import vectorstore.indexer as indexer

    stored = {}

    class Collection:
        def get(self, include=None):
            return {"ids": [], "metadatas": []}

        def add(self, ids, documents, embeddings, metadatas):
            stored.update(zip(ids, metadatas))

        def count(self):
            return len(stored)

    monkeypatch.setattr(indexer, "get_collection", lambda: Collection())
    monkeypatch.setattr(indexer, "embed", lambda texts: [[0.0] for _ in texts])
    indexer.ingest_chunks([{"chunk_id": "c1", "text": "t", "section": "2.1.2", "html_id": "2.2.3_p1",
                            "source_path": "/x/ipcc_reference.html", "source_type": "ipcc_report"}])
    assert stored["c1"]["html_id"] == "2.2.3_p1"
