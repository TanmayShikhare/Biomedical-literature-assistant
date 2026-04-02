"""Fetch PubMed records via NCBI Entrez (Medline)."""

from __future__ import annotations

import time
from typing import Any

from Bio import Entrez, Medline

from biomed_rag.config import Settings


def _sleep_entrez(settings: Settings) -> None:
    # Without API key: be conservative (~3 req/s). With key: still avoid bursts.
    delay = 0.12 if settings.ncbi_api_key else 0.35
    time.sleep(delay)


def _normalize_field(val: Any) -> str:
    if val is None:
        return ""
    if isinstance(val, list):
        return " ".join(str(x) for x in val).strip()
    return str(val).strip()


def medline_record_to_article(rec: dict[str, Any]) -> dict[str, str] | None:
    pmid = rec.get("PMID")
    if isinstance(pmid, list):
        pmid = pmid[0] if pmid else None
    pmid = _normalize_field(pmid)
    title = _normalize_field(rec.get("TI"))
    abstract = _normalize_field(rec.get("AB"))
    if not pmid or not abstract:
        return None
    return {"pmid": pmid, "title": title, "abstract": abstract}


def search_pubmed_ids(term: str, max_ids: int, settings: Settings) -> list[str]:
    if not settings.ncbi_email:
        raise ValueError("Set NCBI_EMAIL in .env (required by NCBI).")
    Entrez.email = settings.ncbi_email
    if settings.ncbi_api_key:
        Entrez.api_key = settings.ncbi_api_key

    ids: list[str] = []
    retstart = 0
    page_size = min(10_000, max_ids)

    while len(ids) < max_ids:
        handle = Entrez.esearch(
            db="pubmed",
            term=term,
            retmax=min(page_size, max_ids - len(ids)),
            retstart=retstart,
            sort="relevance",
        )
        record = Entrez.read(handle)
        handle.close()
        batch = record.get("IdList", [])
        if not batch:
            break
        ids.extend(batch)
        retstart += len(batch)
        if len(batch) < page_size:
            break
        _sleep_entrez(settings)

    return ids[:max_ids]


def fetch_articles_for_pmids(pmids: list[str], settings: Settings) -> list[dict[str, str]]:
    if not pmids:
        return []
    if not settings.ncbi_email:
        raise ValueError("Set NCBI_EMAIL in .env (required by NCBI).")
    Entrez.email = settings.ncbi_email
    if settings.ncbi_api_key:
        Entrez.api_key = settings.ncbi_api_key

    articles: list[dict[str, str]] = []
    batch_size = 200
    for i in range(0, len(pmids), batch_size):
        batch = pmids[i : i + batch_size]
        handle = Entrez.efetch(
            db="pubmed",
            id=",".join(batch),
            rettype="medline",
            retmode="text",
        )
        for rec in Medline.parse(handle):
            art = medline_record_to_article(rec)
            if art:
                articles.append(art)
        handle.close()
        _sleep_entrez(settings)

    return articles
