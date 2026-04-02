"""PMID-grounded triple store (JSONL) + optional NetworkX view."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import networkx as nx

Triple = dict[str, Any]


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _canonical_entity(s: str) -> str:
    return " ".join(str(s or "").split()).strip()


def append_triples_jsonl(path: Path, triples: list[Triple], pmid: str) -> None:
    ensure_parent(path)
    with path.open("a", encoding="utf-8") as f:
        for t in triples:
            rec = {
                "head": _canonical_entity(str(t.get("head", ""))),
                "head_type": t.get("head_type", "other"),
                "relation": str(t.get("relation", "related_to")).strip(),
                "tail": _canonical_entity(str(t.get("tail", ""))),
                "tail_type": t.get("tail_type", "other"),
                "pmid": pmid,
            }
            if not rec["head"] or not rec["tail"]:
                continue
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def load_triples_for_pmids(path: Path, pmids: set[str]) -> list[Triple]:
    if not path.exists() or not pmids:
        return []
    out: list[Triple] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("pmid") in pmids:
                out.append(rec)
    return out


def triples_to_context_text(triples: list[Triple], max_triples: int = 100) -> str:
    if not triples:
        return "(No graph triples for these PMIDs — run ingest without --skip-graph.)"
    lines: list[str] = []
    for t in triples[:max_triples]:
        lines.append(
            f"[PMID:{t.get('pmid','')}] ({t.get('head_type')}:{t.get('head')}) "
            f"--{t.get('relation')}--> ({t.get('tail_type')}:{t.get('tail')})"
        )
    return "\n".join(lines)


_triples_cache: list[Triple] | None = None
_triples_cache_path: Path | None = None


def load_all_triples(path: Path) -> list[Triple]:
    """Load full triple corpus (cached per path for query-time expansion)."""
    global _triples_cache, _triples_cache_path
    if _triples_cache is not None and _triples_cache_path == path:
        return _triples_cache
    if not path.exists():
        _triples_cache, _triples_cache_path = [], path
        return []
    out: list[Triple] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
                out.append(rec)
            except json.JSONDecodeError:
                continue
    _triples_cache, _triples_cache_path = out, path
    return out


def clear_triples_cache() -> None:
    global _triples_cache, _triples_cache_path
    _triples_cache, _triples_cache_path = None, None


def _norm_entity(s: str) -> str:
    return str(s or "").strip().lower()


def expand_triples_by_shared_entities(
    seed_triples: list[Triple],
    corpus_triples: list[Triple],
    max_extra: int,
) -> list[Triple]:
    """
    Add triples from other PMIDs that share at least one entity (head/tail) with seed triples.
    Enables multi-document graph context without changing vector retrieval.
    """
    if not seed_triples or not corpus_triples or max_extra <= 0:
        return []

    entities: set[str] = set()
    for t in seed_triples:
        entities.add(_norm_entity(t.get("head", "")))
        entities.add(_norm_entity(t.get("tail", "")))
    entities.discard("")

    seen: set[tuple[str, str, str, str]] = set()
    for t in seed_triples:
        seen.add(
            (
                str(t.get("pmid", "")),
                _norm_entity(t.get("head", "")),
                str(t.get("relation", "")),
                _norm_entity(t.get("tail", "")),
            )
        )

    extra: list[Triple] = []
    for t in corpus_triples:
        if _norm_entity(t.get("head", "")) in entities or _norm_entity(t.get("tail", "")) in entities:
            key = (
                str(t.get("pmid", "")),
                _norm_entity(t.get("head", "")),
                str(t.get("relation", "")),
                _norm_entity(t.get("tail", "")),
            )
            if key in seen:
                continue
            seen.add(key)
            extra.append(t)
            if len(extra) >= max_extra:
                break
    return extra


def build_networkx(triples: list[Triple]) -> nx.MultiDiGraph:
    g = nx.MultiDiGraph()
    for t in triples:
        h = str(t.get("head", "")).strip()
        r = str(t.get("tail", "")).strip()
        if not h or not r:
            continue
        g.add_node(h, entity_type=t.get("head_type", "other"))
        g.add_node(r, entity_type=t.get("tail_type", "other"))
        g.add_edge(
            h,
            r,
            relation=t.get("relation", "related_to"),
            pmid=t.get("pmid", ""),
        )
    return g


def graph_summary(g: nx.MultiDiGraph) -> dict[str, Any]:
    n = g.number_of_nodes()
    m = g.number_of_edges()
    return {
        "nodes": n,
        "edges": m,
        "density": float(nx.density(g)) if n > 1 else 0.0,
        "weakly_connected_components": nx.number_weakly_connected_components(g),
    }
