"""
concept_graph.py — Places a climate question on the knowledge graph.

For a question it returns:
  - a short explanation written by the local Ollama model from the
    retrieved passages only, citing them as [2.1] (IPCC) or [P1] (paper);
  - the concepts the question touches, to highlight in the corpus-wide
    knowledge graph (see knowledge_graph.py), plus the subgraph that
    links them.

Pipeline (same retrieval as the chatbot):
  1. Retrieve the most relevant chunks from ChromaDB (IPCC AR6 report +
     any ingested research papers).
  2. Find the encyclopedia concepts in the question and those chunks.
  3. Ask Ollama for a cited explanation. If Ollama is unavailable, the
     explanation lists the retrieved sources instead — the graph part
     never depends on the LLM.

Everything is open source and local: ChromaDB (Apache-2.0),
sentence-transformers (Apache-2.0), networkx (BSD-3), Ollama (MIT),
vis-network (Apache-2.0 / MIT).
"""

import logging
import textwrap

import knowledge_graph
from llm.client import OLLAMA_MODEL, ask_llm
from retrieval.citation_parser import extract_citations, strip_ghost_citations
from retrieval.context_builder import assign_citation_keys, build_context
from vectorstore import query_chunks

log = logging.getLogger(__name__)

TOP_K = 6

# ── Prompt ────────────────────────────────────────────────────────────────────
_SYSTEM_PROMPT = textwrap.dedent("""
You are ClimateInsight, a climate-science explainer.
Answer the question using ONLY the source passages below. Do not use outside
knowledge. Each passage starts with its citation ID in square brackets,
e.g. [2.1] or [P1].

Write a clear 3-6 sentence explanation of how the key concepts connect.
Cite every factual claim with the passage ID it comes from, e.g.
"Warming has reached 1.1C [2.1]." If the passages do not cover the
question, say so. Do not mention "passages" or "context".
""").strip()


def _prompt(question: str, context: str, main: list[str]) -> str:
    topic = f"Main topic: {', '.join(main)}. Centre the explanation on it.\n" if main else ""
    return (
        f"{_SYSTEM_PROMPT}\n\nSource passages:\n\n{context}\n\nQuestion: {question}\n{topic}\n"
        "Remember: cite every claim with its passage ID, e.g. [2.1] or [P1].\n"
        "Explanation:"
    )


# ── Sources ───────────────────────────────────────────────────────────────────
def _source_label(chunk: dict) -> str:
    if chunk["ref"].startswith("P"):
        title = chunk.get("citation_label") or chunk.get("document_title") or chunk.get("pmcid")
        section = chunk.get("section_title") or chunk.get("section", "")
        return f"{title}: {section}" if section else title
    title = chunk.get("section_title", "")
    return f"IPCC AR6 {chunk['section']} {title}".strip()


def _sources(chunks: list[dict]) -> list[dict]:
    """One entry per distinct citation ref, in retrieval (best-first) order."""
    seen, out = set(), []
    for c in chunks:
        if c["ref"] in seen:
            continue
        seen.add(c["ref"])
        out.append({
            "ref": c["ref"],
            "label": _source_label(c),
            "section": c.get("section", ""),
            "pmcid": c.get("pmcid", ""),
            "doi": c.get("doi", ""),
            "score": c.get("score"),
        })
    return out


def _fallback_explanation(sources: list[dict]) -> str:
    listing = "; ".join(f'[{s["ref"]}] {s["label"]}' for s in sources)
    return (
        "The local language model is not available, so no written answer was "
        "generated. The highlighted concepts come from the sources most related "
        f"to your question: {listing}."
    )


# ── Public API ────────────────────────────────────────────────────────────────
def generate_concept_graph(question: str) -> dict:
    """
    Returns {
      explanation, source,
      main      : the concept(s) the question is about — the hub of the view,
      focus     : concept ids to highlight in the full knowledge graph,
      subgraph  : {nodes, edges} linking the focus concepts,
      sources   : every passage the answer was built from,
      citations : the subset the explanation cites (same shape as /api/chat),
    }
    """
    chunks = query_chunks(question, top_k=TOP_K)
    assign_citation_keys(chunks)
    sources = _sources(chunks)

    focus = knowledge_graph.focus_concepts(question, chunks)
    main = knowledge_graph.main_concepts(question, focus)
    # Main concepts lead the focus list so they are always highlighted
    focus = main + [c for c in focus if c not in main]

    try:
        explanation = ask_llm(
            _prompt(question, build_context(chunks), main),
            temperature=0.2,
            max_tokens=500,
        )
        if not explanation:
            raise RuntimeError("empty response")
        explanation = strip_ghost_citations(explanation, chunks)
        source = f"Ollama / {OLLAMA_MODEL}"
    except RuntimeError as exc:
        log.warning("Concept graph LLM step failed (%s); listing sources", exc)
        explanation = _fallback_explanation(sources)
        source = "retrieved sources (LLM unavailable)"

    return {
        "explanation": explanation,
        "source": source,
        "main": main,
        "focus": focus,
        "subgraph": knowledge_graph.subgraph(focus),
        "sources": sources,
        "citations": extract_citations(explanation, chunks),
    }


def handle_concept_graph_request(question: str) -> dict:
    question = (question or "").strip()
    if not question:
        raise ValueError("'question' is required.")
    if len(question) > 1000:
        raise ValueError("Question must be 1000 characters or fewer.")
    return generate_concept_graph(question)
