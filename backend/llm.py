"""
llm.py — Ollama caller
-----------------------
Sends a prompt to your local Ollama server and returns the response.
"""

import requests

OLLAMA_URL   = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3.2:latest"


def ask_ollama(prompt: str, temperature: float = 0.2) -> str:
    """
    Send a prompt to Ollama and return the response text.
    Raises RuntimeError if Ollama isn't running.
    """
    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model":  OLLAMA_MODEL,
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
        raise RuntimeError(
            "Cannot connect to Ollama. Make sure it's running: ollama serve"
        )
    except requests.exceptions.Timeout:
        raise RuntimeError("Ollama timed out. The model may be too slow — try a smaller one.")
