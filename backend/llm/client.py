"""
client.py
---------
Handles communication with the LLM backend.
Uses Groq if GROQ_API_KEY is set in the environment, otherwise falls back to Ollama.
"""

import os
import requests

# --- Ollama config ---
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3.2:latest"

# --- Groq config ---
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama3-8b-8192"  # or "mixtral-8x7b-32768", "llama3-70b-8192", etc.

_GROQ_KEY = os.environ.get("GROQ_API_KEY")
USING_GROQ = bool(_GROQ_KEY)


def ask_llm(prompt: str, temperature: float = 0.2) -> str:
    """
    Send a prompt to the active LLM backend and return the response.
    Uses Groq if GROQ_API_KEY is set, otherwise Ollama.
    """
    if USING_GROQ:
        return _ask_groq(prompt, temperature)
    return _ask_ollama(prompt, temperature)


# Keep the old name as an alias so nothing else breaks
ask_ollama = ask_llm


def _ask_groq(prompt: str, temperature: float) -> str:
    try:
        response = requests.post(
            GROQ_API_URL,
            headers={
                "Authorization": f"Bearer {_GROQ_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": GROQ_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": temperature,
                "max_tokens": 1024,
            },
            timeout=60,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"].strip()

    except requests.exceptions.HTTPError as e:
        print(f"Groq HTTP error: {response.status_code} — {response.text}")
        raise RuntimeError(f"Groq request failed: {response.status_code}") from e
    except requests.exceptions.ConnectionError:
        raise RuntimeError("Cannot connect to Groq API. Check your internet connection.")
    except requests.exceptions.Timeout:
        raise RuntimeError("Groq API timed out.")


def _ask_ollama(prompt: str, temperature: float) -> str:
    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "num_predict": 1024,
                },
            },
            timeout=120,
        )
        response.raise_for_status()
        return response.json().get("response", "").strip()

    except requests.exceptions.ConnectionError:
        raise RuntimeError("Cannot connect to Ollama. Is 'ollama serve' running?")
    except requests.exceptions.Timeout:
        raise RuntimeError("Ollama timed out. Try a smaller model or increase the timeout.")