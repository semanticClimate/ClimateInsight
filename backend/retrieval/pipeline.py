from vectorstore import query_chunks
from sessions import get_history
from llm import (
    ask_ollama,
    build_chat_prompt,
)

from .context_builder import assign_citation_keys, build_context
from .prompt_builder import format_history
from .citation_parser import extract_citations, strip_ghost_citations


def answer_question(question, session_id):

    chunks = query_chunks(question, top_k=6)

    if not chunks:
        return None

    # Unique [ref] per chunk so citations can't collide across papers
    assign_citation_keys(chunks)
    context = build_context(chunks)

    history = format_history(get_history(session_id))

    prompt = build_chat_prompt(
        context,
        history,
        question,
    )

    answer = strip_ghost_citations(ask_ollama(prompt), chunks)

    # Pass chunks so each citation can carry its verbatim source text
    citations = extract_citations(answer, chunks)

    return {
        "answer": answer,
        "citations": citations,
    }
