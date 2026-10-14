from __future__ import annotations


def build_prompt(question: str, evidence: list[dict]) -> str:
    context_parts = []
    for e in evidence:
        path = " > ".join(e.get("section_path", []))
        context_parts.append(
            f"[{e['citation_key']}]\n"
            f"Paper: {e['title']}\n"
            f"PMCID: {e['pmcid']}\n"
            f"Section: {path}\n"
            f"Passage: {e['text']}"
        )
    context = "\n\n---\n\n".join(context_parts)
    return f"""You are a research-paper reading assistant. Answer the user's question using ONLY the supplied evidence passages.

Rules:
- Do not use outside knowledge.
- Do not invent paper titles, section names, numbers, or results.
- Be explicit when the evidence is insufficient.
- Put one or more citation handles like [C1] or [C2] immediately after the sentence they support.
- Citation handles must come ONLY from the supplied evidence handles.
- Never cite a paper merely because it is topically related; cite it only when its passage supports the statement.
- Do not output a references list. The application will build the citation chips from the handles.
- Prefer precise, compact explanations over long summaries.

Evidence:
{context}

Question:
{question}

Answer:
"""
