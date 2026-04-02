"""BM25Okapi index aligned with chunk IDs (built at ingest, loaded at query)."""

from __future__ import annotations

import pickle
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from rank_bm25 import BM25Okapi

from biomed_rag.config import Settings

_TOKEN_RE = re.compile(r"[a-z0-9]+", re.I)


def tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


def stable_chunk_id(chunk: dict[str, str]) -> str:
    return f"{chunk['pmid']}_c{chunk['chunk_index']}"


def bm25_pickle_path(settings: Settings) -> Path:
    root = Path(__file__).resolve().parents[2]
    p = settings.data_dir if settings.data_dir.is_absolute() else root / settings.data_dir
    return p / "bm25_index.pkl"


def build_and_save(chunks: list[dict[str, str]], settings: Settings) -> None:
    if not chunks:
        return
    tokenized_corpus = [tokenize(c["text"]) for c in chunks]
    bm25 = BM25Okapi(tokenized_corpus)
    ids = [stable_chunk_id(c) for c in chunks]
    payload = {
        "bm25": bm25,
        "ids": ids,
        "chunks": chunks,
    }
    path = bm25_pickle_path(settings)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as f:
        pickle.dump(payload, f, protocol=pickle.HIGHEST_PROTOCOL)


def delete_bm25_file(settings: Settings) -> None:
    p = bm25_pickle_path(settings)
    if p.exists():
        p.unlink()
    load_bm25_index_cached.cache_clear()


@lru_cache(maxsize=1)
def load_bm25_index_cached(path_str: str) -> dict[str, Any] | None:
    path = Path(path_str)
    if not path.exists():
        return None
    with path.open("rb") as f:
        return pickle.load(f)


def load_bm25_index(settings: Settings) -> dict[str, Any] | None:
    return load_bm25_index_cached(str(bm25_pickle_path(settings)))


def bm25_top_hits(query: str, k: int, settings: Settings) -> list[dict]:
    data = load_bm25_index(settings)
    if not data or k <= 0:
        return []
    bm25: BM25Okapi = data["bm25"]
    ids: list[str] = data["ids"]
    chunks: list[dict[str, str]] = data["chunks"]
    q = tokenize(query)
    scores = bm25.get_scores(q)
    ranked = sorted(range(len(scores)), key=lambda i: float(scores[i]), reverse=True)[:k]
    out: list[dict] = []
    for i in ranked:
        c = chunks[i]
        out.append(
            {
                "chunk_id": ids[i],
                "text": c["text"],
                "pmid": c["pmid"],
                "title": c.get("title", ""),
                "chunk_index": c.get("chunk_index", ""),
                "distance": 1.0 / (1.0 + max(float(scores[i]), 1e-9)),
                "bm25_score": float(scores[i]),
            }
        )
    return out
