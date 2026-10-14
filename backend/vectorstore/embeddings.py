from __future__ import annotations

from sentence_transformers import SentenceTransformer

from ..config import EMBEDDING_MODEL

_model = None


def get_model():
    global _model
    if _model is None:
        print(f"Loading embedding model: {EMBEDDING_MODEL}")
        _model = SentenceTransformer(EMBEDDING_MODEL)
    return _model


def embed_texts(texts: list[str]) -> list[list[float]]:
    return get_model().encode(texts, normalize_embeddings=True, show_progress_bar=False).tolist()
