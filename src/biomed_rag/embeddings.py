"""Local sentence embeddings."""

from __future__ import annotations

from functools import lru_cache

from sentence_transformers import SentenceTransformer

from biomed_rag.config import Settings


@lru_cache(maxsize=1)
def get_embedding_model(model_id: str) -> SentenceTransformer:
    return SentenceTransformer(model_id)


def embed_texts(texts: list[str], settings: Settings) -> list[list[float]]:
    model = get_embedding_model(settings.embedding_model)
    vectors = model.encode(
        texts,
        convert_to_numpy=True,
        show_progress_bar=len(texts) > 32,
    )
    return vectors.tolist()
