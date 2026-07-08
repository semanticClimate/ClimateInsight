import re


def extract_citations(answer: str, chunks: list[dict]) -> list[dict]:
    """
    Parse inline [section] markers from the LLM answer and attach
    the verbatim chunk text that corresponds to each cited section.

    Returns a deduplicated list preserving citation order.
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
            # include it but mark it honestly rather than silently dropping it
            result.append({
                "section": section,
                "title": "Section not found in retrieved context",
                "text": "",
            })
            continue
        result.append({
            "section": section,
            "title": chunk.get("section_title", ""),
            "text": chunk.get("text", ""),
        })

    return result