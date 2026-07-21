"""
translation.py
---------------
Language detection and optional translation to English.

Currently uses the local Ollama model.
The structure is intentionally modular so other providers
(OpenAI, Bedrock, Grok, etc.) can be added later.
"""

import re

from .client import ask_ollama


_LANGUAGE_HINTS = {
    "English": [
        r"\b(the|is|what|how|why|when|where|who|do|can|could|would|should)\b"
    ],

    "Hindi": [
        r"\b(क्या|कैसे|क्यों|कब|कहाँ|किसने|मुझे|समझाइए)\b"
    ],

    "Spanish": [
        r"\b(qué|cómo|por qué|cuándo|dónde|quién|puede|explique|defina|resúmeme)\b"
    ],

    "French": [
        r"\b(quoi|comment|pourquoi|quand|où|qui|explique|résume)\b"
    ],

    "German": [
        r"\b(was|wie|warum|wann|wo|wer|erkläre|zusammenfassen)\b"
    ],

    "Portuguese": [
        r"\b(o que|como|por que|quando|onde|quem|explique|resuma)\b"
    ],

    "Arabic": [
        r"\b(ما|كيف|لماذا|متى|أين|من|هل|وضح|لخص)\b"
    ],

    "Mandarin": [
        r"\b(什么|怎么|为什么|什么时候|在哪里|谁|总结)\b"
    ],
}


def _looks_like_hindi(text: str) ->bool:
    return any("\u0900" <= ch <= "\u097f" for ch in text)


def detect_language(query: str) -> str:
    """
    Very lightweight language detector.

    Good enough for routing before retrieval.
    """

    if not query.strip():
        return "English"

    for language, patterns in _LANGUAGE_HINTS.items():
        for pattern in patterns:
            if re.search(pattern, query, re.IGNORECASE):
                return language

    if _looks_like_hindi(query):
        return "Hindi"

    return "English"


def translate_to_english(query: str) -> str:
    """
    Translate non-English text into English.

    English input is returned unchanged.
    """

    language = detect_language(query)

    if language == "English":
        return query

    prompt = f"""
You are a professional translator.

Translate the following text into English.

Rules:
- Translate only.
- Do not answer.
- Do not explain.
- Preserve meaning exactly.
- Return ONLY the translated text.

Text:
{query}
"""

    try:
        return ask_ollama(prompt, temperature=0.0)

    except Exception:
        # Translation failure should never crash retrieval.
        return query