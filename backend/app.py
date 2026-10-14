from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .retrieval.pipeline import answer_question
from .services.session import add, clear, get

ROOT = Path(__file__).resolve().parent.parent

app = FastAPI(title="PaperInsight", version="0.1.0")
app.mount("/static", StaticFiles(directory=str(ROOT / "frontend")), name="static")


class ChatRequest(BaseModel):
    question: str
    session_id: str | None = None


@app.get("/")
def index():
    return FileResponse(ROOT / "frontend" / "index.html")


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/papers")
def papers():
    from .retrieval.hybrid import _load_lexical_index
    data, _, _ = _load_lexical_index()
    seen = {}
    for x in data:
        seen[x["pmcid"]] = {
            "pmcid": x["pmcid"],
            "doi": x.get("doi", ""),
            "title": x.get("title", ""),
            "url": f"https://europepmc.org/articles/{x['pmcid']}",
        }
    return list(seen.values())


@app.get("/api/retrieve")
def retrieve_api(q: str):
    from .retrieval.hybrid import retrieve
    question = q.strip()
    if not question:
        raise HTTPException(status_code=400, detail="q is required")
    try:
        evidence = retrieve(question)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"question": question, "results": [e.as_dict() for e in evidence]}


@app.post("/api/chat")
def chat(req: ChatRequest):
    question = req.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question is required.")
    session_id = req.session_id or str(uuid.uuid4())
    try:
        result = answer_question(question)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    add(session_id, "user", question)
    add(session_id, "assistant", result["answer"])
    return {
        "session_id": session_id,
        "answer": result["answer"],
        "citations": result["citations"],
    }


@app.get("/api/session/{session_id}")
def session(session_id: str):
    return {"session_id": session_id, "history": get(session_id)}


@app.delete("/api/session/{session_id}")
def delete_session(session_id: str):
    clear(session_id)
    return {"ok": True}
