from __future__ import annotations

from .citations import extractive_fallback, validate_citations
from .hybrid import retrieve
from .prompts import build_prompt
from ..llm import ask_ollama


def answer_question(question: str) -> dict:
    evidence = retrieve(question)
    evidence_dicts = [e.as_dict() for e in evidence]
    if not evidence_dicts:
        return {
            "answer": "I couldn't find enough evidence in the 12 indexed papers to answer that.",
            "citations": [],
        }

    prompt = build_prompt(question, evidence_dicts)
    raw = ask_ollama(prompt)
    answer, citations = validate_citations(raw, evidence_dicts)

    if not citations:
        answer, citations = extractive_fallback(question, evidence_dicts)

    # Return citations only from validated retrieved evidence.
    return {
        "answer": answer,
        "citations": citations,
    }
