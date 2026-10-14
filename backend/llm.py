from __future__ import annotations

import requests

from .config import MAX_NEW_TOKENS, OLLAMA_MODEL, OLLAMA_URL, TEMPERATURE


def ask_ollama(prompt: str) -> str:
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": TEMPERATURE,
            "num_predict": MAX_NEW_TOKENS,
        },
    }
    response = requests.post(f"{OLLAMA_URL}/api/generate", json=payload, timeout=180)
    response.raise_for_status()
    data = response.json()
    answer = (data.get("response") or "").strip()
    if not answer:
        raise RuntimeError("Ollama returned an empty response.")
    return answer
