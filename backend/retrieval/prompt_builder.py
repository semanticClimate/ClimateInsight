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
