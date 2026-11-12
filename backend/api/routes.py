"""FastAPI routes for chat, source documents and the knowledge graph."""

import logging
import os
import re
import uuid
from pathlib import Path

from fastapi import Body, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from starlette.background import BackgroundTask
from starlette.exceptions import HTTPException as StarletteHTTPException
import requests as http_requests

try:
    import tomllib
except ImportError:
    import tomli as tomllib

from backend.retrieval import answer_question
from backend.core.sessions import add_to_history, clear_history
from backend.knowledge_graph.question import handle_concept_graph_request
from backend.knowledge_graph.engine import (
    DEFAULT_IPCC_DOC, concept_resources, get_graph, link_resources,
)
from backend.encyclopedia.service import (
    render_report, render_glossary, render_viewer_script, settings, glossary_html_path,
)
from backend.core.paths import (
    PROJECT_ROOT, FRONTEND_DIR, RAW_DATA_DIR, PAPERS_DIR, ENCYCLOPEDIA_ASSETS_DIR,
)
from backend.api.responses import (
    chat_response, error_response, health_response, message_response,
)

log = logging.getLogger(__name__)
_FRONTEND_DIR = str(FRONTEND_DIR)
_PAPERS_DIR = PAPERS_DIR
_CONFIG_PATH = PROJECT_ROOT / "config.toml"

app = FastAPI()
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)


def _local_file(directory: Path, filename: str) -> Path:
    """Keep file routes inside their designated directory, including symlinks."""
    base = Path(directory).resolve()
    path = (base / filename).resolve()
    if not path.is_relative_to(base) or not path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    return path


def _ipcc_report_path(doc: str) -> Path:
    """Resolve the document stem used by graph links without accepting file paths."""
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", doc) or doc in {".", ".."}:
        raise HTTPException(status_code=404, detail="Unknown IPCC document")
    if doc == DEFAULT_IPCC_DOC:
        return _local_file(RAW_DATA_DIR, "ipcc_reference.html")
    base = RAW_DATA_DIR.resolve()
    matches = [
        path.resolve() for path in base.rglob("*")
        if path.stem == doc and path.suffix.lower() in {".html", ".htm"}
        and path.is_file() and path.resolve().is_relative_to(base)
    ]
    if len(matches) != 1:
        raise HTTPException(
            status_code=409 if matches else 404,
            detail="Ambiguous IPCC document" if matches else "Unknown IPCC document",
        )
    return matches[0]


@app.get("/")
def index():
    return FileResponse(_local_file(FRONTEND_DIR, "index.html"))


@app.get("/api/config")
def get_config():
    try:
        with _CONFIG_PATH.open("rb") as handle:
            return tomllib.load(handle)
    except FileNotFoundError:
        return JSONResponse(error_response("config.toml not found"), status_code=404)


@app.get("/api/health")
def health():
    return health_response()


@app.get("/concept-graph")
def concept_graph_page():
    return FileResponse(_local_file(FRONTEND_DIR, "concept_graph.html"))


@app.get("/ipcc-reference", response_class=HTMLResponse)
def ipcc_reference(doc: str = DEFAULT_IPCC_DOC):
    """Serve SYR by default, or another local IPCC document named by a graph link."""
    html = _ipcc_report_path(doc).read_text(encoding="utf-8")
    html = re.sub(
        r'(src=["\'])https://www\.ipcc\.ch/([^"\'>]+)',
        r'\1/ipcc-image-proxy/\2',
        html,
    )
    # The generated Encyclopedia belongs to the configured SYR report.
    if doc == DEFAULT_IPCC_DOC:
        try:
            html = render_report(html)
        except (ImportError, OSError, ValueError) as exc:
            log.warning("Serving the original IPCC report: %s", exc)
    return HTMLResponse(html)


@app.get("/paper/{pmcid}")
def serve_paper(pmcid: str):
    match = re.fullmatch(r"(?:PMC)?(\d+)", pmcid, flags=re.IGNORECASE)
    if match is None:
        raise HTTPException(status_code=404, detail="Unknown paper")
    paper_id = match.group(1)
    for filename in (f"PMC{paper_id}.html", f"{paper_id}.html"):
        if (_PAPERS_DIR / filename).is_file():
            return FileResponse(_local_file(_PAPERS_DIR, filename))
    raise HTTPException(status_code=404, detail="Unknown paper")


@app.get("/paper/{asset_dir}/{filename:path}")
def serve_paper_asset(asset_dir: str, filename: str):
    if re.fullmatch(r"PMC\d+_assets", asset_dir) is None:
        raise HTTPException(status_code=404, detail="Unknown paper asset")
    directory = _PAPERS_DIR / asset_dir
    # Validate both the asset directory and the requested file.
    if not directory.resolve().is_relative_to(_PAPERS_DIR.resolve()):
        raise HTTPException(status_code=404, detail="Unknown paper asset")
    return FileResponse(_local_file(directory, filename))


@app.get("/climate-wiki-js")
def climate_wiki_js():
    directory = ENCYCLOPEDIA_ASSETS_DIR
    if settings()[0] == "legacy":
        return FileResponse(
            _local_file(directory, "climate-wiki.legacy.js"), media_type="application/javascript",
        )
    try:
        template = (directory / "climate-wiki.js").read_text(encoding="utf-8")
        return Response(render_viewer_script(template), media_type="application/javascript")
    except (ImportError, OSError, ValueError) as exc:
        log.warning("Generated IPCC Encyclopedia unavailable: %s", exc)
        return Response(
            "console.error('IPCC Encyclopedia unavailable. Run python -m backend.encyclopedia.build.');",
            status_code=503, media_type="application/javascript",
        )


