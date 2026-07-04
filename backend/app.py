from flask import Flask, jsonify, request, send_file
from flask_cors import CORS

import os
import uuid

from retrieval import answer_question
from sessions import (
    add_to_history,
    clear_history,
)

app = Flask(__name__)

CORS(app)

# -------------------------
# Health
# -------------------------

@app.get("/api/health")
def health():
    return {"status": "ok"}

# -------------------------
# Reference HTML
# -------------------------

@app.get("/ipcc-reference")
def ipcc_reference():

    html_path = os.path.abspath(
        os.path.join(
            os.path.dirname(__file__),
            "..",
            "data",
            "raw",
            "ipcc_reference.html",
        )
    )

    return send_file(html_path)

# -------------------------
# Chat
# -------------------------

@app.post("/api/chat")
def chat():

    data = request.get_json(silent=True) or {}

    question = (data.get("question") or "").strip()

    session_id = (
        data.get("session_id")
        or str(uuid.uuid4())
    )

    if not question:
        return jsonify({"error": "question required"}), 400

    result = answer_question(
        question,
        session_id,
    )

    if result is None:
        return jsonify({
            "answer":
            "I couldn't find relevant information.",
            "citations": [],
            "session_id": session_id,
        })

    add_to_history(
        session_id,
        "user",
        question,
    )

    add_to_history(
        session_id,
        "assistant",
        result["answer"],
    )

    result["session_id"] = session_id

    return jsonify(result)

# -------------------------
# Clear session
# -------------------------

@app.delete("/api/session/<session_id>")
def clear(session_id):

    clear_history(session_id)

    return {
        "message": "Session cleared"
    }

# -------------------------
# Main
# -------------------------

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True,
    )