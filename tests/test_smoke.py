"""Smoke tests — no network, no Ollama."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def test_expand_triples_entity_overlap():
    from biomed_rag.knowledge_graph import expand_triples_by_shared_entities

    seed = [
        {
            "head": "semaglutide",
            "head_type": "drug",
            "relation": "treats",
            "tail": "obesity",
            "tail_type": "disease",
            "pmid": "111",
        }
    ]
    corpus = seed + [
        {
            "head": "semaglutide",
            "head_type": "drug",
            "relation": "compared_with",
            "tail": "liraglutide",
            "tail_type": "drug",
            "pmid": "222",
        },
        {
            "head": "aspirin",
            "head_type": "drug",
            "relation": "treats",
            "tail": "pain",
            "tail_type": "disease",
            "pmid": "333",
        },
    ]
    extra = expand_triples_by_shared_entities(seed, corpus, max_extra=10)
    assert len(extra) == 1
    assert extra[0]["pmid"] == "222"


def test_rrf_fusion():
    from biomed_rag.hybrid import reciprocal_rank_fusion

    d = [{"chunk_id": "a", "text": "x"}, {"chunk_id": "b", "text": "y"}]
    s = [{"chunk_id": "b", "text": "y"}, {"chunk_id": "c", "text": "z"}]
    fused = reciprocal_rank_fusion(d, s, rrf_k=60, top_n=10)
    ids = [x["chunk_id"] for x in fused]
    assert "b" in ids


def test_rerank_short_circuit():
    from biomed_rag.config import Settings
    from biomed_rag.rerank import rerank_passages

    s = Settings()
    hits = [{"text": "a", "pmid": "1"}]
    out = rerank_passages("q", hits, top_k=5, settings=s)
    assert len(out) == 1


def test_adjust_direction_incidence_not_worsened():
    from biomed_rag.outcomes import _adjust_direction

    assert (
        _adjust_direction(
            "worsened",
            "hypoglycemia",
            "Hypoglycemia was reported in 0.4% of those who received semaglutide.",
        )
        == "reported_incidence"
    )


def test_pmids_for_evidence_substring_match():
    from biomed_rag.outcomes import _pmids_for_evidence

    passages = (
        "[PMID:34170647] Tirzepatide versus Semaglutide\n"
        "hypoglycemia was reported in 0.4% of those who received semaglutide.\n"
        "---\n"
        "[PMID:36871874] Oral semaglutide review\n"
        "Reduced HbA1c by 1.06% (95% CI, 0.81-1.30).\n"
    )
    allowed = {"34170647", "36871874"}
    pm_hypo = _pmids_for_evidence(
        passages,
        "hypoglycemia was reported in 0.4% of those who received semaglutide.",
        allowed,
        ["26308095", "34170647", "36871874"],
    )
    assert pm_hypo == ["34170647"]
    pm_hba1c = _pmids_for_evidence(
        passages,
        "Reduced HbA1c by 1.06% (95% CI, 0.81-1.30)",
        allowed,
        [],
    )
    assert pm_hba1c == ["36871874"]


def test_dedupe_outcomes():
    from biomed_rag.outcomes import _dedupe_outcomes

    rows = [
        {"outcome": "HbA1c", "direction": "decreased"},
        {"outcome": "hba1c", "direction": "unclear"},
        {"outcome": "Weight", "direction": "decreased"},
    ]
    out = _dedupe_outcomes(rows)
    assert len(out) == 2
    assert {r["outcome"] for r in out} == {"HbA1c", "Weight"}


def test_merge_articles_manifest(tmp_path):
    from biomed_rag.corpus_articles import load_articles_manifest, merge_articles_manifest

    p = tmp_path / "articles.jsonl"
    merge_articles_manifest(
        p,
        [{"pmid": "1", "title": "A", "abstract": "alpha"}],
    )
    merge_articles_manifest(
        p,
        [{"pmid": "2", "title": "B", "abstract": "beta"}],
    )
    m = load_articles_manifest(p)
    assert len(m) == 2
    assert m["1"]["title"] == "A"
    merge_articles_manifest(
        p,
        [{"pmid": "1", "title": "A2", "abstract": "alpha2"}],
    )
    m2 = load_articles_manifest(p)
    assert m2["1"]["title"] == "A2"


def test_graph_summary():
    from biomed_rag.knowledge_graph import build_networkx, graph_summary

    triples = [
        {
            "head": "semaglutide",
            "head_type": "drug",
            "relation": "treats",
            "tail": "diabetes",
            "tail_type": "disease",
            "pmid": "1",
        }
    ]
    g = build_networkx(triples)
    s = graph_summary(g)
    assert s["nodes"] == 2
    assert s["edges"] >= 1


def test_focus_terms_from_question():
    from biomed_rag.workflow import _focus_terms_from_question

    assert "semaglutide" in _focus_terms_from_question("semaglutide in T2DM").lower()
    assert _focus_terms_from_question("diabetes") == "(none)"


def test_outcomes_list_from_parsed_accepts_wrapped_or_raw_list():
    from biomed_rag.outcomes import _outcomes_list_from_parsed

    assert _outcomes_list_from_parsed({"outcomes": [{"a": 1}]}) == [{"a": 1}]
    assert _outcomes_list_from_parsed([{"b": 2}]) == [{"b": 2}]
    assert _outcomes_list_from_parsed({}) == []
    assert _outcomes_list_from_parsed("x") == []


def test_enrich_passages_with_topics(tmp_path):
    import json

    from biomed_rag.topic_context import enrich_passages_with_topics

    path = tmp_path / "topic_model.json"
    path.write_text(
        json.dumps(
            {
                "topics": [{"topic_id": 1, "keywords": ["obesity", "weight", "glp"]}],
                "dominant_topic_by_pmid": {"123": 1},
            }
        ),
        encoding="utf-8",
    )
    passages = [{"pmid": "123", "title": "T", "snippet": "x"}]
    enrich_passages_with_topics(passages, path, max_keywords=2)
    assert passages[0]["topic_id"] == 1
    assert passages[0]["topic_keywords"] == ["obesity", "weight"]


def test_clamp_answer_pmids_to_allowed():
    from biomed_rag.workflow import _clamp_answer_pmids_to_allowed, _parse_allowed_pmids

    allowed = _parse_allowed_pmids("11111111, 22222222")
    s = (
        "According to [PMID:11111111], ok. According to [PMID:29432006], bad. "
        "See also PMID: 29432006 and PMID:11111111."
    )
    out = _clamp_answer_pmids_to_allowed(s, allowed)
    assert "11111111" in out
    assert "29432006" not in out
    assert "According to the retrieved excerpts" in out
