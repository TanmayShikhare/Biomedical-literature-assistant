#!/usr/bin/env python3
"""Extract triples from data/articles.jsonl into data/triples.jsonl (no Chroma re-ingest). Requires Ollama."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from biomed_rag.config import get_settings
from biomed_rag.extraction import extract_triples_from_abstract
from biomed_rag.knowledge_graph import append_triples_jsonl


def _pmids_with_triples(path: Path) -> set[str]:
    if not path.exists():
        return set()
    out: set[str] = set()
    with path.open(encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                o = json.loads(line)
            except json.JSONDecodeError:
                continue
            p = o.get("pmid")
            if p:
                out.add(str(p))
    return out


def main() -> None:
    p = argparse.ArgumentParser(description="Backfill triples.jsonl from articles.jsonl (Ollama).")
    p.add_argument("--limit", type=int, default=400, help="Max articles to process (default 400).")
    p.add_argument(
        "--force",
        action="store_true",
        help="Re-extract even if PMID already appears in triples.jsonl.",
    )
    args = p.parse_args()

    settings = get_settings()
    manifest = settings.articles_manifest_path
    triples_path = settings.triples_path

    if not manifest.exists():
        print(f"Missing {manifest}. Run ingest first.", file=sys.stderr)
        sys.exit(1)

    already = set() if args.force else _pmids_with_triples(triples_path)
    done = 0
    skipped = 0
    errors = 0

    with manifest.open(encoding="utf-8") as f:
        for line in f:
            if done >= args.limit:
                break
            line = line.strip()
            if not line:
                continue
            try:
                art = json.loads(line)
            except json.JSONDecodeError:
                continue
            pmid = str(art.get("pmid", "")).strip()
            title = art.get("title") or ""
            abstract = art.get("abstract") or ""
            if not pmid or not abstract:
                continue
            if pmid in already:
                skipped += 1
                continue
            try:
                triples = extract_triples_from_abstract(title, abstract, settings)
                if triples:
                    append_triples_jsonl(triples_path, triples, pmid)
                already.add(pmid)
                done += 1
                if done % 10 == 0:
                    print(f"  extracted {done}/{args.limit} articles…", flush=True)
            except Exception as e:
                print(f"  skip PMID {pmid}: {e}", file=sys.stderr)
                errors += 1
                already.add(pmid)
                done += 1

    print(f"Done. processed_new={done} skipped_existing={skipped} errors={errors}")
    print(f"Triples file: {triples_path}")


if __name__ == "__main__":
    main()
