#!/usr/bin/env python3
"""Run bundled eval questions; optionally flag PMID citations outside the retrieval whitelist."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from biomed_rag.config import get_settings
from biomed_rag.workflow import build_app


def _pmids_in_answer(text: str) -> set[str]:
    out: set[str] = set()
    for m in re.finditer(r"PMID[:\s]+(\d+)", text, flags=re.IGNORECASE):
        out.add(m.group(1))
    return out


def _allowed_set(allowed_field: str) -> set[str]:
    if not allowed_field or allowed_field.startswith("(none"):
        return set()
    return {p.strip() for p in allowed_field.split(",") if p.strip().isdigit()}


def main() -> None:
    p = argparse.ArgumentParser(description="Run smoke eval questions from data/eval_questions.json")
    p.add_argument(
        "--json",
        type=Path,
        default=ROOT / "data" / "eval_questions.json",
        help="Path to eval JSON",
    )
    args = p.parse_args()

    data = json.loads(args.json.read_text(encoding="utf-8"))
    items = data.get("questions", [])
    settings = get_settings()
    app = build_app(settings)

    print(f"Running {len(items)} questions…\n")
    for item in items:
        qid = item.get("id", "?")
        q = item["text"]
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
        allowed = _allowed_set(out.get("allowed_pmids", ""))
        cited = _pmids_in_answer(out.get("answer", ""))
        bad = cited - allowed
        status = "OK" if not bad else f"WARN: cited PMIDs not in retrieval whitelist: {sorted(bad)}"
        print(f"--- [{qid}] ---")
        print(status)
        print(f"allowed count={len(allowed)} cited count={len(cited)}")
        print()
    print("Done.")


if __name__ == "__main__":
    main()
