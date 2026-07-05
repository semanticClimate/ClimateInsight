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
        chunk = chunk_map.get(section, {})
        result.append({
            "section": section,
            "title": chunk.get("section_title", ""),
            "text": chunk.get("text", ""),
        })

    return result
