import re

_MARKER = re.compile(r"\s?\[([^\]]+)\]")


def strip_ghost_citations(answer: str, chunks: list[dict]) -> str:
    """
    Remove [ref] markers that don't match any retrieved chunk.

    Small models sometimes invent IDs like [2.1]; extract_citations()
    already drops them from the citation chips, and this keeps the answer
    text consistent so readers never see a citation with no source.
    """
    valid = {c["ref"] for c in chunks if c.get("ref")}
    return _MARKER.sub(
        lambda m: m.group(0) if m.group(1) in valid else "",
        answer,
    )


def extract_citations(answer: str, chunks: list[dict]) -> list[dict]:
    """
    Parse inline [ref] markers from the LLM answer and attach
    the verbatim chunk text that corresponds to each cited ref.

    Refs are assigned by context_builder.assign_citation_keys(), so each
    one identifies a single retrieved chunk even when several papers share
    a section name like "introduction".

    Returns a deduplicated list preserving citation order.
    Only includes citations whose ref was actually in the retrieved
    chunks — ghost citations (hallucinated refs) are silently dropped.

    Each entry: {"ref": str, "section": str, "title": str, "text": str, ...}
    """

    cited_refs = list(dict.fromkeys(re.findall(r"\[([^\]]+)\]", answer)))

    # Build a lookup: ref -> chunk dict. Chunks arrive best-match first,
    # so keep the first chunk when several share a ref (same IPCC section).
    chunk_map = {}
    for c in chunks:
        # Only per-answer refs count: a bare section name such as
        # [introduction] is shared by many papers and must not resolve.
        if c.get("ref"):
            chunk_map.setdefault(c["ref"], c)

    result = []
    for ref in cited_refs:
        chunk = chunk_map.get(ref)
        if chunk is None:
            # LLM cited a ref that wasn't in the retrieved chunks —
            # drop it entirely so no ghost citations appear in the UI
            continue
        entry = {
            "ref": ref,
            # Globally unique Chroma ID of the cited passage
            "citation_id": chunk.get("chunk_id", ""),
            "section": chunk.get("section", ""),
            "title": chunk.get("section_title", ""),
            "text": chunk.get("text", ""),
        }
        # Attach paper-level metadata when available (research papers)
        for key in ("citation_label", "document_title", "source_type", "doi", "pmcid"):
            if chunk.get(key):
                entry[key] = chunk[key]
        result.append(entry)

    return result
