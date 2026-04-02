#!/usr/bin/env python3
"""Fetch PubMed articles, embed into Chroma, optionally extract KG triples via Ollama."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from biomed_rag.chunking import article_to_chunks
from biomed_rag.config import get_settings
from biomed_rag.corpus_articles import merge_articles_manifest
from biomed_rag.embeddings import embed_texts
from biomed_rag.extraction import extract_triples_from_abstract
from biomed_rag.bm25_index import build_and_save, delete_bm25_file
from biomed_rag.knowledge_graph import append_triples_jsonl, clear_triples_cache
from biomed_rag.pubmed_fetch import fetch_articles_for_pmids, search_pubmed_ids
from biomed_rag.vector_index import reset_collection, upsert_chunks


def main() -> None:
    settings_early = get_settings()
    p = argparse.ArgumentParser(description="Ingest PubMed slice into vector index + graph triples.")
    p.add_argument(
        "--max-papers",
        type=int,
        default=settings_early.default_ingest_max_papers,
        help=f"Max PubMed IDs to fetch (default from config: {settings_early.default_ingest_max_papers}).",
    )
    p.add_argument("--query", type=str, default=None, help="PubMed search query (esearch syntax).")
    p.add_argument("--reset", action="store_true", help="Wipe Chroma collection and triples file.")
    p.add_argument("--skip-graph", action="store_true", help="Skip Ollama triple extraction.")
    p.add_argument(
        "--max-triple-articles",
        type=int,
        default=None,
        metavar="N",
        help="Only extract KG triples for the first N articles (after fetch order). "
        "Use with large --max-papers to keep a big vector index while capping slow Ollama work.",
    )
    args = p.parse_args()

    settings = get_settings()  # reload after .env
    if not settings.ncbi_email:
        print("Set NCBI_EMAIL in .env (required by NCBI Entrez).", file=sys.stderr)
        sys.exit(1)

    query = args.query or settings.default_pubmed_query
    settings.chroma_path.parent.mkdir(parents=True, exist_ok=True)

    if args.reset:
        reset_collection(settings)
        tp = settings.triples_path
        if tp.exists():
            tp.unlink()
        ap = settings.articles_manifest_path
        if ap.exists():
            ap.unlink()
        clear_triples_cache()
        delete_bm25_file(settings)
        print("Reset vector index, triples, article manifest, and BM25 index.")

    print("Searching PubMed:", query[:120] + ("..." if len(query) > 120 else ""))
    ids = search_pubmed_ids(query, args.max_papers, settings)
    print(f"Found {len(ids)} PMIDs (capped at {args.max_papers}).")
    if not ids:
        sys.exit(0)

    print("Fetching Medline records...")
    articles = fetch_articles_for_pmids(ids, settings)
    print(f"Loaded {len(articles)} articles with abstracts.")

    merge_articles_manifest(settings.articles_manifest_path, articles)
    print("Article manifest:", settings.articles_manifest_path)

    all_chunks: list[dict[str, str]] = []
    for a in articles:
        all_chunks.extend(article_to_chunks(a))

    print(f"Embedding {len(all_chunks)} chunks...")
    batch = 64
    for i in range(0, len(all_chunks), batch):
        sub = all_chunks[i : i + batch]
        embs = embed_texts([c["text"] for c in sub], settings)
        upsert_chunks(sub, embs, settings)
        print(f"  indexed {min(i + batch, len(all_chunks))}/{len(all_chunks)}")

    print("Building BM25 index (for hybrid retrieval)...")
    build_and_save(all_chunks, settings)
    print("BM25 saved next to data/.")

    if not args.skip_graph:
        triple_slice = articles
        if args.max_triple_articles is not None:
            n = max(0, args.max_triple_articles)
            triple_slice = articles[:n]
            print(
                f"Extracting triples with Ollama (first {len(triple_slice)}/{len(articles)} articles)..."
            )
        else:
            print("Extracting triples with Ollama (per article)...")
        for j, a in enumerate(triple_slice):
            try:
                triples = extract_triples_from_abstract(
                    a["title"], a["abstract"], settings
                )
                if triples:
                    append_triples_jsonl(settings.triples_path, triples, a["pmid"])
            except Exception as e:
                print(f"  skip PMID {a['pmid']}: {e}")
            if (j + 1) % 10 == 0:
                print(f"  processed {j + 1}/{len(triple_slice)} articles")
        print("Done. Triples at:", settings.triples_path)
    else:
        print("Skipped graph extraction (--skip-graph).")

    print("Chroma path:", settings.chroma_path)


if __name__ == "__main__":
    main()
