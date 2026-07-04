"""
response_formatter.py
---------------------
Creates standardized API responses.

Every response returned by the chatbot should be formatted here.
"""


def chat_response(
    answer: str,
    citations: list,
    session_id: str,
) -> dict:
    """
    Standard successful chatbot response.
    """
    return {
        "answer": answer,
        "citations": citations,
        "session_id": session_id,
    }


def error_response(message: str) -> dict:
    """
    Standard error response.
    """
    return {
        "error": message,
    }


def health_response(status: str = "ok") -> dict:
    """
    Health check response.
    """
    return {
        "status": status,
    }


def message_response(message: str) -> dict:
    """
    Generic success message.
    """
    return {
        "message": message,
    }