"""Tests that Chroma IDs survive retrieval for citation scoping."""

from vectorstore import retriever


class _FakeCollection:
    def count(self):
        return 2

    def query(self, **kwargs):
        assert kwargs["n_results"] == 2
        return {
            "ids": [["paper-a__introduction__chunk_0", "paper-b__introduction__chunk_0"]],
            "documents": [["Paper A text", "Paper B text"]],
            "metadatas": [[
                {"section": "introduction", "pmcid": "PMC-A"},
                {"section": "introduction", "pmcid": "PMC-B"},
            ]],
            "distances": [[0.1, 0.2]],
        }


def test_query_chunks_preserves_globally_unique_chroma_ids(monkeypatch):
    monkeypatch.setattr(retriever, "get_collection", lambda: _FakeCollection())
    monkeypatch.setattr(retriever, "embed", lambda texts: [[0.0, 1.0]])

    chunks = retriever.query_chunks("question", top_k=2)

    assert [chunk["chunk_id"] for chunk in chunks] == [
        "paper-a__introduction__chunk_0",
        "paper-b__introduction__chunk_0",
    ]
    assert chunks[0]["section"] == chunks[1]["section"] == "introduction"
    assert chunks[0]["pmcid"] == "PMC-A"
    assert chunks[1]["pmcid"] == "PMC-B"
