from vectorstore import query_chunks
from sessions import get_history
from llm import (
    ask_ollama,
    build_chat_prompt,
)
from llm.translation import translate_response, translate_to_english

from .context_builder import build_context
from .prompt_builder import build_prompt
from .citation_parser import extract_citations


def answer_question(question, session_id, language="en"):

    # Translate non-English queries to English before embedding so they
    # match the English IPCC/research corpus correctly.
    retrieval_question = translate_to_english(question) if language != "en" else question

    chunks = query_chunks(retrieval_question, top_k=6)

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

    # Translate the answer back to the user's selected language (no-op for English)
    if language != "en":
        answer = translate_response(answer, language)

    return {
        "answer": answer,
        "citations": citations,
        "language": language,
    }
