"""The scientific source boundary is independent of Wikipedia enrichment."""

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.encyclopedia import corpus, service
from backend.encyclopedia.corpus import extract_document
from backend.encyclopedia.sources import POLICY, approved_paths, load_documents


@pytest.fixture
def approved_corpus(tmp_path, monkeypatch):
    raw = tmp_path / "data/raw"
    raw.mkdir(parents=True)
    (raw / "report.html").write_text('<html><title>Report</title><p id="p1">Climate change affects coastal fisheries and marine heatwaves.</p></html>', encoding="utf-8")
    (raw / "glossary.html").write_text('<html><title>Glossary</title><section class="glossary-entry" id="term-climate" data-term="Climate change" data-page="1">'
        '<h2>Climate change</h2><p class="definition">A persistent change in climate.</p></section></html>', encoding="utf-8")
    (raw / "PMC123.xml").write_text('<article><front><article-meta><article-id pub-id-type="pmc">PMC123</article-id>'
        '<title-group><article-title>Marine study</article-title></title-group></article-meta></front><body><sec><title>Results</title>'
        '<p>Marine heatwaves affect fisheries and coastal communities in this scientific study.</p></sec></body>'
        '<back><ref-list><ref><mixed-citation>Unapproved reference-list phrase.</mixed-citation></ref></ref-list></back></article>', encoding="utf-8")
    (raw / "PMC999.xml").write_text('<article>Unlisted paper must not be read.</article>', encoding="utf-8")
    (tmp_path / "config.toml").write_text('[encyclopedia]\nsource="data/raw/report.html"\nglossary="data/raw/glossary.html"\npapers=["data/raw/PMC123.xml"]\n', encoding="utf-8")

    def extract(document, root, cache, config):
        directory = cache / Path(document.source_file).stem
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "wordlist.csv").write_text('term,count,selected\nClimate change,2,Yes\n', encoding="utf-8")
        terms = ["Climate change"] if document.kind != "research_article" else ["Marine heatwaves", "fisheries"]
        return terms, directory

    def enrich(terms, target, cache):
        assert set(terms) == {"Climate change", "Marine heatwaves", "fisheries"}
        return [{"term": term, "wikipedia_url": "https://en.wikipedia.org/wiki/" + term.replace(" ", "_"),
                 "description_html": '<p>A supplementary Wikipedia description.</p>', "wikidata_id": ""} for term in terms]

    monkeypatch.setattr(corpus, "extract_document", extract)
    monkeypatch.setattr(corpus, "enrich_terms", enrich)
    monkeypatch.setattr(corpus, "version", lambda name: "test-model-version")
    return tmp_path


def test_all_approved_documents_feed_terms_while_wikipedia_remains_supplementary(approved_corpus):
    root = approved_corpus
    original = {p: p.read_bytes() for p in approved_paths(root)}
    artifact = corpus.build_corpus(root)
    assert artifact["provenance"]["source_policy"] == POLICY
    assert artifact["provenance"]["wikipedia_requested"] is True
    assert artifact["summary"]["source_files_processed"] == 3
    assert artifact["summary"]["research_papers_processed"] == 1
    records = {c["canonical_name"]: c for c in artifact["concepts"]}
    assert records["Climate change"]["description"] == "A persistent change in climate."
    assert records["Climate change"]["wikipedia_description"] == "A supplementary Wikipedia description."
    assert records["Marine heatwaves"]["description_source"] == "Wikipedia"
    assert records["Marine heatwaves"]["wikipedia_url"]
    assert records["Marine heatwaves"]["term_sources"][0]["source_file"] == "data/raw/PMC123.xml"
    assert any(p["url"] == "/paper/PMC123" for p in records["Marine heatwaves"]["source_excerpts"])
    assert {s["source_file"] for s in artifact["provenance"]["sources"]} == {p.relative_to(root).as_posix() for p in original}
    for path, content in original.items():
        assert path.read_bytes() == content
    publication = (root / "encyclopedia_assets/generated/ipcc_encyclopedia.html").read_text(encoding="utf-8")
    assert 'https://en.wikipedia.org/wiki/' in publication
    assert '/paper/PMC123' in publication
    assert 'Unapproved reference-list phrase' not in publication


