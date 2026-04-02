"""ChromaDB vector index for abstract chunks."""

from __future__ import annotations

import chromadb
from chromadb.config import Settings as ChromaSettings

from biomed_rag.bm25_index import stable_chunk_id
from biomed_rag.config import Settings


def get_chroma_collection(settings: Settings):
    settings.chroma_path.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(
        path=str(settings.chroma_path),
        settings=ChromaSettings(anonymized_telemetry=False),
    )
    return client.get_or_create_collection(
        name=settings.chroma_collection,
        metadata={"description": "PubMed title+abstract chunks"},
    )


def reset_collection(settings: Settings) -> None:
    client = chromadb.PersistentClient(
        path=str(settings.chroma_path),
        settings=ChromaSettings(anonymized_telemetry=False),
    )
    try:
        client.delete_collection(settings.chroma_collection)
    except Exception:
        pass


def upsert_chunks(
    chunks: list[dict[str, str]],
    embeddings: list[list[float]],
    settings: Settings,
) -> None:
    if not chunks:
        return
    col = get_chroma_collection(settings)
    ids = [stable_chunk_id(c) for c in chunks]
    documents = [c["text"] for c in chunks]
    metadatas = [
        {
            "pmid": c["pmid"],
            "title": c["title"][:2000],
            "chunk_index": c["chunk_index"],
        }
        for c in chunks
    ]
    col.add(ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas)


def all_pmids_in_index(settings: Settings) -> set[str]:
    """Unique PMIDs present in Chroma metadata (for backfills / stats)."""
    col = get_chroma_collection(settings)
    try:
        n = col.count()
    except Exception:
        return set()
    if n <= 0:
        return set()
    res = col.get(limit=max(n, 1), include=["metadatas"])
    out: set[str] = set()
    for m in res.get("metadatas") or []:
        if m and m.get("pmid"):
            out.add(str(m["pmid"]).strip())
    return out


def query_similar(
    query_embedding: list[float],
    k: int,
    settings: Settings,
) -> list[dict]:
    col = get_chroma_collection(settings)
    res = col.query(
        query_embeddings=[query_embedding],
        n_results=k,
        include=["documents", "metadatas", "distances"],
    )
    out: list[dict] = []
    docs = res.get("documents") or [[]]
    metas = res.get("metadatas") or [[]]
    dists = res.get("distances") or [[]]
    # Chroma always returns ids at the top-level; some versions don't accept "ids" in include.
    idss = res.get("ids") or [[]]
    # If ids aren't present for some reason, fall back to deterministic pmid_cN.
    if not idss or not idss[0]:
        idss = [
            [
                stable_chunk_id(
                    {
                        "pmid": (m or {}).get("pmid", ""),
                        "chunk_index": (m or {}).get("chunk_index", ""),
                    }
                )
                for m in (metas[0] if metas else [])
            ]
        ]
    for doc, meta, dist, cid in zip(docs[0], metas[0], dists[0], idss[0]):
        out.append(
            {
                "chunk_id": cid,
                "text": doc,
                "pmid": meta.get("pmid", ""),
                "title": meta.get("title", ""),
                "chunk_index": meta.get("chunk_index", ""),
                "distance": dist,
            }
        )
    return out
