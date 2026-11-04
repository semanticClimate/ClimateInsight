from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

import logging
import os
import re
import sys
import uuid
import requests as http_requests
from pathlib import Path

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
    get_history,
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

log = logging.getLogger(__name__)

app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def index():
    """Serves the chat UI, so the frontend and /api share one origin."""
    return FileResponse(os.path.join(_FRONTEND_DIR, "index.html"))

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
        raise HTTPException(status_code=500, detail="tomllib/tomli not available")
    try:
        with open(_CONFIG_PATH, "rb") as f:
            data = tomllib.load(f)
        return data
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="config.toml not found")

# -------------------------
# Health
# -------------------------

@app.get("/api/health")
def health():
    return health_response()

# -------------------------
# Concept Graph page
# -------------------------

@app.get("/concept-graph")
def concept_graph_page():
    """Serves the standalone knowledge graph page."""
    return FileResponse(os.path.join(_FRONTEND_DIR, "concept_graph.html"))

# -------------------------
# Reference HTML
# -------------------------

@app.get("/ipcc-reference", response_class=HTMLResponse)
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

    try:
        with open(html_path, "r", encoding="utf-8") as f:
            html = f.read()
    except FileNotFoundError:
        return "IPCC reference HTML not found. Please place it in data/raw/ipcc_reference.html or run the ingest script.", 404

    # Rewrite all ipcc.ch image URLs to go through our proxy.
    # Matches src="https://www.ipcc.ch/..." and src='https://www.ipcc.ch/...'
    html = re.sub(
        r'(src=["\'])https://www\.ipcc\.ch(/[^"\'>]+)',
        r'\1/ipcc-image-proxy\2',
        html,
    )

    return html

@app.get("/paper/{pmcid}")
def serve_paper(pmcid: str):
    rendered = Path(__file__).parent.parent / "data" / "raw" / "ocean_heatwaves_2026"
    if not re.match(r'^\w+$', pmcid):
        raise HTTPException(status_code=404, detail="Not found")
    paper_path = rendered / f"{pmcid}.html"
    if not paper_path.exists():
        raise HTTPException(status_code=404, detail="Not found")
    return FileResponse(paper_path)

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
    
    if not os.path.exists(js_path):
        return "console.error('climate-wiki.js not found');"
    return FileResponse(js_path, media_type="application/javascript")

@app.get("/ipcc-image-proxy/{image_path:path}")
async def ipcc_image_proxy(image_path: str):
    """
    Fetches images from https://www.ipcc.ch server-side and streams them back.

    The browser's Referer header is NOT forwarded, so IPCC's hotlink protection
    lets the request through. Without this proxy, images fail to load when the
    HTML is embedded in the chatbot's iframe because the browser sends
    Referer from the local frontend, which IPCC's CDN blocks.
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

        return StreamingResponse(
            resp.iter_content(chunk_size=8192),
            status_code=resp.status_code,
            media_type=content_type,
        )

    except http_requests.exceptions.RequestException:
        raise HTTPException(status_code=502, detail="Image unavailable")


@app.get("/report-styles")
def report_styles():
    """
    Serves frontend/css/report.css for the IPCC reference iframe.

    The iframe is loaded at /ipcc-reference (a FastAPI URL with no path depth),
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

    return FileResponse(css_path, media_type="text/css")


# -------------------------
# Chat
# -------------------------

@app.post("/api/chat")
async def chat(request: Request):
    try:
        data = await request.json()
    except Exception:
        data = {}

    question = (data.get("question") or "").strip()

    session_id = (
        data.get("session_id")
        or str(uuid.uuid4())
    )

    language = data.get("language", "en")  # e.g. "en", "es", "pt", "fr", "hi"

    if not question:
        raise HTTPException(status_code=400, detail=error_response("question required"))

    try:
        result = answer_question(
            question,
            session_id,
            language,
        )
    except RuntimeError as e:
        # Ollama down, model missing, or empty ChromaDB — readable for the UI
        raise HTTPException(status_code=503, detail=str(e))

    if result is None:
        return chat_response(
            answer=(
                "I don't have enough information in the indexed sources "
                "to answer that."
            ),
            citations=[],
            session_id=session_id,
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

    return chat_response(
        answer=result["answer"],
        citations=result["citations"],
        session_id=session_id,
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
        return get_graph()
    except Exception as e:
        log.error("knowledge-graph error: %s", e)
        return JSONResponse({"error": "Could not build the knowledge graph"}, status_code=500)


@app.get("/api/knowledge-graph/concept")
def knowledge_graph_concept(id: str = ""):
    """
    Sources for one concept: every passage that mentions it.

    Query: ?id=Ocean%20heat%20content
    Response JSON: { "concept", "total", "passages": [{ source, type, part,
                     link, doi, snippet, highlights, mentions }] }
    """
    try:
        return concept_resources(id)
    except KeyError:
        return JSONResponse({"error": "Unknown concept"}, status_code=404)


@app.get("/api/knowledge-graph/link")
def knowledge_graph_link(a: str = "", b: str = ""):
    """
    Sources for one link: the passages where both concepts appear.

    Query: ?a=Marine%20heatwave&b=Ocean%20heat%20content
    Response JSON: { "from", "to", "kind", "total", "note", "passages": [...] }
    """
    try:
        return link_resources(a, b)
    except KeyError:
        return JSONResponse({"error": "These concepts are not linked"}, status_code=404)


@app.post("/api/concept-graph")
async def concept_graph(request: Request):
    """
    Place a climate question on the knowledge graph.

    Request  JSON: { "question": "How does sea level rise affect ecosystems?" }
    Response JSON: { "explanation": "...", "source": "Ollama / llama3.2:latest",
                     "main": [...], "focus": [concept ids],
                     "subgraph": {nodes, edges}, "sources": [...],
                     "citations": [...] }

    Grounded in the same retrieved IPCC / paper passages as /api/chat; the
    explanation is written by the local Ollama model and lists the sources
    instead when Ollama is unavailable.
    """
    try:
        body = await request.json()
    except Exception:
        body = {}
    question = (body or {}).get("question", "")
    try:
        return handle_concept_graph_request(question)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    except RuntimeError as e:
        log.error("concept-graph error: %s", e)
        return JSONResponse({"error": str(e)}, status_code=503)
    except Exception as e:
        log.error("concept-graph error: %s", e)
        return JSONResponse({"error": "Internal server error"}, status_code=500)

# -------------------------
# Session management
# -------------------------

@app.get("/api/session/{session_id}")
def get_session_history(session_id: str):
    """Returns stored conversation history for a session."""
    return {
        "session_id": session_id,
        "history": get_history(session_id),
    }

@app.delete("/api/session/{session_id}")
def clear(session_id: str):
    clear_history(session_id)
    return message_response("Session cleared")

# -------------------------
# Frontend assets (css/, js/, images/ …) — mounted last so API routes win
# -------------------------

app.mount("/", StaticFiles(directory=_FRONTEND_DIR), name="frontend")

# -------------------------
# Main
# -------------------------

if __name__ == "__main__":
    import uvicorn

    # Port 5000 is taken by the AirPlay Receiver on macOS, hence 5001.
    # Reload and debug logging stay off unless asked for: the app is often
    # exposed through a public tunnel.
    dev = os.getenv("DEV", "0") == "1"
    uvicorn.run(
        "app:app",
        host="127.0.0.1" if dev else os.getenv("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", "5001")),
        reload=dev,
        log_level="debug" if dev else "info",
    )
