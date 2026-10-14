from __future__ import annotations

from collections import defaultdict

_history = defaultdict(list)


def get(session_id: str) -> list[dict]:
    return _history[session_id][-10:]


def add(session_id: str, role: str, content: str) -> None:
    _history[session_id].append({"role": role, "content": content})
    _history[session_id] = _history[session_id][-10:]


def clear(session_id: str) -> None:
    _history.pop(session_id, None)
