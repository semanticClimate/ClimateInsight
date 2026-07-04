"""
client.py
---------
Handles communication with the Ollama server.
"""

import requests

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3.2:latest"


def ask_ollama(prompt: str, temperature: float = 0.2) -> str:
    """
    Send a prompt to Ollama and return the generated response.
    """

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
        raise RuntimeError(
            "Cannot connect to Ollama. Is 'ollama serve' running?"
        )

    except requests.exceptions.Timeout:
        raise RuntimeError(
            "Ollama timed out. Try a smaller model or increase the timeout."
        )