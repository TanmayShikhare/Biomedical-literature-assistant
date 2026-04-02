#!/usr/bin/env python3
"""
Suggest PMIDs from data/articles.jsonl for building retrieval_eval.json.

Greps title+abstract (case-insensitive). Requires ingest + backfill_articles_manifest.

Example:
  PYTHONPATH=src python scripts/suggest_eval_pmids.py tirzepatide semaglutide
  PYTHONPATH=src python scripts/suggest_eval_pmids.py --limit 5 "weight loss" GLP-1
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "data" / "articles.jsonl"


def main() -> None:
    p = argparse.ArgumentParser(description="Find PMIDs in articles.jsonl matching keywords.")
    p.add_argument("keywords", nargs="*", help="Words that must all appear (title or abstract).")
    p.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST, help="Path to articles.jsonl")
    p.add_argument("--limit", type=int, default=20, help="Max rows to print")
    args = p.parse_args()

    path = args.manifest if args.manifest.is_absolute() else ROOT / args.manifest
    if not path.exists():
        print(f"Missing {path}. Run ingest or backfill_articles_manifest.py.", file=sys.stderr)
        sys.exit(1)

    kws = [k.lower() for k in args.keywords if k.strip()]
    if not kws:
        print("Provide at least one keyword.", file=sys.stderr)
        sys.exit(1)

    n = 0
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                o = json.loads(line)
            except json.JSONDecodeError:
                continue
            blob = f"{o.get('title', '')} {o.get('abstract', '')}".lower()
            if all(kw in blob for kw in kws):
                pmid = o.get("pmid", "")
                title = (o.get("title") or "")[:100]
                print(f"{pmid}\t{title}")
                n += 1
                if n >= args.limit:
                    break

    if n == 0:
        print("No matches. Try fewer or different keywords.", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
