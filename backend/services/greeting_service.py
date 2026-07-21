"""
Handles simple conversational greetings without invoking RAG.
"""

CASUAL_MESSAGES = {
    "hi": "Hi! Ask me anything about the IPCC AR6 climate report.",
    "hello": "Hello! I'm here to help with questions about climate change and the IPCC AR6 report.",
    "hey": "Hey! What would you like to know about climate change?",
    "thanks": "You're welcome! Feel free to ask more questions.",
    "thank you": "Happy to help! Let me know if you have more questions.",
    "bye": "Goodbye! Come back if you have more climate questions.",
    "ok": "Sure! Ask me another climate question whenever you're ready.",
    "okay": "Sure! Ask me another climate question whenever you're ready.",
    "cool": "Glad to help!"
}


def is_casual_message(message: str) -> bool:
    return message.lower().strip("!.,?") in CASUAL_MESSAGES


def casual_response(message: str) -> str:
    key = message.lower().strip("!.,?")
    return CASUAL_MESSAGES.get(
        key,
        "Hi! What would you like to know?"
    )