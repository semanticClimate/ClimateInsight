from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

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
)

from services import (
    chat_response,
    error_response,
    health_response,
    message_response,
)

app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

    result = answer_question(
        question,
        session_id,
        language,
    )

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
# Clear session
# -------------------------

@app.delete("/api/session/{session_id}")
def clear(session_id: str):
    clear_history(session_id)
    return message_response("Session cleared")

# -------------------------
# Main
# -------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "5001")),
        reload=True,
        log_level="debug",
    )
