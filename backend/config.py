from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CORPUS_DIR = ROOT / "corpus"
CHROMA_DIR = ROOT / "backend" / "chroma_db"
INDEX_CACHE_DIR = ROOT / "backend" / "index_cache"
COLLECTION_NAME = "paperinsight_v1"

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")

TOP_K_DENSE = int(os.getenv("TOP_K_DENSE", "20"))
TOP_K_LEXICAL = int(os.getenv("TOP_K_LEXICAL", "20"))
TOP_K_FINAL = int(os.getenv("TOP_K_FINAL", "6"))
DENSE_WEIGHT = float(os.getenv("DENSE_WEIGHT", "0.65"))
LEXICAL_WEIGHT = float(os.getenv("LEXICAL_WEIGHT", "0.35"))
RRF_K = int(os.getenv("RRF_K", "60"))
MIN_DENSE_SCORE = float(os.getenv("MIN_DENSE_SCORE", "0.25"))
MIN_HYBRID_SCORE = float(os.getenv("MIN_HYBRID_SCORE", "0.20"))
TEMPERATURE = float(os.getenv("TEMPERATURE", "0.1"))
MAX_NEW_TOKENS = int(os.getenv("MAX_NEW_TOKENS", "700"))
