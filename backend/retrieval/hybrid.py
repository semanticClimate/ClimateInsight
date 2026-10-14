from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

from ..config import (
    DENSE_WEIGHT, LEXICAL_WEIGHT, MIN_DENSE_SCORE, MIN_HYBRID_SCORE,
    RRF_K, TOP_K_DENSE, TOP_K_FINAL, TOP_K_LEXICAL, INDEX_CACHE_DIR,
)
from ..vectorstore.chroma_store import get_collection
from ..vectorstore.embeddings import embed_texts

TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_\-]+")
_STOP = {
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "with", "is", "are",
    "was", "were", "be", "by", "from", "that", "this", "what", "how", "does", "do",
}


@dataclass
class Evidence:
    citation_key: str
    chunk_id: str
    pmcid: str
    doi: str
    title: str
    section_title: str
    section_path: list[str]
    text: str
    score: float
    dense_score: float
    lexical_score: float

    def as_dict(self) -> dict:
        return {
            "citation_key": self.citation_key,
            "chunk_id": self.chunk_id,
            "pmcid": self.pmcid,
            "doi": self.doi,
            "title": self.title,
            "section_title": self.section_title,
            "section_path": self.section_path,
            "text": self.text,
            "score": round(self.score, 4),
            "dense_score": round(self.dense_score, 4),
            "lexical_score": round(self.lexical_score, 4),
            "pmc_url": f"https://europepmc.org/articles/{self.pmcid}" if self.pmcid else "",
            "doi_url": f"https://doi.org/{self.doi}" if self.doi else "",
        }


def _load_lexical_index():
    payload_path = INDEX_CACHE_DIR / "chunks.json"
    if not payload_path.exists():
        raise RuntimeError("Index not built. Run: python -m backend.ingest.build_index")
    data = json.loads(payload_path.read_text(encoding="utf-8"))
    docs = [x["text"] for x in data]
    vectorizer = TfidfVectorizer(lowercase=True, stop_words="english", ngram_range=(1, 2), sublinear_tf=True)
    matrix = vectorizer.fit_transform(docs)
    return data, vectorizer, matrix


_lex_cache = None


def _lexical_search(question: str, k: int):
    global _lex_cache
    if _lex_cache is None:
        _lex_cache = _load_lexical_index()
    data, vectorizer, matrix = _lex_cache
    q = vectorizer.transform([question])
    scores = (matrix @ q.T).toarray().ravel()
    order = np.argsort(-scores)[:k]
    return [(int(i), float(scores[i])) for i in order if scores[i] > 0]


def _dense_search(question: str, k: int):
    collection = get_collection()
    if collection.count() == 0:
        raise RuntimeError("Chroma collection is empty. Run ingestion first.")
    q_emb = embed_texts([question])[0]
    result = collection.query(
        query_embeddings=[q_emb],
        n_results=min(k, collection.count()),
        include=["documents", "metadatas", "distances"],
    )
    out = []
    ids = result["ids"][0]
    docs = result["documents"][0]
    metas = result["metadatas"][0]
    dists = result["distances"][0]
    for rank, (cid, doc, meta, dist) in enumerate(zip(ids, docs, metas, dists), start=1):
        score = max(0.0, 1.0 - float(dist))
        out.append((cid, doc, meta, score, rank))
    return out


def retrieve(question: str, top_k: int = TOP_K_FINAL) -> list[Evidence]:
    data = _lexical_search_data()[0]
    lexical = _lexical_search(question, TOP_K_LEXICAL)
    dense = _dense_search(question, TOP_K_DENSE)

    dense_by_id = {cid: (doc, meta, score, rank) for cid, doc, meta, score, rank in dense}
    lexical_by_idx = {idx: (score, rank) for rank, (idx, score) in enumerate(lexical, start=1)}
    id_to_idx = {item["chunk_id"]: i for i, item in enumerate(data)}

    candidates = set(dense_by_id)
    candidates.update(data[i]["chunk_id"] for i in lexical_by_idx)

    fused = []
    for cid in candidates:
        dense_score, dense_rank = 0.0, None
        lexical_score, lexical_rank = 0.0, None
        if cid in dense_by_id:
            _doc, _meta, dense_score, dense_rank = dense_by_id[cid]
        idx = id_to_idx.get(cid)
        if idx in lexical_by_idx:
            lexical_score, lexical_rank = lexical_by_idx[idx]
        rrf = 0.0
        if dense_rank is not None:
            rrf += DENSE_WEIGHT / (RRF_K + dense_rank)
        if lexical_rank is not None:
            rrf += LEXICAL_WEIGHT / (RRF_K + lexical_rank)
        hybrid_score = rrf * 100.0
        fused.append((cid, hybrid_score, dense_score, lexical_score))

    fused.sort(key=lambda x: x[1], reverse=True)

    selected: list[Evidence] = []
    paper_counts: dict[str, int] = {}
    max_per_paper = 3
    for cid, hybrid_score, dense_score, lexical_score in fused:
        if len(selected) >= top_k:
            break
        idx = id_to_idx[cid]
        item = data[idx]
        if dense_score and dense_score < MIN_DENSE_SCORE and lexical_score <= 0:
            continue
        if hybrid_score < MIN_HYBRID_SCORE and dense_score < MIN_DENSE_SCORE:
            continue
        pmcid = item["pmcid"]
        if paper_counts.get(pmcid, 0) >= max_per_paper:
            continue
        paper_counts[pmcid] = paper_counts.get(pmcid, 0) + 1
        selected.append(Evidence(
            citation_key=f"C{len(selected)+1}",
            chunk_id=item["chunk_id"],
            pmcid=pmcid,
            doi=item.get("doi", ""),
            title=item.get("title", ""),
            section_title=item.get("section_title", ""),
            section_path=item.get("section_path", []),
            text=item["text"],
            score=hybrid_score,
            dense_score=dense_score,
            lexical_score=lexical_score,
        ))
    return selected


def _lexical_search_data():
    global _lex_cache
    if _lex_cache is None:
        _lex_cache = _load_lexical_index()
    return _lex_cache
