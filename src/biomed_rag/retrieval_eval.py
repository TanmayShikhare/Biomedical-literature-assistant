"""Retrieval eval metrics (no LLM): must-include PMIDs vs retrieved whitelist."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Callable

from biomed_rag.workflow import run_retrieve


def allowed_pmids_from_state(allowed_str: str) -> set[str]:
    return set(re.findall(r"\d{5,10}", allowed_str or ""))


@dataclass
class RowResult:
    question: str
    must_include: set[str]
    hit: set[str]
    miss: set[str]
    ok: bool

    @property
    def pmid_recall(self) -> float:
        if not self.must_include:
            return 1.0
        return len(self.hit) / len(self.must_include)


def eval_rows(
    rows: list[dict[str, Any]],
    settings: Any,
    *,
    retrieve_fn: Callable[..., Any] | None = None,
) -> list[RowResult]:
    """Run retrieval for each eval row. `retrieve_fn` defaults to `run_retrieve` (inject for tests)."""
    fn = retrieve_fn or run_retrieve
    out: list[RowResult] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        q = row.get("question", "")
        must = row.get("must_include_pmids") or row.get("must_include") or []
        if isinstance(must, str):
            must = [must]
        must_set = {str(x).strip() for x in must if str(x).strip()}
        if not q or not must_set:
            continue
        state = fn(
            {
                "question": q,
                "focus_terms": "",
                "allowed_pmids": "",
                "passages": "",
                "top_passages": [],
                "graph_text": "",
                "outcomes_json": "[]",
                "answer": "",
            },
            settings,
        )
        got = allowed_pmids_from_state(state.get("allowed_pmids", ""))
        hit = must_set & got
        miss = must_set - got
        out.append(
            RowResult(
                question=q,
                must_include=must_set,
                hit=hit,
                miss=miss,
                ok=not miss,
            )
        )
    return out
