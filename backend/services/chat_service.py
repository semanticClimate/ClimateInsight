"""
Main chatbot orchestration.

Delegates to the retrieval pipeline, which handles context retrieval,
prompt building, and LLM calls. Session history is managed by app.py.
"""

from retrieval import answer_question


def generate_answer(question, session_id):

    result = answer_question(question, session_id)

    if result is None:
        return {
            "answer": (
                "I couldn't find relevant information in the IPCC report "
                "for that question. Try rephrasing it."
            ),
            "citations": [],
        }

    return result