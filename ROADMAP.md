# Roadmap — PubMed biomedical RAG + KG

**North star:** evidence-grounded Q&A over a **curated PubMed slice**, with **hybrid retrieval**, **reranking**, **graph context** (including cross-paper entity expansion), **citation discipline**, and **measured quality** — not a notebook demo.

## What “good RAG” means here (so we’re not arguing labels)

- **Retrieval**: relevant chunks for the question land in the top‑K after **dense + BM25 (RRF) + cross‑encoder rerank** — that is real multi-stage RAG, not “one embedding search and hope.”
- **Generation**: answers are **grounded in what was retrieved**; quality rises when the **corpus matches the question** and embeddings/rerank are tuned — not when we prettify prose after the fact.
- **KG in this repo**: PMID‑linked **LLM triples + entity overlap** across papers — useful context and navigation, **not** a full industrial ontology/SPARQL stack until we add entity IDs, linking, and eval.

**Corpus scale:** sub‑thousands can work for narrow queries; **1k–5k+ on‑topic abstracts** is the usual band where broad questions stop feeling empty. Default ingest target is **thousands** (`DEFAULT_INGEST_MAX_PAPERS`, CLI `--max-papers` overrides). Use `NCBI_API_KEY` for Entrez rate limits on large pulls.

## Phase 1 — Corpus you can defend

**Code / plumbing (done):**

- [x] Ingest from PubMed with configurable query + `--max-papers`
- [x] Persist Chroma + `triples.jsonl`; `--reset` clears caches
- [x] **`articles.jsonl`** merged manifest (title+abstract per PMID) for analytics / topic modeling
- [x] **`scripts/topics_fit.py`** — LDA + TF–IDF → `topic_model.json` (run after ingest)
- [x] **Default ingest cap** aligned to **thousands** (`default_ingest_max_papers`, Makefile `MAX=…`)

**Operational target (you must run ingest — not “done” until Chroma reflects it):**

- [ ] **Corpus in the intended band:** roadmap calls for **~1k–5k+ on-topic abstracts**. Hundreds (e.g. **762**) is a **dev slice**, not the main RAG corpus. Close Phase 1 by running a full ingest at **`--max-papers 2500`** or higher (see **RUNBOOK §6**), then **`scripts/corpus_stats.py`** until `unique_pmids_in_chroma` matches your target (or PubMed hit count for your query).

## Phase 2 — Retrieval (dense + sparse + rerank)

- [x] Wide **dense** recall → **cross-encoder rerank**
- [x] **BM25** index built at ingest; **RRF fusion** with dense (when index present)
- [ ] **You:** tune `RETRIEVAL_TOP_K`, `RERANK_TOP_K`, `HYBRID_DENSE_WEIGHT` / disable hybrid via `USE_HYBRID_RETRIEVAL=false` if debugging

## Phase 3 — Knowledge graph

- [x] LLM triples + PMID; **entity expansion** across papers (shared head/tail)
- [x] **`scripts/graph_export.py`** — stats + optional **GEXF** export for external graph tools
- [ ] Optional next: entity synonym table or MeSH-assisted filtering (only if it feeds retrieval or eval)

## Phase 4 — Trust & evaluation

- [x] Allowed-PMID whitelist in prompts; smoke eval script
- [x] **`retrieval_eval.json`** — 8 bundled rows (must-hit PMIDs from default incretin corpus); `scripts/eval_retrieval.py` reports per-question `pmid_recall`, aggregate pass rate, optional `--json-out` / `--min-question-pass-rate`
- [x] **`scripts/suggest_eval_pmids.py`** — grep `data/articles.jsonl` to pick PMIDs when adding rows
- [ ] Grow toward **20–50** labeled questions + track trends when you change retrieval weights or corpus

## Phase 5 — Shippable

- [x] Makefile, `pytest`, GitHub Actions CI
- [ ] Optional: Docker Compose (Ollama on host), structured logging

---

**Anti-patterns:** cosmetic answer post-processing instead of improving retrieval/corpus/graph; chasing every SOTA model without metrics.

---

## Execution order (do not skip Phase 1 scale)

1. **Phase 1 — Scale corpus:** `make ingest-scale-vectors MAX=2500` (or `3000` / `5000`) **or** `ingest-scale-vectors-partial-graph` if you want a big index + capped triples. Requires `.env` **`NCBI_EMAIL`**; use **`NCBI_API_KEY`** for thousands of IDs. Confirm: **`python scripts/corpus_stats.py`**.
2. **Phase 4 (retrieval):** **`python scripts/eval_retrieval.py`** — expand **`retrieval_eval.json`** toward 20–50 rows after the corpus changes (old gold PMIDs may disappear).
3. **Phase 2:** Tune **`RETRIEVAL_TOP_K`**, **`RERANK_TOP_K`**, hybrid flags in `.env` using eval metrics.
4. **Phase 4 (end-to-end):** **`python scripts/eval_smoke.py`** with Ollama — citation whitelist vs retrieval.
5. **Phase 3 / 5:** Graph export, topics, Docker/logging as needed.

Until step 1 shows **thousands** of PMIDs (or the maximum your PubMed query returns), treat the system as **under-built for broad RAG**, regardless of how many phases are checked off in code.
