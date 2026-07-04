def build_context(chunks: list[dict]) -> str:
    """
    Convert retrieved chunks into the context block
    given to the language model.
    """

    return "\n\n".join(
        f"[{chunk['section']}] {chunk['text']}"
        for chunk in chunks
    )