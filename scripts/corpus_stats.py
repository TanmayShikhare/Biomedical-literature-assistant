#!/usr/bin/env python3
"""Print corpus size: unique PMIDs in Chroma, manifest lines, triples lines."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from biomed_rag.config import get_settings
from biomed_rag.vector_index import all_pmids_in_index


def _count_lines(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open(encoding="utf-8", errors="replace") as f:
        return sum(1 for line in f if line.strip())


def main() -> None:
    s = get_settings()
    pmids = all_pmids_in_index(s)
    manifest = s.articles_manifest_path
    triples = s.triples_path

    print("Corpus stats (main dataset = PubMed slice in Chroma)")
    print(f"  unique_pmids_in_chroma: {len(pmids)}")
    print(f"  articles_manifest_lines: {_count_lines(manifest)}  ({manifest})")
    print(f"  triples_jsonl_lines: {_count_lines(triples)}  ({triples})")
    q = s.default_pubmed_query
    qdisp = (q[:120] + "…") if len(q) > 120 else q
    print(f"  default_pubmed_query (config): {qdisp}")
    print()
    print("To grow the corpus: ingest.py --reset --max-papers N (see RUNBOOK.md).")


if __name__ == "__main__":
    main()