@app.get("/ipcc-encyclopedia", response_class=HTMLResponse)
def ipcc_encyclopedia():
    try:
        report = (RAW_DATA_DIR / "ipcc_reference.html").read_text(encoding="utf-8")
        return HTMLResponse(render_glossary(report))
    except (ImportError, OSError, ValueError) as exc:
        log.warning("IPCC Encyclopedia unavailable: %s", exc)
        return JSONResponse(error_response(
            "The IPCC Encyclopedia is unavailable. Run python -m backend.encyclopedia.build; "
            "the original report remains available."
        ), status_code=503)


@app.get("/ipcc-glossary")
def ipcc_glossary():
    path = glossary_html_path()
    if not path.is_file():
        return JSONResponse(error_response(
            "Build the glossary with python -m backend.encyclopedia.build --reuse-report"
        ), status_code=503)
    return FileResponse(path, media_type="text/html")


@app.get("/ipcc-image-proxy/{image_path:path}")
def ipcc_image_proxy(image_path: str):
    """Stream IPCC images without forwarding the browser's Referer header."""
    try:
        resp = http_requests.get(
            f"https://www.ipcc.ch/{image_path}", timeout=15,
            headers={"User-Agent": "Mozilla/5.0"}, stream=True,
        )
        return StreamingResponse(
            resp.iter_content(chunk_size=8192), status_code=resp.status_code,
            media_type=resp.headers.get("Content-Type", "image/png"),
            background=BackgroundTask(resp.close),
        )
    except http_requests.exceptions.RequestException:
        return Response("Image unavailable", status_code=502, media_type="text/plain")


@app.get("/report-styles")
def report_styles():
    return FileResponse(_local_file(FRONTEND_DIR, "css/report.css"), media_type="text/css")


@app.post("/api/chat")
def chat(body: dict | None = Body(default=None)):
    data = body or {}
    question = data.get("question") or ""
    if not isinstance(question, str) or not question.strip():
        return JSONResponse(error_response("question required"), status_code=400)
    question = question.strip()
    session_id = data.get("session_id") or str(uuid.uuid4())
    if not isinstance(session_id, str):
        return JSONResponse(error_response("session_id must be a string"), status_code=400)
    try:
        result = answer_question(question, session_id)
    except RuntimeError as exc:
        log.error("chat error: %s", exc)
        return JSONResponse(error_response(str(exc)), status_code=503)
    if result is None:
        return chat_response(
            answer="I couldn't find relevant information.", citations=[], session_id=session_id,
        )
    add_to_history(session_id, "user", question)
    add_to_history(session_id, "assistant", result["answer"])
    return chat_response(
        answer=result["answer"], citations=result["citations"], session_id=session_id,
    )


@app.get("/api/knowledge-graph")
def knowledge_graph_data():
    try:
        return get_graph()
    except Exception:
        log.exception("knowledge-graph error")
        return JSONResponse(error_response("Could not build the knowledge graph"), status_code=500)


@app.get("/api/knowledge-graph/concept")
def knowledge_graph_concept(id: str = ""):
    try:
        return concept_resources(id)
    except KeyError:
        return JSONResponse(error_response("Unknown concept"), status_code=404)


@app.get("/api/knowledge-graph/link")
def knowledge_graph_link(a: str = "", b: str = ""):
    try:
        return link_resources(a, b)
    except KeyError:
        return JSONResponse(error_response("These concepts are not linked"), status_code=404)


@app.post("/api/concept-graph")
def concept_graph(body: dict | None = Body(default=None)):
    question = (body or {}).get("question", "")
    if not isinstance(question, str):
        return JSONResponse(error_response("'question' must be a string."), status_code=400)
    try:
        return handle_concept_graph_request(question)
    except ValueError as exc:
        return JSONResponse(error_response(str(exc)), status_code=400)
    except RuntimeError as exc:
        log.error("concept-graph error: %s", exc)
        return JSONResponse(error_response(str(exc)), status_code=503)
    except Exception:
        log.exception("concept-graph error")
        return JSONResponse(error_response("Internal server error"), status_code=500)


@app.delete("/api/session/{session_id}")
def clear(session_id: str):
    clear_history(session_id)
    return message_response("Session cleared")


@app.exception_handler(StarletteHTTPException)
async def http_error(request: Request, exc: StarletteHTTPException):
    if exc.status_code == 404 and (request.url.path == "/api" or request.url.path.startswith("/api/")):
        content = {"error": "API route not found", "path": request.url.path}
    else:
        content = error_response(str(exc.detail))
    return JSONResponse(content, status_code=exc.status_code, headers=exc.headers)


@app.exception_handler(RequestValidationError)
async def invalid_request(request: Request, exc: RequestValidationError):
    return JSONResponse(error_response("Invalid request body or parameters"), status_code=400)


# Keep both the original /css, /js, /images URLs and /frontend/... working.
# Register the root mount last so it cannot intercept API or document routes.
app.mount("/frontend", StaticFiles(directory=_FRONTEND_DIR), name="frontend")
app.mount("/", StaticFiles(directory=_FRONTEND_DIR), name="frontend-root")

