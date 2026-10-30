def format_history(history: list[dict], max_turns: int = 6) -> str:
    """
    Render session history (list of {"role", "content"} dicts) as plain
    "User: ..." / "Assistant: ..." lines for the prompt.

    Only the last *max_turns* messages are kept to bound prompt length.
    """
    lines = []
    for turn in history[-max_turns:]:
        role = "User" if turn["role"] == "user" else "Assistant"
        lines.append(f"{role}: {turn['content']}")
    return "\n".join(lines)


def build_prompt(
    question: str,
    context: str,
    history: list[dict],
) -> str:

    history_block = format_history(history)
    if history_block:
        history_block += "\n"

    return f"""
You are a knowledgeable and friendly climate science assistant specialising in the IPCC AR6 Synthesis Report.

Your job is to give clear, direct, helpful answers based on the context passages provided.

Guidelines:
- Answer directly.
- Never mention "context".
- Cite sections inline.
- Keep explanations clear.

Context:
{context}

{"Previous conversation:" + history_block if history_block else ""}

User:
{question}

Assistant:
"""
