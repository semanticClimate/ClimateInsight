"""
sessions.py — In-memory session store
--------------------------------------
Stores conversation history per session in a plain Python dict.
No Redis, no database — just memory. Resets when the server restarts,
which is fine for development.

When you're ready to persist sessions later, this is the only file
you'd need to change.
"""

from collections import defaultdict

# { session_id: [{"role": "user"|"assistant", "content": "..."}] }
_sessions: dict[str, list[dict]] = defaultdict(list)

MAX_HISTORY = 20  # max messages per session (10 exchanges)


def get_history(session_id: str) -> list[dict]:
    """Return the conversation history for a session."""
    return list(_sessions[session_id])


def add_to_history(session_id: str, role: str, content: str) -> None:
    """Append a message to a session's history."""
    _sessions[session_id].append({"role": role, "content": content})

    # Keep history capped
    if len(_sessions[session_id]) > MAX_HISTORY:
        _sessions[session_id] = _sessions[session_id][-MAX_HISTORY:]


def clear_history(session_id: str) -> None:
    """Clear a session's history."""
    _sessions[session_id] = []


def session_exists(session_id: str) -> bool:
    return session_id in _sessions and len(_sessions[session_id]) > 0
