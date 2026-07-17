import re


def extract_citations(answer: str, chunks: list[dict]) -> list[dict]:
    """
    Parse inline [section] markers from the LLM answer and attach
    the verbatim chunk text that corresponds to each cited section.

    Returns a deduplicated list preserving citation order.
    Only includes citations whose section ID was actually in the
    retrieved chunks — ghost citations (hallucinated section IDs)
    are silently dropped.

    Each entry: {"section": str, "title": str, "text": str}
    """

    cited_sections = list(dict.fromkeys(re.findall(r"\[([^\]]+)\]", answer)))

    # Build a lookup: section_id -> chunk dict
    chunk_map = {c["section"]: c for c in chunks}

    result = []
    for section in cited_sections:
        chunk = chunk_map.get(section)
        if chunk is None:
            # LLM cited a section that wasn't in the retrieved chunks —
            # drop it entirely so no ghost citations appear in the UI
            continue
        entry = {
            "section": section,
            "title": chunk.get("section_title", ""),
            "text": chunk.get("text", ""),
        }
        # Attach paper-level metadata when available (manifest-ingested papers)
        if chunk.get("citation_label"):
            entry["citation_label"] = chunk["citation_label"]
        if chunk.get("doi"):
            entry["doi"] = chunk["doi"]
        if chunk.get("pmcid"):
            entry["pmcid"] = chunk["pmcid"]
        result.append(entry)

    return result