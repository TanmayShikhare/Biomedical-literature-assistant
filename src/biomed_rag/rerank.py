"""Cross-encoder reranking over (query, passage) pairs — standard two-stage dense RAG."""

from __future__ import annotations

from functools import lru_cache

from sentence_transformers import CrossEncoder

from biomed_rag.config import Settings


@lru_cache(maxsize=2)
def _get_cross_encoder(model_id: str) -> CrossEncoder:
    return CrossEncoder(model_id)


def rerank_passages(
    question: str,
    hits: list[dict],
    top_k: int,
    settings: Settings,
) -> list[dict]:
    """Rerank vector hits by cross-encoder relevance. `hits` items need `text` key."""
    if not hits or top_k <= 0:
        return []
    if not settings.use_cross_encoder_rerank or len(hits) == 1:
        return hits[:top_k]

    model = _get_cross_encoder(settings.cross_encoder_model)
    pairs = [(question, h.get("text", "")[:8000]) for h in hits]
    scores = model.predict(pairs, show_progress_bar=len(pairs) > 16)
    order = sorted(range(len(hits)), key=lambda i: float(scores[i]), reverse=True)
    return [hits[i] for i in order[:top_k]]
