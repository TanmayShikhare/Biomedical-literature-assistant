"""Outcome extraction from retrieved excerpts via Ollama (strict JSON)."""

from __future__ import annotations

import json
import re
from typing import Iterable

from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage
from tenacity import retry, stop_after_attempt, wait_exponential

from biomed_rag.config import Settings
from biomed_rag.prompts import OUTCOME_EXTRACTION_SYSTEM


def _parse_json_object(raw: str) -> dict | list:
    text = raw.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        text = fence.group(1).strip()
    return json.loads(text)


def _outcomes_list_from_parsed(data: object) -> list:
    """LLM sometimes returns {"outcomes": [...]} or a raw list of outcome objects."""
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        o = data.get("outcomes", [])
        return o if isinstance(o, list) else []
    return []


def _normalize_ws(s: str) -> str:
    return " ".join(s.split())


def _split_passages_by_pmid(passages: str) -> list[tuple[str, str]]:
    """Return (pmid, block_text) for each `[PMID:...]` block."""
    if not passages or passages.strip() == "(No retrieved passages.)":
        return []
    blocks = re.split(r"\n---\n", passages)
    out: list[tuple[str, str]] = []
    for b in blocks:
        m = re.match(r"\[PMID:(\d+)\]\s*", b)
        if m:
            out.append((m.group(1), b))
    return out


def _allowed_pmids_set(allowed_pmids: str) -> set[str]:
    return set(re.findall(r"\d{5,10}", allowed_pmids or ""))


def _snippet_in_block(snippet: str, block: str) -> bool:
    sn = _normalize_ws(snippet).lower()
    bl = _normalize_ws(block).lower()
    if len(sn) < 12:
        return sn in bl
    # Prefer full substring; else try a stable prefix (verbatim copy often matches).
    if sn in bl:
        return True
    prefix = sn[: min(60, len(sn))]
    return len(prefix) >= 12 and prefix in bl


def _word_overlap_score(snippet: str, block: str) -> int:
    words = [
        w
        for w in re.findall(r"[a-z0-9%]+", snippet.lower())
        if len(w) > 2
    ]
    if not words:
        return 0
    t = block.lower()
    return sum(1 for w in words if w in t)


def _pmids_for_evidence(
    passages: str,
    snippet: str,
    allowed: set[str],
    llm_pmids: list[str],
) -> list[str]:
    """Restrict PMIDs to blocks that actually support the evidence snippet."""
    if not snippet.strip():
        return []
    blocks = _split_passages_by_pmid(passages)
    hits: list[str] = []
    for pmid, text in blocks:
        if pmid not in allowed:
            continue
        if _snippet_in_block(snippet, text):
            hits.append(pmid)
    if hits:
        return sorted(set(hits))[:3]

    # Model paraphrased or listed all PMIDs: pick best overlap (prefer LLM hint if tied).
    scored: list[tuple[int, int, str]] = []
    llm_set = {p for p in llm_pmids if p in allowed}
    for pmid, text in blocks:
        if pmid not in allowed:
            continue
        ov = _word_overlap_score(snippet, text)
        hint = 1 if pmid in llm_set else 0
        if ov > 0:
            scored.append((ov, hint, pmid))
    scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
    if scored:
        return [scored[0][2]]

    # Last resort: if LLM gave a small honest list, keep those in allowed.
    tight = [p for p in llm_pmids if p in allowed]
    if 1 <= len(tight) <= 3:
        return tight
    return []


def _adjust_direction(direction: str, outcome: str, snippet: str) -> str:
    """Avoid labeling incidence-only reports as worsened/increased."""
    d = (direction or "").strip().lower()
    s = (snippet or "").lower()
    oc = (outcome or "").lower()

    comparative = any(
        k in s
        for k in (
            "versus",
            "vs ",
            "vs.",
            "compared",
            "placebo",
            "higher rate",
            "lower rate",
            "worsen",
            "increased risk",
            "reduced risk",
        )
    )
    incidence_only = any(
        k in s for k in ("reported in", "% of those", "% of patients", " incidence")
    )

    if d in ("worsened", "increased") and incidence_only and not comparative:
        return "reported_incidence"

    if d in ("worsened", "increased") and oc in (
        "hypoglycemia",
        "hypoglycaemia",
        "severe hypoglycemia",
    ):
        if "reported" in s and "%" in s and not comparative:
            return "reported_incidence"

    return direction or "unclear"


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
def extract_outcomes_from_excerpts(
    question: str,
    focus_terms: str,
    allowed_pmids: str,
    passages: str,
    settings: Settings,
) -> list[dict]:
    llm = ChatOllama(
        base_url=settings.ollama_base_url,
        model=settings.ollama_model,
        temperature=0.0,
    )
    msg = (
        f"Question: {question}\n"
        f"Primary focus terms: {focus_terms}\n"
        f"Allowed PMIDs: {allowed_pmids}\n\n"
        f"Excerpts:\n{passages}\n\n"
        "Extract outcomes as JSON."
    )
    messages = [
        SystemMessage(content=OUTCOME_EXTRACTION_SYSTEM),
        HumanMessage(content=msg),
    ]
    resp = llm.invoke(messages)
    content = resp.content if hasattr(resp, "content") else str(resp)
    data = _parse_json_object(content)
    outcomes = _outcomes_list_from_parsed(data)
    if not isinstance(outcomes, list):
        return []

    allowed = _allowed_pmids_set(allowed_pmids)
    cleaned: list[dict] = []
    for o in outcomes:
        if not isinstance(o, dict):
            continue
        pmids = o.get("pmids", [])
        if isinstance(pmids, str):
            pmids = [pmids]
        if not isinstance(pmids, list):
            pmids = []
        raw_pmids = [str(p).strip() for p in pmids if str(p).strip()]

        row = {
            "outcome": str(o.get("outcome", "")).strip(),
            "direction": str(o.get("direction", "unclear")).strip(),
            "population": str(o.get("population", "")).strip(),
            "pmids": raw_pmids,
            "evidence_snippet": str(o.get("evidence_snippet", "")).strip()[:200],
        }
        if not row["outcome"] or not row["evidence_snippet"]:
            continue

        row["direction"] = _adjust_direction(
            row["direction"], row["outcome"], row["evidence_snippet"]
        )

        row["pmids"] = _pmids_for_evidence(
            passages, row["evidence_snippet"], allowed, raw_pmids
        )
        if not row["pmids"]:
            continue

        cleaned.append(row)

    return _dedupe_outcomes(cleaned)


def _dedupe_outcomes(rows: Iterable[dict]) -> list[dict]:
    """Keep first row per normalized outcome label to avoid duplicate table lines."""
    seen: set[str] = set()
    out: list[dict] = []
    for r in rows:
        key = re.sub(r"\s+", " ", (r.get("outcome") or "").strip().lower())
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out
