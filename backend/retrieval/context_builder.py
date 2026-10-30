def _is_paper(chunk: dict) -> bool:
    return bool(
        chunk.get("pmcid")
        or chunk.get("source_id")
        or chunk.get("source_type") == "research_article"
    )


def assign_citation_keys(chunks: list[dict]) -> list[dict]:
    """
    Give every retrieved chunk a citation key ("ref") that is unique within
    this answer, so the LLM's [ref] markers map back to exactly one source.

    IPCC section IDs (e.g. "2.1.2") are already unique across the report, so
    they are kept as-is; repeated chunks of the same section share the key.
    Paper section slugs ("introduction", "results", ...) repeat across papers,
    so each paper chunk gets a short per-answer key instead: P1, P2, ...
    """
    paper_n = 0
    for chunk in chunks:
        if _is_paper(chunk):
            paper_n += 1
            chunk["ref"] = f"P{paper_n}"
        else:
            chunk["ref"] = chunk.get("section", "")
    return chunks


def build_context(chunks: list[dict]) -> str:
    """
    Convert retrieved chunks into the context block given to the LLM.

    Each passage starts with its citation key from assign_citation_keys(),
    e.g. [2.1] for IPCC sections or [P1] for research-paper passages.
    When a citation_label is present (e.g. "Chen et al. 2024"), it is
    prepended so the LLM can reference the source naturally.
    """
    parts = []
    for chunk in chunks:
        ref = chunk.get("ref") or chunk.get("section", "")
        text = chunk.get("text", "")
        label = chunk.get("citation_label") or chunk.get("document_title", "")
        if label and _is_paper(chunk):
            parts.append(f"[{ref}] ({label}) {text}")
        else:
            parts.append(f"[{ref}] {text}")
    return "\n\n".join(parts)
