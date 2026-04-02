#!/usr/bin/env python3
"""
Fit topic model (LDA on TF–IDF) over ingested abstracts in data/articles.jsonl.

Run after: python scripts/ingest.py ... (builds articles.jsonl).
Output: JSON with topic keywords and dominant topic id per PMID.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from sklearn.decomposition import LatentDirichletAllocation
from sklearn.feature_extraction.text import TfidfVectorizer

from biomed_rag.config import get_settings
from biomed_rag.corpus_articles import load_articles_manifest


def main() -> None:
    p = argparse.ArgumentParser(description="LDA topics over articles.jsonl")
    p.add_argument(
        "--n-topics",
        type=int,
        default=12,
        help="Number of LDA topics (clamped to corpus size).",
    )
    p.add_argument(
        "--out",
        type=str,
        default=None,
        help="Output JSON path (default: DATA_DIR/topic_model.json).",
    )
    p.add_argument(
        "--top-words",
        type=int,
        default=15,
        help="Top keywords per topic.",
    )
    args = p.parse_args()
    settings = get_settings()
    manifest = settings.articles_manifest_path
    if not manifest.exists():
        print(
            f"No {manifest}. Run ingest first (articles.jsonl is written during ingest).",
            file=sys.stderr,
        )
        sys.exit(1)

    by_pmid = load_articles_manifest(manifest)
    pmids: list[str] = sorted(by_pmid.keys(), key=lambda x: int(x) if x.isdigit() else x)
    texts: list[str] = []
    for pmid in pmids:
        a = by_pmid[pmid]
        texts.append(f"{a.get('title', '')}\n{a.get('abstract', '')}".strip())

    n_docs = len(texts)
    if n_docs < 3:
        print("Need at least 3 documents for topic modeling.", file=sys.stderr)
        sys.exit(1)

    n_topics = max(2, min(args.n_topics, n_docs - 1))
    min_df = 2 if n_docs >= 20 else 1

    vectorizer = TfidfVectorizer(
        max_df=0.85,
        min_df=min_df,
        max_features=20_000,
        stop_words="english",
        ngram_range=(1, 2),
    )
    X = vectorizer.fit_transform(texts)
    lda = LatentDirichletAllocation(
        n_components=n_topics,
        max_iter=30,
        learning_method="batch",
        random_state=42,
        n_jobs=1,
    )
    doc_topic = lda.fit_transform(X)
    names = vectorizer.get_feature_names_out()

    topics_out: list[dict[str, Any]] = []
    for k in range(n_topics):
        top = lda.components_[k].argsort()[-args.top_words :][::-1]
        topics_out.append(
            {
                "topic_id": k,
                "keywords": [str(names[i]) for i in top],
            }
        )

    assignments: dict[str, int] = {}
    for i, pmid in enumerate(pmids):
        assignments[pmid] = int(doc_topic[i].argmax())

    out_path = Path(args.out) if args.out else settings.articles_manifest_path.parent / "topic_model.json"
    if not out_path.is_absolute():
        out_path = ROOT / out_path
    out_path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "method": "lda_tfidf",
        "n_topics": n_topics,
        "n_documents": n_docs,
        "topics": topics_out,
        "dominant_topic_by_pmid": assignments,
    }
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {out_path} ({n_topics} topics, {n_docs} docs)")


if __name__ == "__main__":
    main()
