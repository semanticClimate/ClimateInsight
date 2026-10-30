from flask import Flask, jsonify, request, send_file, Response
from flask_cors import CORS

import os
import re
import sys
import uuid
import requests as http_requests
from pathlib import Path          # ← add this line near the other imports

# tomllib is stdlib in Python 3.11+; fall back to tomli for older versions
if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomli as tomllib
    except ImportError:
        tomllib = None

from retrieval import answer_question
from sessions import (
    add_to_history,
    clear_history,
)
from concept_graph import handle_concept_graph_request
from knowledge_graph import concept_resources, get_graph, link_resources

from services import (
    chat_response,
    error_response,
    health_response,
    message_response,
)

_FRONTEND_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "frontend")
)

# Serve the frontend from the same origin as the API, so api.js can resolve
# /api from window.location and a single tunnel exposes the whole app.
app = Flask(__name__, static_folder=_FRONTEND_DIR, static_url_path="")

CORS(app)


@app.get("/")
def index():
    return send_file(os.path.join(_FRONTEND_DIR, "index.html"))

# -------------------------
# Config
# -------------------------

_CONFIG_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "config.toml")
)

@app.get("/api/config")
def get_config():
    """Reads config.toml from the project root and returns it as JSON."""
    if tomllib is None:
        return jsonify({"error": "tomllib/tomli not available"}), 500
    try:
        with open(_CONFIG_PATH, "rb") as f:
            data = tomllib.load(f)
        return jsonify(data)
    except FileNotFoundError:
        return jsonify({"error": "config.toml not found"}), 404

# -------------------------
# Health
# -------------------------

@app.get("/api/health")
def health():
    return jsonify(
        health_response()
    )

# -------------------------
# Concept Graph page
# -------------------------

@app.get("/concept-graph")
def concept_graph_page():
    """Serves the standalone Concept Graph UI."""
    html_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "frontend", "concept_graph.html")
    )
    return send_file(html_path)

@app.get("/frontend/<path:filepath>")
def frontend_static(filepath):
    """Serves frontend static assets (css, js, images) for the concept-graph page."""
    from flask import send_from_directory
    frontend_dir = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "frontend")
    )
    return send_from_directory(frontend_dir, filepath)

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

@app.get("/paper/<pmcid>")
def serve_paper(pmcid):
    from flask import send_from_directory
    rendered = Path(__file__).parent.parent / "data" / "raw" / "ocean_heatwaves_2026"
    if not re.match(r'^\w+$', pmcid):
        return "Not found", 404
    return send_from_directory(rendered, f"{pmcid}.html")

@app.get("/climate-wiki-js")
def climate_wiki_js():
    """Serves the climate-wiki.js script for the IPCC reference iframe."""
    js_path = os.path.abspath(
        os.path.join(
            os.path.dirname(__file__),
            "..",
            "encyclopedia",
            "climate-wiki.js",
        )
    )
    
    try:
        return send_file(js_path, mimetype="application/javascript")
    except FileNotFoundError:
        return Response(
            "console.error('climate-wiki.js not found');",
            status=404,
            mimetype="application/javascript"
        )

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

    try:
        result = answer_question(
            question,
            session_id,
        )
    except RuntimeError as e:
        # Ollama down, model missing, or empty ChromaDB — readable for the UI
        app.logger.error("chat error: %s", e)
        return jsonify(error_response(str(e))), 503

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
# Knowledge Graph
# -------------------------

@app.get("/api/knowledge-graph")
def knowledge_graph_data():
    """
    The corpus-wide concept knowledge graph (see knowledge_graph.py).

    Response JSON: { "nodes": [...], "edges": [...], "groups": [...],
                     "sources": {...}, "stats": {...} }

    Nodes are encyclopedia concepts found in the indexed sources; edges link
    concepts that share passages. AI-free and cached until re-ingest.
    """
    try:
        return jsonify(get_graph())
    except Exception as e:
        app.logger.error("knowledge-graph error: %s", e)
        return jsonify({"error": "Could not build the knowledge graph"}), 500


@app.get("/api/knowledge-graph/concept")
def knowledge_graph_concept():
    """
    Sources for one concept: every passage that mentions it.

    Query: ?id=Ocean%20heat%20content
    Response JSON: { "concept", "total", "passages": [{ source, type, part,
                     link, doi, snippet, highlights, mentions }] }
    """
    try:
        return jsonify(concept_resources(request.args.get("id", "")))
    except KeyError:
        return jsonify({"error": "Unknown concept"}), 404


@app.get("/api/knowledge-graph/link")
def knowledge_graph_link():
    """
    Sources for one link: the passages where both concepts appear.

    Query: ?a=Marine%20heatwave&b=Ocean%20heat%20content
    Response JSON: { "from", "to", "kind", "total", "note", "passages": [...] }
    """
    try:
        return jsonify(link_resources(request.args.get("a", ""), request.args.get("b", "")))
    except KeyError:
        return jsonify({"error": "These concepts are not linked"}), 404


@app.post("/api/concept-graph")
def concept_graph():
    """
    Place a climate question on the knowledge graph.

    Request  JSON: { "question": "How does sea level rise affect ecosystems?" }
    Response JSON: { "explanation": "...", "source": "Ollama / llama3.2:latest",
                     "focus": [concept ids], "subgraph": {nodes, edges},
                     "sources": [...], "citations": [...] }

    Grounded in the same retrieved IPCC / paper passages as /api/chat; the
    explanation is written by the local Ollama model and lists the sources
    instead when Ollama is unavailable. Fully open source.
    """
    body = request.get_json(force=True, silent=True) or {}
    question = body.get("question", "")
    try:
        return jsonify(handle_concept_graph_request(question))
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except RuntimeError as e:
        app.logger.error("concept-graph error: %s", e)
        return jsonify({"error": str(e)}), 503
    except Exception as e:
        app.logger.error("concept-graph error: %s", e)
        return jsonify({"error": "Internal server error"}), 500


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

    # Port 5000 is taken by the AirPlay Receiver on macOS, hence 5001.
    port = int(os.getenv("PORT", "5001"))

    # Never enable the Werkzeug debugger by default: it allows arbitrary code
    # execution, and the app is often exposed through a public tunnel.
    debug = os.getenv("FLASK_DEBUG", "0") == "1"
    host = "127.0.0.1" if debug else os.getenv("HOST", "0.0.0.0")

    app.run(
        host=host,
        port=port,
        debug=debug,
    )