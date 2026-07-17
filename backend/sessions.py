"""
sessions.py — Redis-backed session store
-----------------------------------------
Stores conversation history per session in Redis as JSON.
Sessions survive server restarts and work across multiple Flask workers.

Falls back to in-memory storage if Redis is unavailable (e.g. local dev
without Redis running), so the app never hard-crashes on startup.

Config:
    REDIS_URL env var (default: redis://localhost:6379/0)
    SESSION_TTL_SECONDS env var (default: 86400 — 24 hours)
"""

import json
import os
from collections import defaultdict

# ── Config ────────────────────────────────────────────────────────────────────
MAX_HISTORY = 20  # max messages per session (10 exchanges)
_REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
_TTL = int(os.environ.get("SESSION_TTL_SECONDS", 86400))  # 24h default

# ── Redis client (optional) ───────────────────────────────────────────────────
_redis = None

try:
    import redis
    _client = redis.from_url(_REDIS_URL, decode_responses=True)
    _client.ping()  # fail fast if Redis isn't running
    _redis = _client
    print(f"[sessions] Redis connected: {_REDIS_URL}")
except Exception as e:
    print(f"[sessions] Redis unavailable ({e}) — falling back to in-memory store.")

# ── In-memory fallback ────────────────────────────────────────────────────────
_fallback: dict[str, list[dict]] = defaultdict(list)


# ── Internal helpers ──────────────────────────────────────────────────────────
def _key(session_id: str) -> str:
    return f"session:{session_id}"


def _redis_get(session_id: str) -> list[dict]:
    raw = _redis.get(_key(session_id))
    return json.loads(raw) if raw else []


def _redis_set(session_id: str, history: list[dict]) -> None:
    _redis.setex(_key(session_id), _TTL, json.dumps(history))


# ── Public API (identical interface to the old in-memory version) ─────────────
def get_history(session_id: str) -> list[dict]:
    """Return the conversation history for a session."""
    if _redis:
        return _redis_get(session_id)
    return list(_fallback[session_id])


def add_to_history(session_id: str, role: str, content: str) -> None:
    """Append a message to a session's history, capped at MAX_HISTORY."""
    if _redis:
        history = _redis_get(session_id)
        history.append({"role": role, "content": content})
        if len(history) > MAX_HISTORY:
            history = history[-MAX_HISTORY:]
        _redis_set(session_id, history)
    else:
        _fallback[session_id].append({"role": role, "content": content})
        if len(_fallback[session_id]) > MAX_HISTORY:
            _fallback[session_id] = _fallback[session_id][-MAX_HISTORY:]


def clear_history(session_id: str) -> None:
    """Clear a session's history."""
    if _redis:
        _redis.delete(_key(session_id))
    else:
        _fallback[session_id] = []


def session_exists(session_id: str) -> bool:
    if _redis:
        return _redis.exists(_key(session_id)) == 1
    return session_id in _fallback and len(_fallback[session_id]) > 0