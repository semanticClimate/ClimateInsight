import re


def extract_citations(answer: str, chunks: list[dict]) -> list[dict]:
    """
    Parse inline [passage-id] markers from the LLM answer and attach
    the verbatim chunk text that corresponds to each cited passage.

    Returns a deduplicated list preserving citation order.
    Only includes citations whose passage ID was actually in the
    retrieved chunks — ghost citations (hallucinated passage IDs)
    are silently dropped.

    Each entry: {"section": str, "title": str, "text": str}
    """

    cited_ids = list(dict.fromkeys(re.findall(r"\[([^\]]+)\]", answer)))

    # Chroma chunk IDs are globally unique across papers. Never fall back to
    # section names here: doing so would recreate the cross-paper collision.
    chunk_map = {
        c["chunk_id"]: c
        for c in chunks
        if c.get("chunk_id")
    }

    result = []
    for citation_id in cited_ids:
        chunk = chunk_map.get(citation_id)
        if chunk is None:
            # LLM cited a passage that wasn't in the retrieved chunks —
            # drop it entirely so no ghost citations appear in the UI
            continue
        entry = {
            "citation_id": citation_id,
            "section": chunk.get("section", ""),
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
        if chunk.get("source_type"):
            entry["source_type"] = chunk["source_type"]
        if chunk.get("document_title"):
            entry["document_title"] = chunk["document_title"]
        result.append(entry)

    return result
