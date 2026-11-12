"""Regression checks for package moves and working-directory-independent paths."""

from pathlib import Path
import runpy
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock
from fastapi.testclient import TestClient

import pytest

from backend.core import paths
from backend.encyclopedia import importer


def test_source_and_database_locations_survive_a_different_working_directory(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    expected_root = Path(__file__).resolve().parents[2]
    assert paths.PROJECT_ROOT == expected_root
    assert (paths.FRONTEND_DIR / "index.html").is_file()
    assert (paths.RAW_DATA_DIR / "ipcc_reference.html").is_file()
    assert len(list(paths.PAPERS_DIR.glob("*.xml"))) == 12
    assert paths.GENERATED_CONCEPTS.is_file()
    assert paths.CHROMA_DIR == expected_root / "backend/chroma_db"


def test_importer_still_defaults_to_the_installed_vocabulary(monkeypatch, tmp_path):
    written = []
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["importer", "export.html"])
    monkeypatch.setattr(importer, "build_normalized_vocabulary", lambda *args: ({"summary": {}}, {}))
    monkeypatch.setattr(importer, "write_artifact", lambda artifact, output: written.append(output))
    importer.main()
    assert written == [paths.GENERATED_CONCEPTS]


@pytest.mark.parametrize("directory", [paths.PROJECT_ROOT, paths.PROJECT_ROOT / "backend"])
def test_original_app_script_launch_styles_still_start_the_same_server(monkeypatch, directory):
    routes = ModuleType("backend.api.routes")
    run = Mock()
    routes.app = SimpleNamespace()
    monkeypatch.setattr("uvicorn.run", run)
    monkeypatch.setitem(sys.modules, "backend.api.routes", routes)
    monkeypatch.setattr(sys, "path", sys.path.copy())
    monkeypatch.setenv("PORT", "5112")
    monkeypatch.setenv("HOST", "127.0.0.1")
    monkeypatch.setenv("DEV", "0")
    monkeypatch.chdir(directory)
    runpy.run_path(str(paths.PROJECT_ROOT / "backend/app.py"), run_name="__main__")
    run.assert_called_once_with(
        "backend.api.routes:app", host="127.0.0.1", port=5112, reload=False, log_level="info",
    )


def test_chat_still_connects_retrieval_generation_citations_and_session_history(monkeypatch):
    from backend.api import routes
    from backend.retrieval import pipeline

    question = "What does the study say about marine heatwaves?"
    source_text = "The study describes marine heatwaves and climate variability."
    chunk = {
        "text": source_text, "section": "results", "section_title": "Results",
        "document_title": "Example study", "source_type": "research_article",
        "pmcid": "PMC123", "doi": "10.example/study",
    }
    queries, prompts, saved = [], [], []

    def retrieve(text, top_k):
        queries.append((text, top_k))
        return [dict(chunk)]

    def answer(prompt):
        prompts.append(prompt)
        return "The study describes marine heatwaves [P1]."

    monkeypatch.setattr(pipeline, "query_chunks", retrieve)
    monkeypatch.setattr(pipeline, "get_history", lambda session: [])
    monkeypatch.setattr(pipeline, "ask_ollama", answer)
    monkeypatch.setattr(routes, "add_to_history", lambda *args: saved.append(args))
    response = TestClient(routes.app).post(
        "/api/chat", json={"question": question, "session_id": "structure-check"},
    )

    assert response.status_code == 200
    data = response.json()
    assert queries == [(question, 6)]
    assert len(prompts) == 1 and source_text in prompts[0] and question in prompts[0]
    assert data["session_id"] == "structure-check"
    assert data["citations"][0]["ref"] == "P1"
    assert data["citations"][0]["text"] == source_text
    assert data["references"][0]["pmcid"] == "PMC123"
    assert saved == [
        ("structure-check", "user", question),
        ("structure-check", "assistant", data["answer"]),
    ]
