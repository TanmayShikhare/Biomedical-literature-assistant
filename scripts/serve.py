#!/usr/bin/env python3
"""HTTP API + static web UI: GET / → app, POST /ask JSON {\"question\": \"...\"}."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

try:
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import FileResponse
    from fastapi.staticfiles import StaticFiles
    from pydantic import BaseModel, Field
    import uvicorn
except ModuleNotFoundError as e:
    missing = getattr(e, "name", None) or str(e).split()[-1].rstrip("'")
    raise SystemExit(
        f"Missing dependency ({missing}). Use this repo's environment:\n"
        "  source .venv/bin/activate   # or: python3 -m venv .venv && source .venv/bin/activate\n"
        "  pip install -r requirements.txt\n"
        "  python scripts/serve.py\n"
        "Or run: .venv/bin/python scripts/serve.py"
    ) from e

from biomed_rag.config import get_settings
from biomed_rag.prompts import USER_FACING_DISCLAIMER
from biomed_rag.workflow import build_app

WEB_DIR = ROOT / "web"
STATIC_DIR = WEB_DIR / "static"

app = FastAPI(title="PubMed biomed RAG", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_settings = get_settings()
_graph = build_app(_settings)


@app.get("/")
def index_page():
    return FileResponse(WEB_DIR / "index.html")


if STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


class AskIn(BaseModel):
    question: str = Field(..., min_length=1)


class AskOut(BaseModel):
    disclaimer: str
    answer: str
    allowed_pmids: str
    top_passages: list[dict]
    outcomes_json: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/ask", response_model=AskOut)
def ask(body: AskIn):
    out = _graph.invoke(
        {
            "question": body.question.strip(),
            "focus_terms": "",
            "allowed_pmids": "",
            "passages": "",
            "top_passages": [],
            "graph_text": "",
            "outcomes_json": "[]",
            "answer": "",
        }
    )
    return AskOut(
        disclaimer=USER_FACING_DISCLAIMER,
        answer=out.get("answer", ""),
        allowed_pmids=out.get("allowed_pmids", ""),
        top_passages=out.get("top_passages", []),
        outcomes_json=out.get("outcomes_json", "[]"),
    )


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Biomed RAG API + web UI")
    ap.add_argument("--host", default="127.0.0.1", help="Bind address (default 127.0.0.1)")
    ap.add_argument("--port", type=int, default=8000, help="Port (default 8000)")
    args = ap.parse_args()
    uvicorn.run(app, host=args.host, port=args.port)
