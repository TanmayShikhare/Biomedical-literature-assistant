"""LLM-based triple extraction via local Ollama."""

from __future__ import annotations

import json
import re

from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage
from tenacity import retry, stop_after_attempt, wait_exponential

from biomed_rag.config import Settings
from biomed_rag.prompts import TRIPLE_EXTRACTION_SYSTEM


def _parse_json_object(raw: str) -> dict:
    text = raw.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        text = fence.group(1).strip()
    return json.loads(text)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
def extract_triples_from_abstract(
    title: str,
    abstract: str,
    settings: Settings,
) -> list[dict]:
    llm = ChatOllama(
        base_url=settings.ollama_base_url,
        model=settings.ollama_model,
        temperature=0.0,
    )
    body = f"Title: {title}\n\nAbstract: {abstract}"
    messages = [
        SystemMessage(content=TRIPLE_EXTRACTION_SYSTEM),
        HumanMessage(
            content=f"Extract triples as JSON from this abstract:\n\n{body}"
        ),
    ]
    resp = llm.invoke(messages)
    content = resp.content if hasattr(resp, "content") else str(resp)
    data = _parse_json_object(content)
    triples = data.get("triples", [])
    if not isinstance(triples, list):
        return []
    cleaned: list[dict] = []
    for t in triples:
        if not isinstance(t, dict):
            continue
        cleaned.append(
            {
                "head": str(t.get("head", "")).strip(),
                "head_type": str(t.get("head_type", "other")).strip(),
                "relation": str(t.get("relation", "related_to")).strip(),
                "tail": str(t.get("tail", "")).strip(),
                "tail_type": str(t.get("tail_type", "other")).strip(),
            }
        )
    return [t for t in cleaned if t["head"] and t["tail"]]
