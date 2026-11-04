"""Offline identity, package, report and HTTP integration regressions."""

import hashlib
import csv
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
from types import ModuleType, SimpleNamespace

from lxml import html
import pytest

import encyclopedia_service as service
import knowledge_graph as kg
from encyclopedia_importer import merge_manual_and_imported


CASES = [
    ("Green infrastructure", "green infrastructure", "Q3427027", "Green_infrastructure"),
    ("Carbon tax", "carbon tax", "Q288401", "Carbon_tax"),
    ("Greenhouse gas emissions", "greenhouse gas emissions", "Q106358009", "Greenhouse_gas_emissions"),
]


def concept(title, qid, slug, synonyms=()):
    return {"canonical_name": title, "synonyms": list(synonyms),
            "description": "Imported definition of " + title,
            "wikidata_id": qid, "wikipedia_url": "https://en.wikipedia.org/wiki/" + slug,
            "source_file": "encyclopedia.html"}


@pytest.mark.parametrize("public, imported, qid, slug", CASES)
def test_imported_metadata_uses_existing_public_id(public, imported, qid, slug):
    manual = {public.lower(): public}
    if public == "Green infrastructure":
        manual = {"urban green infrastructure": public}
    merged, metadata, _ = merge_manual_and_imported(manual, [concept(imported, qid, slug)])
    assert set(merged.values()) == {public}
    assert kg.ConceptMatcher(merged).find(imported.upper()) == {public: 1}
    assert metadata[public]["description"] == "Imported definition of " + imported
    assert metadata[public]["wikidata_id"] == qid
    assert metadata[public]["wikipedia_url"].endswith("/" + slug)


def test_wikidata_resolution_is_order_independent_and_alias_collisions_are_not_identity():
    records = [concept("Tax on carbon", "Q288401", "Carbon_tax"), concept("carbon tax", "Q288401", "Carbon_tax")]
    manual = {"carbon taxes": "Carbon tax"}
    first = merge_manual_and_imported(manual, records)
    assert first == merge_manual_and_imported(manual, list(reversed(records)))
    assert first[0]["tax on carbon"] == "Carbon tax"
    assert set(first[1]) == {"Carbon tax"}
    merged, metadata, conflicts = merge_manual_and_imported(
        {"urban green infrastructure": "Green infrastructure"},
        [concept("green infrastructure", "Q3427027", "Green_infrastructure"),
         concept("Urban green infrastructure", "Q57498230", "Urban_green_infrastructure")],
    )
    assert merged["urban green infrastructure"] == "Green infrastructure"
    assert metadata["Green infrastructure"]["wikidata_id"] == "Q3427027"
    assert any(c["reason"] == "manual_vocabulary_precedence" for c in conflicts)


def test_conflicting_qids_cannot_overwrite_a_node_metadata():
    merged, metadata, conflicts = merge_manual_and_imported(
        {"carbon tax": "Carbon tax"},
        [concept("carbon tax", "Q1", "Carbon_tax"), concept("Carbon tax", "Q2", "Carbon_tax")],
    )
    assert merged == {"carbon tax": "Carbon tax"}
    assert "Carbon tax" not in metadata
    assert any(c["reason"] == "conflicting_wikidata_ids" for c in conflicts)


def test_real_builder_keeps_counts_bridge_weights_communities_and_display_edges(monkeypatch):
    manual = {"urban green infrastructure": "Green infrastructure", "carbon tax": "Carbon tax",
              "greenhouse gas emissions": "Greenhouse gas emissions", "amoc": "AMOC"}
    records = [concept(imported, qid, slug) for _, imported, qid, slug in CASES]
    merged, metadata, _ = merge_manual_and_imported(manual, records)
    docs = ["Green infrastructure, carbon tax and greenhouse gas emissions.",
            "Urban green infrastructure and carbon tax.", "AMOC alone."]
    collection = SimpleNamespace(get=lambda **kw: {"documents": docs, "metadatas": [{"section": "2.1"}] * 3})
    monkeypatch.setattr(kg, "get_collection", lambda: collection)
    monkeypatch.setattr(kg, "load_encyclopedia", lambda: merged)
    monkeypatch.setattr(kg, "_import_metadata", metadata)
    actual = kg._build()
    assert set(actual["G"]) == {"Green infrastructure", "Carbon tax", "Greenhouse gas emissions", "AMOC"}
    assert actual["G"]["Green infrastructure"]["Carbon tax"]["weight"] == 2
    bridges = [d for _, _, d in actual["G"].edges(data=True) if d["kind"] == "source"]
    assert len(bridges) == 1 and bridges[0]["weight"] == 0.5
    assert all("encyclopedia" in node for node in actual["graph"]["nodes"] if node["id"] != "AMOC")
    baseline = dict(manual, **{"green infrastructure": "Green infrastructure"})
    monkeypatch.setattr(kg, "load_encyclopedia", lambda: baseline)
    expected = kg._build()
    assert actual["graph"]["edges"] == expected["graph"]["edges"]
    assert actual["graph"]["groups"] == expected["graph"]["groups"]


def test_generated_artifact_edits_refresh_the_vocabulary_cache(tmp_path):
    artifact = tmp_path / "entries.json"
    record = concept("carbon tax", "Q288401", "Carbon_tax")
    data = {"schema_version": 1, "concepts": [record], "provenance": {
        "source_sha256": hashlib.sha256(service.source_path().read_bytes()).hexdigest()}}
    artifact.write_text(json.dumps(data), encoding="utf-8")
    first = service.source_concepts(artifact)
    record["description"] = "A newly updated local description."
    artifact.write_text(json.dumps(data), encoding="utf-8")
    second = service.source_concepts(artifact)
    assert first[0]["description"] != second[0]["description"]
    assert second[0]["description"] == record["description"]


