#!/usr/bin/env python3
"""Rebuild data/articles.jsonl from PMIDs found in Chroma (for topic modeling after older ingests)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from biomed_rag.config import get_settings
from biomed_rag.corpus_articles import merge_articles_manifest
from biomed_rag.pubmed_fetch import fetch_articles_for_pmids
from biomed_rag.vector_index import all_pmids_in_index


def main() -> None:
    p = argparse.ArgumentParser(description="Backfill articles.jsonl from Chroma PMIDs via PubMed.")
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Print PMID count only; do not fetch or write.",
    )
    args = p.parse_args()
    settings = get_settings()
    if not settings.ncbi_email:
        print("Set NCBI_EMAIL in .env", file=sys.stderr)
        sys.exit(1)

    pmids = sorted(all_pmids_in_index(settings), key=lambda x: int(x) if x.isdigit() else x)
    print(f"Unique PMIDs in Chroma: {len(pmids)}")
    if args.dry_run:
        return

    if not pmids:
        print("Chroma is empty; nothing to backfill.", file=sys.stderr)
        sys.exit(1)

    print("Fetching Medline records from NCBI (batched)...")
    articles = fetch_articles_for_pmids(pmids, settings)
    print(f"Got {len(articles)} articles with abstracts.")
    merge_articles_manifest(settings.articles_manifest_path, articles)
    print("Wrote", settings.articles_manifest_path)


if __name__ == "__main__":
    main()
