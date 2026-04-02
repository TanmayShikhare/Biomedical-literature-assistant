#!/usr/bin/env python3
"""Run LangGraph QA over indexed corpus (vector + graph context)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import json

from biomed_rag.config import get_settings
from biomed_rag.prompts import USER_FACING_DISCLAIMER
from biomed_rag.workflow import build_app


def main() -> None:
    p = argparse.ArgumentParser(description="Ask a research question over ingested PubMed slice.")
    p.add_argument("question", nargs="?", help="Question (or pass via stdin).")
    p.add_argument("--debug", action="store_true", help="Print retrieved PMIDs and top passages.")
    args = p.parse_args()

    q = args.question
    if not q and not sys.stdin.isatty():
        q = sys.stdin.read().strip()
    if not q:
        p.error("Provide a question as an argument or on stdin.")

    settings = get_settings()
    app = build_app(settings)
    out = app.invoke(
        {
            "question": q,
            "focus_terms": "",
            "allowed_pmids": "",
            "passages": "",
            "top_passages": [],
            "graph_text": "",
            "outcomes_json": "[]",
            "answer": "",
        }
    )

    print(USER_FACING_DISCLAIMER)
    print()
    if args.debug:
        print("Allowed PMIDs:", out.get("allowed_pmids", ""))
        print("Focus terms:", out.get("focus_terms", ""))
        print()
        print("Top passages (reranked):")
        for i, psg in enumerate(out.get("top_passages", [])[:8], start=1):
            pmid = psg.get("pmid", "")
            title = (psg.get("title", "") or "").strip()
            snippet = (psg.get("snippet", "") or "").strip().replace("\n", " ")
            print(f"{i}. [PMID:{pmid}] {title}")
            print(f"   {snippet[:260]}")
        print()
        print("Extracted outcomes JSON:")
        try:
            obj = json.loads(out.get("outcomes_json", "[]") or "[]")
            print(json.dumps(obj, indent=2, ensure_ascii=False))
        except Exception:
            print(out.get("outcomes_json", "[]"))
        print()
    print(out.get("answer", ""))


if __name__ == "__main__":
    main()