def test_missing_or_stale_build_does_not_silently_reenable_manual_terms(tmp_path, monkeypatch):
    artifact = tmp_path / "entries.json"
    data = {"schema_version": 1, "concepts": [concept("carbon tax", "Q288401", "Carbon_tax")],
            "provenance": {"source_sha256": "an-old-report"}}
    artifact.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="stale"):
        service.source_concepts(artifact)
    artifact.write_text('{"schema_version": 1, "concepts": []}', encoding="utf-8")
    with pytest.raises(ValueError, match="Build the IPCC"):
        service.source_concepts(artifact)


def test_generated_vocabulary_does_not_read_manual_map(monkeypatch):
    monkeypatch.setattr(kg, "load_manual_encyclopedia", lambda *a: pytest.fail("Manual vocabulary used"))
    aliases = kg.load_encyclopedia()
    assert aliases
    provenance = json.loads(service.GENERATED.read_text(encoding="utf-8"))["provenance"]
    assert provenance["extractor"] == "txt2phrases"
    assert provenance["source_sha256"] == hashlib.sha256(service.source_path().read_bytes()).hexdigest()
    with (service.ROOT / "encyclopedia/generated/wordlist.csv").open(encoding="utf-8") as stream:
        selected = {r["term"].casefold() for r in csv.DictReader(stream) if r["selected"] == "Yes"}
    assert selected
    # Canonical titles may be resolved by Wikipedia; every node has an extracted alias.
    for title in set(aliases.values()):
        assert any(alias in selected for alias, target in aliases.items() if target == title)
    active = (service.ROOT / "encyclopedia/climate-wiki.js").read_text(encoding="utf-8")
    assert "/* ENCYCLOPEDIA_DATA */" in active and "const WIKI_MAP = {" not in active


@pytest.fixture
def client(monkeypatch):
    # Import only Flask routing, without starting retrieval/Redis/model services.
    names = {
        "retrieval": ["answer_question"], "sessions": ["add_to_history", "clear_history"],
        "concept_graph": ["handle_concept_graph_request"],
        "services": ["chat_response", "error_response", "health_response", "message_response"],
    }
    for name, attributes in names.items():
        module = ModuleType(name)
        for attribute in attributes:
            setattr(module, attribute, lambda *args, **kw: {})
        monkeypatch.setitem(sys.modules, name, module)
    path = service.ROOT / "backend/app.py"
    spec = importlib.util.spec_from_file_location("encyclopedia_test_app", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.app.config["TESTING"] = True
    monkeypatch.setattr(kg, "get_collection", lambda: pytest.fail("Report routes must not open ChromaDB"))
    return module.app.test_client()


def test_report_and_glossary_routes_have_real_entries_and_preserve_source_paragraphs(client):
    raw_path = service.ROOT / "data/raw/ipcc_reference.html"
    original = raw_path.read_bytes()
    raw = html.fromstring(raw_path.read_text(encoding="utf-8"))
    response = client.get("/ipcc-reference")
    assert response.status_code == 200
    rendered = html.fromstring(response.data)
    assert rendered.xpath("//*[@role='ami_encyclopedia']/*[@role='ami_entry']")
    original_paragraphs = [(p.get("id"), p.text_content()) for p in raw.xpath("//p[@id]")]
    original_ids = {identifier for identifier, text in original_paragraphs}
    served_paragraphs = [(p.get("id"), p.text_content()) for p in rendered.xpath("//p[@id]") if p.get("id") in original_ids]
    assert served_paragraphs == original_paragraphs
    glossary = client.get("/ipcc-encyclopedia")
    assert glossary.status_code == 200
    assert b'role="ami_entry"' in glossary.data
    assert b'Wikipedia' in glossary.data and b'Read the IPCC passage' in glossary.data
    assert raw_path.read_bytes() == original


def test_shared_viewer_uses_package_descriptions_and_is_valid_javascript(client):
    response = client.get("/climate-wiki-js")
    assert response.status_code == 200
    script = response.get_data(as_text=True)
    assert "const ENCYCLOPEDIA_CONCEPTS =" in script
    assert "if (imported && imported.description)" in script
    assert 'node.getAttribute("role") === "ami_encyclopedia"' in script
    if shutil.which("node"):
        checked = subprocess.run([shutil.which("node"), "--check"], input=script, text=True, encoding="utf-8", capture_output=True)
        assert checked.returncode == 0, checked.stderr


def test_legacy_switch_restores_original_script_and_report(client, monkeypatch):
    monkeypatch.setenv("CLIMATEINSIGHT_ENCYCLOPEDIA_MODE", "legacy")
    script = client.get("/climate-wiki-js")
    assert script.data == (service.ROOT / "encyclopedia/climate-wiki.legacy.js").read_bytes()
    report = client.get("/ipcc-reference")
    assert b'role="ami_entry"' not in report.data
    assert client.get("/ipcc-encyclopedia").status_code == 503


def test_missing_package_reports_unavailability_without_reactivating_manual_terms(client, monkeypatch, tmp_path):
    monkeypatch.setenv("CLIMATEINSIGHT_ENCYCLOPEDIA_REPO", str(tmp_path))
    assert client.get("/ipcc-reference").status_code == 200
    script = client.get("/climate-wiki-js")
    assert script.status_code == 503
    assert b"build_ipcc_encyclopedia.py" in script.data


def test_unknown_api_route_returns_json_instead_of_html(client):
    response = client.get("/api/route-that-does-not-exist")
    assert response.status_code == 404
    assert response.is_json
    assert response.get_json() == {
        "error": "API route not found",
        "path": "/api/route-that-does-not-exist",
    }
