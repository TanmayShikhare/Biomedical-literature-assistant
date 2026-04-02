"""Fuse dense and BM25 rankings with reciprocal rank fusion (RRF)."""

from __future__ import annotations

from collections import defaultdict
from typing import Any


def reciprocal_rank_fusion(
    dense_hits: list[dict[str, Any]],
    sparse_hits: list[dict[str, Any]],
    rrf_k: int = 60,
    top_n: int = 40,
) -> list[dict[str, Any]]:
    """
    RRF: score(chunk) = sum 1/(k + rank) across rankers.
    chunk_id must be present on hits.
    """
    scores: defaultdict[str, float] = defaultdict(float)
    by_id: dict[str, dict[str, Any]] = {}

    for rank, h in enumerate(dense_hits):
        cid = h.get("chunk_id")
        if not cid:
            continue
        scores[cid] += 1.0 / (rrf_k + rank + 1)
        by_id[cid] = dict(h)

    for rank, h in enumerate(sparse_hits):
        cid = h.get("chunk_id")
        if not cid:
            continue
        scores[cid] += 1.0 / (rrf_k + rank + 1)
        if cid not in by_id:
            by_id[cid] = dict(h)
        else:
            # Prefer dense hit metadata if present; merge bm25_score if useful
            if h.get("bm25_score") is not None:
                by_id[cid]["bm25_score"] = h.get("bm25_score")

    ordered = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)[:top_n]
    return [by_id[cid] for cid in ordered if cid in by_id]