def test_missing_source_or_failed_enrichment_keeps_installed_vocabulary(approved_corpus, monkeypatch):
    root = approved_corpus
    target = root / "backend/generated_artifacts/encyclopedia_concepts.json"
    corpus.build_corpus(root)
    previous = target.read_bytes()
    monkeypatch.setattr(corpus, "enrich_terms", lambda *args: (_ for _ in ()).throw(RuntimeError("lookup failed")))
    with pytest.raises(RuntimeError, match="lookup failed"):
        corpus.build_corpus(root)
    assert target.read_bytes() == previous
    (root / "data/raw/PMC123.xml").unlink()
    with pytest.raises(FileNotFoundError):
        corpus.build_corpus(root)
    assert target.read_bytes() == previous


def test_changed_paper_and_unapproved_term_provenance_are_rejected(approved_corpus, monkeypatch):
    root = approved_corpus
    artifact = corpus.build_corpus(root)
    target = root / "backend/generated_artifacts/encyclopedia_concepts.json"
    repository = service.settings()[1]
    monkeypatch.setattr(service, "ROOT", root)
    monkeypatch.setattr(service, "settings", lambda: ("generated", repository, approved_paths(root)))
    monkeypatch.setattr(service, "source_path", lambda: root / "data/raw/report.html")
    monkeypatch.setattr(service, "glossary_path", lambda: root / "data/raw/glossary.html")
    assert service.source_concepts(target)
    artifact["concepts"][0]["term_sources"][0]["source_file"] = "outside.html"
    target.write_text(json.dumps(artifact), encoding="utf-8")
    with pytest.raises(ValueError, match="unapproved"):
        service.source_concepts(target)
    artifact = corpus.build_corpus(root)
    paper = root / "data/raw/PMC123.xml"
    paper.write_bytes(paper.read_bytes() + b'\n')
    with pytest.raises(ValueError, match="stale"):
        service.source_concepts(target)


def test_explicit_allowlist_does_not_scan_unlisted_files_or_references(approved_corpus):
    documents = load_documents(approved_corpus)
    assert len(documents) == 3
    assert documents[-1].source_file == "data/raw/PMC123.xml"
    assert "Unapproved reference-list phrase" not in documents[-1].content
    assert "Unlisted paper" not in " ".join(d.content for d in documents)
    with (approved_corpus / "config.toml").open("a", encoding="utf-8") as stream:
        stream.write('\n')
    assert all(path.is_relative_to(approved_corpus / "data/raw") for path in approved_paths(approved_corpus))


def test_model_terms_must_occur_in_the_document_and_cached_wordlists_are_validated(approved_corpus, monkeypatch):
    from backend.encyclopedia import pipeline

    root = approved_corpus
    document = load_documents(root)[-1]
    cache = root / "tmp/validated-extraction"
    cache.mkdir(parents=True)
    calls = []

    def extract(source, output, **options):
        calls.append(source)
        output.mkdir(parents=True)
        wordlist, prepared = output / "wordlist.csv", output / "source.txt"
        wordlist.write_text('term,count,selected\nMarine heatwaves,3,Yes\nUnseen fish myth,2,Yes\n', encoding="utf-8")
        prepared.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
        return ["Marine heatwaves", "Unseen fish myth"], wordlist, prepared

    monkeypatch.setattr(pipeline, "extract_report_wordlist", extract)
    terms, directory = extract_document(document, root, cache, {})
    assert terms == ["Marine heatwaves"]
    assert extract_document(document, root, cache, {})[0] == terms
    assert len(calls) == 1
    (directory / "wordlist.csv").write_text("Changed cached wordlist", encoding="utf-8")
    assert extract_document(document, root, cache, {})[0] == terms
    assert len(calls) == 2
    marker = directory / "source.json"
    saved = json.loads(marker.read_text(encoding="utf-8"))
    saved["accepted_terms"].append("Unseen fish myth")
    marker.write_text(json.dumps(saved), encoding="utf-8")
    assert extract_document(document, root, cache, {})[0] == terms
    assert len(calls) == 3


def test_wikipedia_identity_normalization_retains_all_document_origins(approved_corpus, monkeypatch):
    root = approved_corpus

    def extract(document, root, cache, config):
        directory = cache / Path(document.source_file).stem
        directory.mkdir(parents=True, exist_ok=True)
        terms = {"ipcc_report": ["Climate change", "coastal fisheries"],
                 "ipcc_glossary": ["Climate change"],
                 "research_article": ["Marine heatwaves", "fisheries"]}[document.kind]
        return terms, directory

    def enrich(terms, target, cache):
        return [{"term": term, "wikipedia_url": "https://en.wikipedia.org/wiki/" + (
                    "Fishery" if 'fisheries' in term else term.replace(' ', '_')),
                 "wikidata_id": "Q123" if 'fisheries' in term else None,
                 "description_html": '<p>Supplementary Wikipedia text.</p>'} for term in terms]

    monkeypatch.setattr(corpus, "extract_document", extract)
    monkeypatch.setattr(corpus, "enrich_terms", enrich)
    artifact = corpus.build_corpus(root)
    fisheries = [c for c in artifact["concepts"] if c.get("wikidata_id") == "Q123"]
    assert len(fisheries) == 1
    assert {p["source_file"] for p in fisheries[0]["term_sources"]} == {"data/raw/report.html", "data/raw/PMC123.xml"}
    assert fisheries[0]["description_source"] == "Wikipedia"
    assert fisheries[0]["wikipedia_url"] == "https://en.wikipedia.org/wiki/Fishery"


