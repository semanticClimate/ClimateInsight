from flask import Flask, jsonify, request, send_file, Response
from flask_cors import CORS

import os
import re
import uuid
import requests as http_requests

from retrieval import answer_question
from sessions import (
    add_to_history,
    clear_history,
)

from services import (
    chat_response,
    error_response,
    health_response,
    message_response,
)

app = Flask(__name__)

CORS(app)

# -------------------------
# Health
# -------------------------

@app.get("/api/health")
def health():
    return jsonify(
        health_response()
    )

# -------------------------
# Reference HTML
# -------------------------

@app.get("/ipcc-reference")
def ipcc_reference():
    """
    Serves ipcc_reference.html with all ipcc.ch image URLs rewritten to
    go through our local /ipcc-image-proxy route.

    Why: IPCC's CDN uses hotlink protection — it blocks image requests that
    carry a Referer header from localhost. The browser sends this Referer
    when loading images inside the iframe. By proxying server-side, we fetch
    the images without any Referer, so IPCC allows it.
    """
    html_path = os.path.abspath(
        os.path.join(
            os.path.dirname(__file__),
            "..",
            "data",
            "raw",
            "ipcc_reference.html",
        )
    )

    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()

    # Rewrite all ipcc.ch image URLs to go through our proxy.
    # Matches src="https://www.ipcc.ch/..." and src='https://www.ipcc.ch/...'
    html = re.sub(
        r'(src=["\'])https://www\.ipcc\.ch(/[^"\'>]+)',
        r'\1/ipcc-image-proxy\2',
        html,
    )

    return Response(html, mimetype="text/html")


@app.get("/ipcc-image-proxy/<path:image_path>")
def ipcc_image_proxy(image_path):
    """
    Fetches images from https://www.ipcc.ch server-side and streams them back.

    The browser's Referer header is NOT forwarded, so IPCC's hotlink protection
    lets the request through. Without this proxy, images fail to load when the
    HTML is embedded in the chatbot's iframe because the browser sends
    Referer: http://localhost:5000 which IPCC's CDN blocks.
    """
    upstream_url = f"https://www.ipcc.ch/{image_path}"

    try:
        resp = http_requests.get(
            upstream_url,
            timeout=15,
            headers={"User-Agent": "Mozilla/5.0"},
            stream=True,
        )
        content_type = resp.headers.get("Content-Type", "image/png")

        return Response(
            resp.iter_content(chunk_size=8192),
            status=resp.status_code,
            content_type=content_type,
        )

    except http_requests.exceptions.RequestException:
        return Response("Image unavailable", status=502)


@app.get("/report-styles")
def report_styles():
    """
    Serves frontend/css/report.css for the IPCC reference iframe.

    The iframe is loaded at /ipcc-reference (a Flask URL with no path depth),
    so relative CSS paths in ipcc_reference.html break. This route gives the
    iframe a stable absolute URL it can always resolve: /report-styles
    """
    css_path = os.path.abspath(
        os.path.join(
            os.path.dirname(__file__),
            "..",
            "frontend",
            "css",
            "report.css",
        )
    )

    return send_file(css_path, mimetype="text/css")


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
        return jsonify(
            error_response("question required")
        ), 400

    result = answer_question(
        question,
        session_id,
    )

    if result is None:
        return jsonify(
            chat_response(
                answer="I couldn't find relevant information.",
                citations=[],
                session_id=session_id,
            )
        )

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

    return jsonify(
        chat_response(
            answer=result["answer"],
            citations=result["citations"],
            session_id=session_id,
        )
)

# -------------------------
# Clear session
# -------------------------

@app.delete("/api/session/<session_id>")
def clear(session_id):

    clear_history(session_id)

    return jsonify(
        message_response(
            "Session cleared"
        )
    )

# -------------------------
# Main
# -------------------------

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True,
    )