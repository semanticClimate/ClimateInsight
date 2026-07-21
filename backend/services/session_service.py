"""
Wrapper around session history.
"""

from sessions import (
    get_history,
    add_to_history,
    clear_history,
)


def build_history_block(session_id: str) -> str:

    history = get_history(session_id)

    lines = []

    for turn in history[-6:]:
        role = "User" if turn["role"] == "user" else "Assistant"
        lines.append(f"{role}: {turn['content']}")

    return "\n".join(lines)


def save_exchange(session_id, question, answer):

    add_to_history(session_id, "user", question)
    add_to_history(session_id, "assistant", answer)


__all__ = [
    "build_history_block",
    "save_exchange",
    "clear_history",
]