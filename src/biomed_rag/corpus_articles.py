"""Persist merged article records (PMID, title, abstract) for topic modeling and analytics."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def load_articles_manifest(path: Path) -> dict[str, dict[str, Any]]:
    """Load articles.jsonl into pmid -> record."""
    if not path.exists():
        return {}
    out: dict[str, dict[str, Any]] = {}
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            pmid = str(rec.get("pmid", "")).strip()
            if pmid:
                out[pmid] = rec
    return out


def merge_articles_manifest(path: Path, articles: list[dict[str, str]]) -> None:
    """
    Merge ingested articles into articles.jsonl (by PMID). Survives non-reset ingests.
    Each record: pmid, title, abstract.
    """
    existing = load_articles_manifest(path)
    for a in articles:
        pmid = str(a.get("pmid", "")).strip()
        if not pmid:
            continue
        existing[pmid] = {
            "pmid": pmid,
            "title": str(a.get("title", "")).strip(),
            "abstract": str(a.get("abstract", "")).strip(),
        }
    ensure_parent(path)
    with path.open("w", encoding="utf-8") as f:
        for pmid in sorted(existing.keys(), key=lambda x: int(x) if x.isdigit() else x):
            f.write(json.dumps(existing[pmid], ensure_ascii=False) + "\n")
