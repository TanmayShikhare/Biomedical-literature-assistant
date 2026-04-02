"""Split title + abstract into overlapping text chunks for embedding."""

from __future__ import annotations


def chunk_text(
    text: str,
    max_chars: int = 1200,
    overlap: int = 150,
) -> list[str]:
    text = text.strip()
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]

    chunks: list[str] = []
    start = 0
    n = len(text)
    while start < n:
        end = min(start + max_chars, n)
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= n:
            break
        start = end - overlap
        if start < 0:
            start = 0
    return chunks


def article_to_chunks(article: dict[str, str]) -> list[dict[str, str]]:
    """Return chunk dicts with pmid, chunk_index, text."""
    body = f"{article['title']}\n\n{article['abstract']}".strip()
    texts = chunk_text(body)
    out: list[dict[str, str]] = []
    for i, t in enumerate(texts):
        out.append(
            {
                "pmid": article["pmid"],
                "title": article["title"],
                "chunk_index": str(i),
                "text": t,
            }
        )
    return out
