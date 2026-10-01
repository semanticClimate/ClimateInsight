"""Tests for the no-relevant-context path in the RAG pipeline."""

from retrieval import pipeline


def test_pipeline_does_not_call_llm_when_no_chunks_are_relevant(monkeypatch):
    monkeypatch.setattr(pipeline, "query_chunks", lambda question, top_k: [])

    def fail_if_called(prompt):
        raise AssertionError("The LLM must not run without relevant chunks")

    monkeypatch.setattr(pipeline, "ask_ollama", fail_if_called)

    assert pipeline.answer_question("unrelated question", "session-1") is None
