from vectorstore import query_chunks
from sessions import get_history
from llm import (
    ask_ollama,
    build_chat_prompt,
)

from .context_builder import build_context
from .prompt_builder import build_prompt
from .citation_parser import extract_citations


def answer_question(question, session_id):

    chunks = query_chunks(question, top_k=6)

    if not chunks:
        return None

    context = build_context(chunks)

    history = get_history(session_id)

    prompt = build_chat_prompt(
        context,
        history,
        question,
    )

    answer = ask_ollama(prompt)

    # Pass chunks so each citation can carry its verbatim source text
    citations = extract_citations(answer, chunks)

    return {
        "answer": answer,
        "citations": citations,
    }
