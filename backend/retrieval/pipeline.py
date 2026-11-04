from vectorstore import query_chunks
from sessions import get_history
from llm import (
    ask_ollama,
    build_chat_prompt,
)
from llm.translation import translate_response, translate_to_english

from .context_builder import assign_citation_keys, build_context
from .prompt_builder import format_history
from .citation_parser import extract_citations, strip_ghost_citations


def answer_question(question, session_id, language="en"):

    # Translate non-English queries to English before embedding so they
    # match the English IPCC/research corpus correctly.
    retrieval_question = translate_to_english(question) if language != "en" else question

    chunks = query_chunks(retrieval_question, top_k=6)

    if not chunks:
        return None

    # Unique [ref] per chunk so citations can't collide across papers
    assign_citation_keys(chunks)
    context = build_context(chunks)

    history = format_history(get_history(session_id))

    prompt = build_chat_prompt(
        context,
        history,
        retrieval_question,
    )

    # Drop any [ref] the model invented, so every citation shown has a source
    answer = strip_ghost_citations(ask_ollama(prompt), chunks)

    # Pass chunks so each citation can carry its verbatim source text
    citations = extract_citations(answer, chunks)

    # Translate the answer back to the user's selected language (no-op for English)
    if language != "en":
        answer = translate_response(answer, language)

    return {
        "answer": answer,
        "citations": citations,
        "language": language,
    }
