def build_context(chunks: list[dict]) -> str:
    """
    Convert retrieved chunks into the context block given to the LLM.

    Each passage is labelled with its globally unique chunk ID. This keeps
    identically named sections from different papers distinct.
    When a citation_label is present (e.g. "Chen et al. 2024"), it is
    prepended so the LLM can reference the source naturally.
    """
    parts = []
    for chunk in chunks:
        citation_id = chunk.get("chunk_id")
        if not citation_id:
            raise ValueError(
                "Retrieved chunk is missing chunk_id; citations require a "
                "globally unique passage identifier."
            )
        text = chunk.get("text", "")
        label = chunk.get("citation_label", "")
        if label:
            parts.append(f"[{citation_id}] ({label}) {text}")
        else:
            parts.append(f"[{citation_id}] {text}")
    return "\n\n".join(parts)
