"""Optional LDA topic hints from data/topic_model.json (see scripts/topics_fit.py)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

# (resolved_path_str, mtime_ns, pmid -> {topic_id, topic_keywords})
_lookup_cache: tuple[str, int, dict[str, dict[str, Any]]] | None = None


def _load_raw(path: Path) -> Optional[dict[str, Any]]:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def load_topic_lookup(path: Path) -> Optional[dict[str, dict[str, Any]]]:
    """PMID string -> {topic_id: int, topic_keywords: list[str]}. None if file missing."""
    global _lookup_cache
    if not path.is_file():
        return None
    key = str(path.resolve())
    try:
        mtime_ns = path.stat().st_mtime_ns
    except OSError:
        return None
    if _lookup_cache is not None and _lookup_cache[0] == key and _lookup_cache[1] == mtime_ns:
        return _lookup_cache[2]

    data = _load_raw(path)
    if not data:
        return None
    topics: dict[int, list[str]] = {}
    for t in data.get("topics", []):
        tid = t.get("topic_id")
        if isinstance(tid, int):
            topics[tid] = [str(x) for x in t.get("keywords", []) if x]

    lookup: dict[str, dict[str, Any]] = {}
    for pmid, tid in data.get("dominant_topic_by_pmid", {}).items():
        p = str(pmid).strip()
        if not p:
            continue
        try:
            k = int(tid)
        except (TypeError, ValueError):
            continue
        lookup[p] = {
            "topic_id": k,
            "topic_keywords": topics.get(k, []),
        }

    _lookup_cache = (key, mtime_ns, lookup)
    return lookup


def enrich_passages_with_topics(
    passages: list[dict],
    path: Path,
    *,
    max_keywords: int = 8,
) -> None:
    """In-place: add topic_id and topic_keywords when topic_model.json exists."""
    lookup = load_topic_lookup(path)
    if not lookup:
        return
    for row in passages:
        pmid = str(row.get("pmid", "") or "").strip()
        if not pmid:
            continue
        info = lookup.get(pmid)
        if not info:
            continue
        kws = info["topic_keywords"][:max_keywords]
        row["topic_id"] = info["topic_id"]
        row["topic_keywords"] = kws
