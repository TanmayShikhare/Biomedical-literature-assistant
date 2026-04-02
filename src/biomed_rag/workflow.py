"""LangGraph workflow: retrieve → extract outcome hints → synthesize answer."""

from __future__ import annotations

import json
import re
from typing import Any, TypedDict

from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph

from biomed_rag.bm25_index import bm25_top_hits, load_bm25_index
from biomed_rag.config import Settings
from biomed_rag.embeddings import embed_texts
from biomed_rag.hybrid import reciprocal_rank_fusion
from biomed_rag.knowledge_graph import (
    expand_triples_by_shared_entities,
    load_all_triples,
    load_triples_for_pmids,
    triples_to_context_text,
)
from biomed_rag.prompts import SYNTHESIS_USER_TEMPLATE, SYSTEM_RESEARCH_ASSISTANT
from biomed_rag.rerank import rerank_passages
from biomed_rag.topic_context import enrich_passages_with_topics
from biomed_rag.vector_index import query_similar
from biomed_rag.outcomes import extract_outcomes_from_excerpts

_PMID_LINK_RE = re.compile(r"\[PMID:(\d+)\]\(#\)")
# Model sometimes writes table cells as [39248221] instead of [PMID:39248221]
_BARE_PMID_BRACKET_RE = re.compile(r"\[(?!PMID:)(\d{7,10})\]")
# Bracket citations (after normalize); disallowed IDs are stripped entirely.
_PMID_CITATION_RE = re.compile(r"\[PMID:(\d+)\]", re.IGNORECASE)


def _normalize_answer_pmids(answer: str) -> str:
    answer = _PMID_LINK_RE.sub(r"[PMID:\1]", answer)
    answer = _BARE_PMID_BRACKET_RE.sub(r"[PMID:\1]", answer)
    return answer


def _parse_allowed_pmids(allowed_field: str) -> set[str]:
    """Same rules as scripts/eval_smoke._allowed_set."""
    if not allowed_field or allowed_field.strip().startswith("(none"):
        return set()
    return {p.strip() for p in allowed_field.split(",") if p.strip().isdigit()}


def _clamp_answer_pmids_to_allowed(answer: str, allowed: set[str]) -> str:
    """Drop PMID citations not in the retrieval whitelist (eval + honest grounding)."""
    if not allowed:
        return answer

    def bracket_repl(m: re.Match) -> str:
        return m.group(0) if m.group(1) in allowed else ""

    s = _PMID_CITATION_RE.sub(bracket_repl, answer)

    def bare_repl(m: re.Match) -> str:
        return m.group(0) if m.group(1) in allowed else ""

    s = re.sub(r"PMID[:\s]+(\d+)", bare_repl, s, flags=re.IGNORECASE)

    # Common broken attributions after stripping a bracket citation
    s = re.sub(r"According to\s*,\s*", "According to the retrieved excerpts, ", s)
    s = re.sub(r"The excerpt for\s*,\s*", "In the retrieved excerpts, ", s)
    s = re.sub(r"  +", " ", s)
    return s


def _focus_terms_from_question(question: str) -> str:
    """Light hint for the prompt only; does not filter retrieval."""
    q = question.lower()
    found: list[str] = []
    for term in ("semaglutide", "tirzepatide", "liraglutide", "oral semaglutide"):
        if term in q:
            found.append(term)
    return ", ".join(found) if found else "(none)"


