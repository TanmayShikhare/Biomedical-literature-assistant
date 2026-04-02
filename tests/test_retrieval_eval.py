"""Unit tests for retrieval eval (mocked retrieve, no Chroma)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def test_eval_rows_all_hit():
    from biomed_rag.retrieval_eval import eval_rows

    def fake_retrieve(state, settings):
        return {"allowed_pmids": "PMID 11111111 PMID 22222222", "top_passages": []}

    rows = [
        {"question": "q1", "must_include_pmids": ["11111111"]},
        {"question": "q2", "must_include_pmids": ["22222222", "11111111"]},
    ]
    out = eval_rows(rows, object(), retrieve_fn=fake_retrieve)
    assert len(out) == 2
    assert all(r.ok for r in out)
    assert out[1].pmid_recall == 1.0


def test_eval_rows_partial_miss():
    from biomed_rag.retrieval_eval import eval_rows

    def fake_retrieve(state, settings):
        return {"allowed_pmids": "PMID 99999999", "top_passages": []}

    rows = [{"question": "q", "must_include_pmids": ["11111111", "99999999"]}]
    out = eval_rows(rows, object(), retrieve_fn=fake_retrieve)
    assert len(out) == 1
    assert not out[0].ok
    assert out[0].pmid_recall == 0.5


def test_allowed_pmids_from_state():
    from biomed_rag.retrieval_eval import allowed_pmids_from_state

    assert allowed_pmids_from_state("foo PMID:12345 bar 99999999") == {"12345", "99999999"}
