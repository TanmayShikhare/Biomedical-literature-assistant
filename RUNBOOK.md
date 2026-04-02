# Runbook — one thing at a time

All paths assume the project folder:

`/Users/tanmayshikhare/Downloads/pubmed_biomed_rag`

Open **Terminal** (one window is enough unless noted).

---

## 1) Go to the project

```bash
cd /Users/tanmayshikhare/Downloads/pubmed_biomed_rag
```

---

## 2) Activate the virtualenv (if you use it)

```bash
source .venv/bin/activate
```

If you do not use `.venv`, skip this step.

---

## 3) Install dependencies (once, or after `requirements.txt` changes)

```bash
pip install -r requirements.txt
```

---

## 4) Configure NCBI (required for PubMed)

Create or edit `.env` in **this** folder (same level as `README.md`). Minimum:

```bash
NCBI_EMAIL=your_real_email@example.com
```

Optional: `NCBI_API_KEY=` for higher Entrez limits when ingesting thousands of papers.

---

## 4b) How big is the corpus **right now**?

The **main dataset** is whatever PubMed slice is in **Chroma** (`data/chroma/`), driven by `default_pubmed_query` in config (GLP-1 / incretin drugs ∧ diabetes or obesity by default).

```bash
PYTHONPATH=src python scripts/corpus_stats.py
```

Run this **before and after** a big ingest so you can see `unique_pmids_in_chroma` move.

---

## 5) Start Ollama (only when you need the LLM: ingest triples, `ask.py`, or `serve`)

In **this same terminal** (or a **second** terminal window if you prefer Ollama to stay visible):

```bash
ollama serve
```

Leave it running. In the **original** terminal (with `cd` and `venv` already done), pull a model if needed:

```bash
ollama pull llama3.2
```

---

## 6) Ingest PubMed → vectors + BM25 (+ optional KG triples)

**This is the lever that increases corpus size.** Eval scripts do **not** add papers; only `ingest.py` does.

Pick **one** path:

1. **Large index, no graph (fastest way to scale)** — good when you want thousands of abstracts without waiting on Ollama per paper:

   ```bash
   PYTHONPATH=src python scripts/ingest.py --reset --max-papers 2500 --skip-graph
   ```

2. **Large index + triples only on first N papers** — big RAG slice, bounded KG cost:

   ```bash
   PYTHONPATH=src python scripts/ingest.py --reset --max-papers 2500 --max-triple-articles 400
   ```

3. **Full re-ingest with triples on every paper** — slow at scale (one Ollama call per article); use for smaller N or overnight runs:

   ```bash
   PYTHONPATH=src python scripts/ingest.py --reset --max-papers 800
   ```

Default `--max-papers` if you omit the flag comes from config (`default_ingest_max_papers`, currently **2500**). Override with `--max-papers 3000` (or any cap PubMed returns for your query).

Custom slice: add `--query '...'` (PubMed search syntax), or set **`DEFAULT_PUBMED_QUERY`** in `.env` (maps to config `default_pubmed_query`).

- Omit `--reset` only if you are **merging** into an existing index on purpose (manifest merges PMIDs).
- After **any** full re-ingest, re-run **`corpus_stats.py`** and **`eval_retrieval.py`**; refresh **`retrieval_eval.json`** if your PMIDs no longer exist in the new slice.

---

## 6a) Triples only (after `ingest --skip-graph`)

If Chroma already has papers but **`data/triples.jsonl` is empty**, backfill triples from the manifest **without re-embedding** (Ollama must be running):

```bash
PYTHONPATH=src python scripts/backfill_triples.py --limit 400
```

Or `make backfill-triples` / `make backfill-triples LIMIT_TRIPLES=200`. Skips PMIDs already present in `triples.jsonl` unless you pass **`--force`**.

---

## 6b) If you ingested **before** `articles.jsonl` existed (topics need it)

This one command rebuilds `data/articles.jsonl` from PMIDs already in Chroma (same NCBI email as ingest):

```bash
PYTHONPATH=src python scripts/backfill_articles_manifest.py
```

---

## 7) Measure retrieval (no LLM — do this before trusting answers)

Default **`retrieval_eval.json`** has **8** questions with must-hit PMIDs (aligned to the bundled incretin corpus). Run:

```bash
PYTHONPATH=src python scripts/eval_retrieval.py
```

You should see **`questions_passed: 8/8`** after a good ingest. Add rows with PMIDs from your corpus:

```bash
PYTHONPATH=src python scripts/suggest_eval_pmids.py tirzepatide semaglutide
```

Optional: machine-readable metrics and CI gate:

```bash
PYTHONPATH=src python scripts/eval_retrieval.py --json-out /tmp/retrieval_metrics.json
PYTHONPATH=src python scripts/eval_retrieval.py --min-question-pass-rate 1.0
```

To start from a clean template: `cp retrieval_eval.example.json retrieval_eval.json`

Improve `RETRIEVAL_TOP_K`, `RERANK_TOP_K`, embedding model, or corpus — not post-processing — if this fails.

---

## 8) Ask one question

```bash
PYTHONPATH=src python scripts/ask.py --debug "Your question here"
```

---

## 9) Optional: topics (after ingest created `data/articles.jsonl`)

```bash
PYTHONPATH=src python scripts/topics_fit.py --n-topics 12
```

---

## 10) Optional: graph stats / GEXF (needs `data/triples.jsonl`)

```bash
PYTHONPATH=src python scripts/graph_export.py --write-gexf data/kg_graph.gexf
```

---

## What this stack is (no marketing)

- **RAG:** dense embeddings (Chroma) + optional BM25 fused with RRF + cross-encoder rerank → LLM reads passages + graph text + outcome JSON hints.
- **KG:** LLM-extracted triples in JSONL + entity overlap expansion; exportable to GEXF. Not a full ontology/SPARQL system until you add entity IDs and linking.

Stronger results: **bigger on-topic ingest**, **better `EMBEDDING_MODEL` + full re-ingest**, **tune retrieval eval**, **stronger Ollama model** when hardware allows.
