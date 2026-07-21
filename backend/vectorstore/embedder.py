"""
embedder.py
-----------
Loads the embedding model and generates embeddings.
"""

from sentence_transformers import SentenceTransformer

EMBED_MODEL = "all-MiniLM-L6-v2"

_model = None


def get_model():
    """
    Lazy-load the embedding model.
    """

    global _model

    if _model is None:
        print(f"Loading embedding model ({EMBED_MODEL})...")
        _model = SentenceTransformer(EMBED_MODEL)
        print("Embedding model loaded.")

    return _model


def embed(texts):
    """
    Generate normalized embeddings.

    Accepts:
        list[str]

    Returns:
        list[list[float]]
    """

    model = get_model()
    return model.encode(texts, normalize_embeddings=True).tolist()