def test_existing_wikipedia_helper_and_explicit_refresh_remain_available(tmp_path, monkeypatch):
    from encyclopedia.pipeline import query_to_encyclopedia
    from lxml import html

    cache = tmp_path / "cache"
    cache.mkdir()
    calls = []

    def create(terms, title, output, **options):
        assert options == {"add_wikipedia": True}
        calls.append(terms)
        return SimpleNamespace(entries=[{"term": terms[0], "search_term": terms[0],
            "wikipedia_url": "https://en.wikipedia.org/wiki/Marine_heatwave", "wikidata_id": "Q123",
            "description_html": f'<p>Wikipedia description {len(calls)}.</p>', "content_note": "",
            "figure_html": html.Element("figure")}])

    monkeypatch.setattr(query_to_encyclopedia, "create_encyclopedia_from_terms", create)
    first = corpus.enrich_terms(["Marine heatwaves"], tmp_path / "absent.json", cache)
    second = corpus.enrich_terms(["Marine heatwaves"], tmp_path / "absent.json", cache)
    assert first == second and len(calls) == 1
    refreshed = corpus.enrich_terms(["Marine heatwaves"], tmp_path / "absent.json", cache, refresh=True)
    assert len(calls) == 2
    assert refreshed[0]["description_html"] == '<p>Wikipedia description 2.</p>'
    assert refreshed[0]["wikidata_id"] == "Q123"


def test_explicit_legacy_no_wikipedia_option_does_not_change_primary_sources(approved_corpus, monkeypatch):
    from encyclopedia.pipeline import query_to_encyclopedia

    def create(terms, title, output, **options):
        assert options == {"add_wikipedia": False}
        return SimpleNamespace(entries=[{"term": term} for term in terms])

    monkeypatch.setattr(query_to_encyclopedia, "create_encyclopedia_from_terms", create)
    artifact = corpus.build_corpus(approved_corpus, add_wikipedia=False)
    assert artifact['summary']['source_files_processed'] == 3
    assert artifact['summary']['research_papers_processed'] == 1
    assert artifact['provenance']['wikipedia_requested'] is False
    assert not any(c.get('wikipedia_url') for c in artifact['concepts'])
    assert artifact['summary']['concepts_with_ipcc_definitions'] == 1


def test_source_defined_acronym_does_not_publish_an_unrelated_wikipedia_entity(approved_corpus, monkeypatch):
    root = approved_corpus
    paper = root / 'data/raw/PMC123.xml'
    paper.write_text(paper.read_text(encoding='utf-8').replace('<p>', '<p>Ocean heat content (OHC) is measured. '), encoding='utf-8')

    def extract(document, root, cache, config):
        directory = cache / Path(document.source_file).stem
        directory.mkdir(parents=True, exist_ok=True)
        # The real corpus extracts both the source's full name and its acronym.
        return (["OHC", "Ocean heat content", "Marine heatwaves"] if document.kind == 'research_article' else ["Climate change"]), directory

    def enrich(terms, target, cache):
        return [{"term": term, 'wikipedia_url': 'https://en.wikipedia.org/wiki/' + (
                    'Overhead_camshaft_engine' if term == 'OHC' else term.replace(' ', '_')),
                 'wikidata_id': 'Q123' if term == 'OHC' else 'Q456' if term == 'Ocean heat content' else None,
                 'description_html': '<p>A supplementary description.</p>'} for term in terms]

    monkeypatch.setattr(corpus, 'extract_document', extract)
    monkeypatch.setattr(corpus, 'enrich_terms', enrich)
    artifact = corpus.build_corpus(root)
    names = {c['canonical_name'] for c in artifact['concepts']}
    assert 'Ocean heat content' in names
    assert 'Overhead camshaft engine' not in names
    assert any(c.get('wikipedia_url') for c in artifact['concepts'])
    assert artifact['provenance']['wikipedia_requested'] is True
