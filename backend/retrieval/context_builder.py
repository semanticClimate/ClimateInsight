def build_context(chunks: list[dict]) -> str:
    """
    Convert retrieved chunks into the context block given to the LLM.

    For IPCC-style chunks, IDs look like [2.1].
    For manifest/paper chunks, IDs may be [introduction] or [results].
    When a citation_label is present (e.g. "Chen et al. 2024"), it is
    prepended so the LLM can reference the source naturally.
    """
    parts = []
    for chunk in chunks:
        section = chunk.get("section", "")
        text = chunk.get("text", "")
        label = chunk.get("citation_label", "")
        if label:
            parts.append(f"[{section}] ({label}) {text}")
        else:
            parts.append(f"[{section}] {text}")
    return "\n\n".join(parts)
