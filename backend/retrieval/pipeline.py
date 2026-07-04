from vectorstore import query_chunks
from sessions import get_history
from llm import ask_ollama

from .context_builder import build_context
from .prompt_builder import build_prompt
from .citation_parser import extract_citations


def answer_question(question, session_id):

    chunks = query_chunks(question, top_k=6)

    if not chunks:
        return None

    context = build_context(chunks)

    history = get_history(session_id)

    prompt = build_prompt(
        question,
        context,
        history,
    )

    answer = ask_ollama(prompt)

    citations = extract_citations(answer)

    return {
        "answer": answer,
        "citations": citations,
    }