def run_retrieve(state: QAState, settings: Settings) -> QAState:
    """Dense (+BM25 RRF) → cross-encoder rerank → graph context. No post-hoc answer forcing."""
    q = state["question"]
    q_emb = embed_texts([q], settings)[0]
    dense = query_similar(q_emb, k=settings.retrieval_top_k, settings=settings)
    if settings.use_hybrid_retrieval and load_bm25_index(settings) is not None:
        sparse = bm25_top_hits(q, settings.retrieval_top_k, settings=settings)
        wide = reciprocal_rank_fusion(
            dense,
            sparse,
            rrf_k=settings.rrf_k,
            top_n=settings.retrieval_top_k,
        )
    else:
        wide = dense
    hits = rerank_passages(q, wide, top_k=settings.rerank_top_k, settings=settings)

    blocks: list[str] = []
    top_passages: list[dict] = []
    pmids: set[str] = set()
    for h in hits:
        pmid = h.get("pmid", "")
        if pmid:
            pmids.add(pmid)
        top_passages.append(
            {
                "chunk_id": h.get("chunk_id", ""),
                "pmid": pmid,
                "title": h.get("title", ""),
                "chunk_index": h.get("chunk_index", ""),
                "snippet": (h.get("text", "") or "")[:600],
            }
        )
        blocks.append(f"[PMID:{pmid}] {h.get('title','')}\n{h.get('text','')}\n")
    passages = "\n---\n".join(blocks) if blocks else "(No retrieved passages.)"

    enrich_passages_with_topics(top_passages, settings.topic_model_path)

    seed_triples = load_triples_for_pmids(settings.triples_path, pmids)
    graph_triples = list(seed_triples)

    if settings.graph_expand_entities and seed_triples:
        corpus = load_all_triples(settings.triples_path)
        expanded = expand_triples_by_shared_entities(
            seed_triples,
            corpus,
            max_extra=settings.graph_expand_max_extra_triples,
        )
        graph_triples.extend(expanded)
        for t in expanded:
            p = str(t.get("pmid", ""))
            if p:
                pmids.add(p)

    graph_text = triples_to_context_text(graph_triples, max_triples=200)
    allowed = ", ".join(sorted(pmids)) if pmids else "(none — retrieval empty)"
    return {
        **state,
        "focus_terms": _focus_terms_from_question(q),
        "allowed_pmids": allowed,
        "passages": passages,
        "top_passages": top_passages,
        "graph_text": graph_text,
    }


class QAState(TypedDict):
    question: str
    focus_terms: str
    allowed_pmids: str
    passages: str
    top_passages: list[dict]
    graph_text: str
    outcomes_json: str
    answer: str


def build_app(settings: Settings):
    def retrieve(state: QAState) -> QAState:
        return run_retrieve(state, settings)

    def synthesize(state: QAState) -> QAState:
        llm = ChatOllama(
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
            temperature=settings.ollama_temperature,
        )
        user = SYNTHESIS_USER_TEMPLATE.format(
            question=state["question"],
            focus_terms=state.get("focus_terms", "(none)"),
            allowed_pmids=state.get("allowed_pmids", "(none)"),
            passages=state["passages"],
            graph_text=state["graph_text"],
            outcomes_json=state.get("outcomes_json", "[]"),
        )
        messages = [
            SystemMessage(content=SYSTEM_RESEARCH_ASSISTANT),
            HumanMessage(content=user),
        ]
        resp = llm.invoke(messages)
        answer = resp.content if hasattr(resp, "content") else str(resp)
        answer = _normalize_answer_pmids(answer)
        allowed = _parse_allowed_pmids(state.get("allowed_pmids", ""))
        answer = _clamp_answer_pmids_to_allowed(answer, allowed)
        return {**state, "answer": answer}

    def extract_outcomes(state: QAState) -> QAState:
        outcomes = extract_outcomes_from_excerpts(
            question=state["question"],
            focus_terms=state.get("focus_terms", "(none)"),
            allowed_pmids=state.get("allowed_pmids", "(none)"),
            passages=state["passages"],
            settings=settings,
        )
        return {**state, "outcomes_json": json.dumps(outcomes, ensure_ascii=False)}

    g = StateGraph(QAState)
    g.add_node("retrieve", retrieve)
    g.add_node("extract_outcomes", extract_outcomes)
    g.add_node("synthesize", synthesize)
    g.add_edge(START, "retrieve")
    g.add_edge("retrieve", "extract_outcomes")
    g.add_edge("extract_outcomes", "synthesize")
    g.add_edge("synthesize", END)
    return g.compile()
