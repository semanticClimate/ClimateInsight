"""
app.py — IPCC Chatbot backend
------------------------------
Run with:  python app.py
"""

from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import uuid
import re
import os

from vectorstore import query_chunks
from llm import ask_ollama
from sessions import get_history, add_to_history

app = Flask(__name__)
CORS(app, origins=[
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5500",
    r"https://.*\.trycloudflare\.com",   # Cloudflare quick tunnels
])


# ── Health check ──────────────────────────────────────────────────────────────

@app.get("/api/health")
def health():
    return jsonify({"status": "ok"})


# ── IPCC Reference document ───────────────────────────────────────────────────

@app.get("/ipcc-reference")
def ipcc_reference():
    html_path = os.path.join(
        os.path.dirname(__file__), "..", "data", "raw", "ipcc_reference.html"
    )
    return send_file(os.path.abspath(html_path), mimetype="text/html")


# ── Chat ──────────────────────────────────────────────────────────────────────

@app.post("/api/chat")
def chat():
    data       = request.get_json(silent=True) or {}
    question   = (data.get("question") or "").strip()
    session_id = (data.get("session_id") or str(uuid.uuid4())).strip()

    if not question:
        return jsonify({"error": "question is required"}), 400

    # Casual messages — skip RAG, just respond naturally
    casual = {"hi", "hello", "hey", "thanks", "thank you", "ok", "okay", "bye", "cool"}
    if question.lower().strip("!.,?") in casual:
        greetings = {
            "hi": "Hi! Ask me anything about the IPCC AR6 climate report.",
            "hello": "Hello! I'm here to help with questions about climate change and the IPCC AR6 report.",
            "hey": "Hey! What would you like to know about climate change?",
            "thanks": "You're welcome! Feel free to ask more questions.",
            "thank you": "Happy to help! Let me know if you have more questions.",
            "bye": "Goodbye! Come back if you have more climate questions.",
        }
        reply = greetings.get(question.lower().strip("!.,?"), "Hi! What would you like to know?")
        return jsonify({"answer": reply, "citations": [], "session_id": session_id})

    # 1. Retrieve relevant chunks from ChromaDB
    chunks = query_chunks(question, top_k=6)

    if not chunks:
        return jsonify({
            "answer":     "I couldn't find relevant information in the IPCC report for that question. Try rephrasing or asking about a different climate topic.",
            "citations":  [],
            "session_id": session_id,
        })

    # 2. Build context block from chunks
    context = "\n\n".join(
        f"[{c['section']}] {c['text']}" for c in chunks
    )

    # 3. Get conversation history
    history = get_history(session_id)

    history_block = ""
    for turn in history[-6:]:
        role = "User" if turn["role"] == "user" else "Assistant"
        history_block += f"{role}: {turn['content']}\n"

    # 4. Build the prompt
    prompt = f"""You are a knowledgeable and friendly climate science assistant specialising in the IPCC AR6 Synthesis Report.

Your job is to give clear, direct, helpful answers based on the context passages provided. Write like a knowledgeable person explaining something to a curious reader.

Guidelines:
- Answer the question directly and confidently. Do NOT start your answer with "According to..." or "The context passage mentions...".
- Cite sections naturally inline at the end of the relevant sentence, e.g. "Global temperatures have risen by 1.1°C since pre-industrial times [2.1.1]."
- If the context covers the topic partially, answer what you can — don't refuse just because it's incomplete.
- Write in clear, plain English. Short paragraphs, no walls of text.
- Never refer to "the context passage" or "the provided context" — just answer as if you know this material.
- If the question is completely outside what the context covers, say so briefly and suggest they rephrase.

Context passages from the IPCC AR6 report:
{context}

# pyrefly: ignore [invalid-syntax]
{"Previous conversation:" + history_block if history_block else ""}
User: {question}
Assistant:"""

    # 5. Call Ollama
    answer = ask_ollama(prompt)

    # 6. Save to history
    add_to_history(session_id, "user", question)
    add_to_history(session_id, "assistant", answer)

    # 7. Extract citations from the answer
    cited     = re.findall(r"\[([^\]]+)\]", answer)
    citations = [{"section": s} for s in dict.fromkeys(cited)]

    return jsonify({
        "answer":     answer,
        "citations":  citations,
        "session_id": session_id,
    })


# ── Session clear ─────────────────────────────────────────────────────────────

@app.delete("/api/session/<session_id>")
def clear_session(session_id):
    from sessions import clear_history
    clear_history(session_id)
    return jsonify({"message": "Session cleared"})


# ── Run ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Starting IPCC Chatbot...")
    print("Visit http://localhost:5000/api/health to check it's running")
    app.run(host="0.0.0.0", port=5000, debug=True)