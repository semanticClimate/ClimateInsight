"""Check the live paper exports without opening ChromaDB or calling an LLM."""

import importlib.util
from contextlib import redirect_stdout
import io
from pathlib import Path
import sys
from types import ModuleType
from urllib.parse import urljoin, urlsplit
import xml.etree.ElementTree as ET

from bs4 import BeautifulSoup
from fastapi.testclient import TestClient
import pytest

from backend.ingest.loader_registry import discover_documents
from backend.ingest.pipeline import build_chunks_from_directory
from backend.ingest.xml_parser import parse_xml


ROOT = Path(__file__).resolve().parents[2]
PAPERS = ROOT / "data/raw/ocean_heatwaves_2026"


@pytest.fixture
def paper_app(monkeypatch):
    # Routing checks must not start Redis, load an embedding model, or open Chroma.
    for name, attributes in {
        "backend.retrieval": ["answer_question"],
        "backend.core.sessions": ["add_to_history", "clear_history"],
        "backend.knowledge_graph.question": ["handle_concept_graph_request"],
        "backend.api.responses": ["chat_response", "error_response", "health_response", "message_response"],
    }.items():
        module = ModuleType(name)
        for attribute in attributes:
            setattr(module, attribute, lambda *args, **kwargs: {})
        monkeypatch.setitem(sys.modules, name, module)
    spec = importlib.util.spec_from_file_location("paper_sources_test_app", ROOT / "backend/api/routes.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_live_paper_pairs_ingest_only_xml_with_correct_metadata():
    xml_files = sorted(PAPERS.glob("*.xml"))
    assert len(xml_files) == 12
    assert {p.stem for p in xml_files} == {p.stem for p in PAPERS.glob("*.html")}
    assert discover_documents(PAPERS) == xml_files

    chunks = build_chunks_from_directory(PAPERS, chunk_size=400, overlap=50)
    assert len({c.chunk_id for c in chunks}) == len(chunks)
    assert {c.pmcid for c in chunks} == {p.stem for p in xml_files}
    for path in xml_files:
        article_meta = ET.parse(path).getroot().find("front/article-meta")
        doi = article_meta.find("article-id[@pub-id-type='doi']").text
        paper_chunks = [c for c in chunks if c.pmcid == path.stem]
        assert len(paper_chunks) > 1
        assert all(c.doi == doi and c.source_type == "research_article" for c in paper_chunks)
        assert all(Path(c.source_path) == path.resolve() for c in paper_chunks)
    bay_of_bengal = " ".join(c.text for c in chunks if c.pmcid == "PMC10468509")
    assert "CO2" in bay_of_bengal
    assert "imax" in bay_of_bengal


@pytest.mark.parametrize("path", sorted(PAPERS.glob("*.html")), ids=lambda p: p.stem)
def test_paper_routes_serve_exports_unchanged(paper_app, path):
    client = TestClient(paper_app.app)
    for paper_id in (path.stem, path.stem.removeprefix("PMC")):
        response = client.get(f"/paper/{paper_id}")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/html")
        assert response.content == path.read_bytes()


def test_local_paper_images_resolve_from_the_display_url(paper_app):
    client = TestClient(paper_app.app)
    checked = 0
    for path in PAPERS.glob("*.html"):
        soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
        for tag in soup.find_all(["img", "script"], src=True):
            src = tag["src"]
            if urlsplit(src).scheme or src.startswith("//"):
                continue
            image_url = urljoin(f"/paper/{path.stem.removeprefix('PMC')}", src)
            response = client.get(image_url)
            assert response.status_code == 200, image_url
            assert response.content == (PAPERS / src).read_bytes()
            checked += 1
    assert checked == 13


def test_numeric_html_exports_remain_supported(paper_app, monkeypatch, tmp_path):
    source = tmp_path / "123.html"
    source.write_text("<p>Legacy paper export</p>", encoding="utf-8")
    monkeypatch.setattr(paper_app, "_PAPERS_DIR", tmp_path)
    client = TestClient(paper_app.app)
    assert client.get("/paper/123").content == source.read_bytes()
    assert client.get("/paper/PMC123").content == source.read_bytes()
    assert client.get("/paper/not-a-paper").status_code == 404
    assert client.get("/paper/PMC123_assets/../123.html").status_code == 404
    assert client.get("/paper/review/review_table.edited.json").status_code == 404


def test_scientific_values_survive_xml_extraction(tmp_path):
    path = tmp_path / "PMC123.xml"
    source = """<article><front><article-meta>
      <article-id pub-id-type="pmcid">PMC123</article-id>
      <title-group><article-title>Heat flux observations</article-title></title-group>
    </article-meta></front><body><sec><title>Results</title>
      <p>Carbon dioxide CO<sub>2</sub> increased while heat flux reached
      15 W m<sup>−2</sup> during the observed event
      <sup><xref ref-type="bibr" rid="ref999">999</xref></sup>.</p>
    </sec></body></article>"""
    path.write_text(source, encoding="utf-8")
    sections = parse_xml(path)
    assert len(sections) == 1
    assert "CO2" in sections[0].text
    assert "m−2" in sections[0].text
    assert "999" not in sections[0].text
    assert path.read_text(encoding="utf-8") == source


def test_windows_console_does_not_make_valid_xml_fail():
    with io.TextIOWrapper(io.BytesIO(), encoding="cp1252", errors="strict") as output:
        with redirect_stdout(output):
            sections = parse_xml(PAPERS / "PMC10468509.xml")
        output.flush()
    assert sections
    assert all(s.pmcid == "PMC10468509" for s in sections)


def test_ingestion_fails_when_every_document_has_no_usable_text(tmp_path):
    (tmp_path / "PMC123.xml").write_text("<article/>", encoding="utf-8")
    with pytest.raises(RuntimeError, match="No usable text"):
        build_chunks_from_directory(tmp_path, chunk_size=400, overlap=50)
