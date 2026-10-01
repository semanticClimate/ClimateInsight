from vectorstore import query_chunks
from sessions import get_history
from llm import (
    ask_ollama,
    build_chat_prompt,
    build_grounding_repair_prompt,
)
from llm.translation import translate_response, translate_to_english

from .context_builder import build_context
from .prompt_builder import build_prompt
from .citation_parser import (
    answer_is_grounded,
    build_extractive_fallback,
    extract_citations,
    strip_source_aliases,
)


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

    if not answer_is_grounded(answer, chunks):
        repair_prompt = build_grounding_repair_prompt(
            context,
            retrieval_question,
            answer,
        )
        answer = ask_ollama(repair_prompt)

    if not answer_is_grounded(answer, chunks):
        answer = build_extractive_fallback(retrieval_question, chunks)

    if not answer or not answer_is_grounded(answer, chunks):
        fallback_msg = "I couldn't produce a source-validated answer. Please try a more specific question."
        if language != "en":
            fallback_msg = translate_response(fallback_msg, language)
        return {
            "answer": fallback_msg,
            "citations": [],
            "language": language,
        }

    # Pass chunks so each citation can carry its verbatim source text
    citations = extract_citations(answer, chunks)
    answer = strip_source_aliases(answer)

    # Generate dynamic Mermaid concept flowchart
    from .concept_map import generate_concept_map
    concept_map = generate_concept_map(question, answer)

    # Translate the answer back to the user's selected language (no-op for English)
    if language != "en":
        answer = translate_response(answer, language)

    return {
        "answer": answer,
        "citations": citations,
        "concept_map": concept_map,
        "language": language,
    }
