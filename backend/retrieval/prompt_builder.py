def build_prompt(
    question: str,
    context: str,
    history: list[dict],
) -> str:

    history_block = ""

    for turn in history[-6:]:
        role = "User" if turn["role"] == "user" else "Assistant"
        history_block += f"{role}: {turn['content']}\n"

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