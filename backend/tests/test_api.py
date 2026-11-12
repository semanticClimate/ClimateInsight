"""Exercise FastAPI HTTP behavior without a model, Redis or a live vector store."""

import importlib.util
import sys
from types import ModuleType, SimpleNamespace

from fastapi.testclient import TestClient
import pytest

from backend.core.paths import PROJECT_ROOT


@pytest.fixture
def routes(monkeypatch):
    for name, attributes in {
        "backend.retrieval": ["answer_question"],
        "backend.core.sessions": ["add_to_history", "clear_history"],
        "backend.knowledge_graph.question": ["handle_concept_graph_request"],
    }.items():
        module = ModuleType(name)
        for attribute in attributes:
            setattr(module, attribute, lambda *args, **kwargs: None)
        monkeypatch.setitem(sys.modules, name, module)
    spec = importlib.util.spec_from_file_location("fastapi_routes_test", PROJECT_ROOT / "backend/api/routes.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_health_config_frontend_and_static_files(routes):
    with TestClient(routes.app) as client:
        assert client.get("/api/health").json() == {"status": "ok"}
        assert client.get("/api/config").json()["backend"]["framework"] == "FastAPI"
        for url in ("/", "/concept-graph", "/css/tokens.css", "/js/api.js", "/frontend/js/api.js", "/report-styles"):
            assert client.get(url).status_code == 200, url
        missing = client.get("/api/unknown")
        assert missing.status_code == 404
        assert missing.json() == {"error": "API route not found", "path": "/api/unknown"}


def test_chat_preserves_response_and_session_history(routes, monkeypatch):
    saved = []
    monkeypatch.setattr(routes, "answer_question", lambda question, session: {
        "answer": f"Answer to {question}",
        "citations": [{"ref": "P1", "doi": "10.example/paper", "pmcid": "PMC123"}],
    })
    monkeypatch.setattr(routes, "add_to_history", lambda *args: saved.append(args))
    response = TestClient(routes.app).post("/api/chat", json={"question": "  Warming?  ", "session_id": "s1"})
    assert response.status_code == 200
    assert response.json()["answer"] == "Answer to Warming?"
    assert response.json()["references"][0]["url"] == "https://doi.org/10.example/paper"
    assert saved == [("s1", "user", "Warming?"), ("s1", "assistant", "Answer to Warming?")]


@pytest.mark.parametrize("body", [{}, {"question": " "}, {"question": 12}, [], {"question": "Warming?", "session_id": 12}])
def test_bad_chat_requests_return_json_errors(routes, body):
    response = TestClient(routes.app).post("/api/chat", json=body)
    assert response.status_code == 400
    assert "error" in response.json()


def test_malformed_json_and_unavailable_chat_return_errors(routes, monkeypatch):
    client = TestClient(routes.app)
    assert client.post("/api/chat", content="{", headers={"Content-Type": "application/json"}).status_code == 400
    def unavailable(*args):
        raise RuntimeError("Ollama unavailable")
    monkeypatch.setattr(routes, "answer_question", unavailable)
    response = client.post("/api/chat", json={"question": "Warming?"})
    assert response.status_code == 503
    assert response.json() == {"error": "Ollama unavailable"}


def test_graph_query_parameters_and_session_path_parameters(routes, monkeypatch):
    monkeypatch.setattr(routes, "get_graph", lambda: {"nodes": [], "edges": []})
    monkeypatch.setattr(routes, "concept_resources", lambda concept: {"concept": concept})
    monkeypatch.setattr(routes, "link_resources", lambda a, b: {"from": a, "to": b})
    cleared = []
    monkeypatch.setattr(routes, "clear_history", cleared.append)
    client = TestClient(routes.app)
    assert client.get("/api/knowledge-graph").json() == {"nodes": [], "edges": []}
    assert client.get("/api/knowledge-graph/concept", params={"id": "Ocean warming"}).json() == {"concept": "Ocean warming"}
    assert client.get("/api/knowledge-graph/link", params={"a": "Ocean warming", "b": "Coral reefs"}).json() == {
        "from": "Ocean warming", "to": "Coral reefs",
    }
    assert client.delete("/api/session/session-1").json() == {"message": "Session cleared"}
    assert cleared == ["session-1"]


@pytest.mark.parametrize("exception,status", [(ValueError("question required"), 400), (RuntimeError("Unavailable"), 503), (Exception("unexpected"), 500)])
def test_concept_graph_error_statuses(routes, monkeypatch, exception, status):
    def fail(question):
        raise exception
    monkeypatch.setattr(routes, "handle_concept_graph_request", fail)
    response = TestClient(routes.app).post("/api/concept-graph", json={"question": "Warming?"})
    assert response.status_code == status
    assert "error" in response.json()


def test_ipcc_document_links_resolve_and_unknown_documents_do_not_fall_back(routes, monkeypatch, tmp_path):
    default = tmp_path / "ipcc_reference.html"
    default.write_text('<html><p id="syr-p1">SYR</p></html>', encoding="utf-8")
    chapter_dir = tmp_path / "ipcc"
    chapter_dir.mkdir()
    chapter = chapter_dir / "wg1_Chapter01.html"
    chapter.write_text('<html><p id="wg1-p1">WG I</p></html>', encoding="utf-8")
    monkeypatch.setattr(routes, "RAW_DATA_DIR", tmp_path)
    monkeypatch.setattr(routes, "render_report", lambda report: report)
    client = TestClient(routes.app)
    assert client.get("/ipcc-reference").text == default.read_text(encoding="utf-8")
    assert client.get("/ipcc-reference", params={"doc": "wg1_Chapter01"}).text == chapter.read_text(encoding="utf-8")
    for doc in ("missing", "../ipcc_reference", "..\\ipcc_reference"):
        assert client.get("/ipcc-reference", params={"doc": doc}).status_code == 404
    duplicate = tmp_path / "wg1_Chapter01.html"
    duplicate.write_text("another chapter", encoding="utf-8")
    assert client.get("/ipcc-reference", params={"doc": "wg1_Chapter01"}).status_code == 409


def test_image_proxy_streams_bytes_and_closes_upstream(routes, monkeypatch):
    closed = []
    monkeypatch.setattr(routes.http_requests, "get", lambda *args, **kwargs: SimpleNamespace(
        status_code=200, headers={"Content-Type": "image/png"},
        iter_content=lambda chunk_size: iter([b"image", b"data"]), close=lambda: closed.append(True),
    ))
    response = TestClient(routes.app).get("/ipcc-image-proxy/content/image.png")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.content == b"imagedata"
    assert closed == [True]


def test_cors_preflight_is_supported(routes):
    response = TestClient(routes.app).options("/api/chat", headers={
        "Origin": "http://localhost:3000", "Access-Control-Request-Method": "POST",
    })
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "*"
