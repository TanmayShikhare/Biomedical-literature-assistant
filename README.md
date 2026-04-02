# Biomed Literature RAG

**Hybrid RAG over a curated PubMed slice** — dense + BM25 retrieval, cross-encoder rerank, optional **knowledge-graph** context (Ollama-extracted triples), **LangGraph** orchestration, and a **local web UI** (FastAPI + static frontend). Answers are grounded with an **allowed-PMID** policy and researcher-oriented prompts.

> **Suggested GitHub repository name:** `pubmed-biomed-rag` (or `biomed-literature-rag`). The folder name can stay `pubmed_biomed_rag`.

---

## Who this is for

Researchers and reviewers who want **navigable, cited summaries** over a **defined literature subset** they control (ingest), not a black-box medical chatbot.

**Not medical advice.** Use for literature context and reference discovery only; verify claims in primary papers.

**NCBI:** Follow [E-utilities guidelines](https://www.ncbi.nlm.nih.gov/books/NBK25497/); set `NCBI_EMAIL` in `.env` for PubMed ingest.

---

## If I put this on GitHub, how do people “see” the app?

| What | Reality |
|------|---------|
| **GitHub** | Hosts **code** and small files (e.g. smoke questions). It does **not** run Ollama, Chroma, or your index. |
| **Visitors** | They **clone**, install, run **ingest** (to build `data/`), then **`serve.py`** — same as you. |
| **A public website** | You must **deploy** the stack somewhere (server + Python + disk + LLM). See **[DEPLOYMENT.md](DEPLOYMENT.md)**. |
| **Streamlit Cloud** | Only runs **Streamlit** apps. This project’s UI is **FastAPI + HTML/JS**. Moving to Streamlit means **rewriting the frontend**, not flipping a switch. The current UI works fine for local use and can be deployed with FastAPI anywhere Python runs. |

---

## Requirements

| Requirement | Notes |
|-------------|--------|
| **Python** | **3.10+** recommended (3.9 often works). |
| **Disk** | Chroma + embeddings + HF models grow with corpus size (gigabytes for thousands of papers). |
| **RAM** | Embedding models + Ollama (e.g. 7B) — plan several GB free. |
| **[Ollama](https://ollama.com/)** | Local LLM for **synthesis** and (if not `--skip-graph`) **triple extraction** during ingest. |
| **NCBI email** | Required in `.env` for **ingest** via Entrez. Optional `NCBI_API_KEY` for higher rate limits. |

---

## Quick start (clone → first query)

Do these **in order** from the repository root.

1. **Clone and enter the repo**
   ```bash
   git clone <your-repo-url>
   cd pubmed_biomed_rag
   ```

2. **Create a virtual environment and install dependencies**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate          # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Configure environment**
   ```bash
   cp .env.example .env
   ```
   Edit **`.env`**: set `NCBI_EMAIL`, and `OLLAMA_MODEL` (e.g. `qwen2.5:7b`). Pull the model:
   ```bash
   ollama pull qwen2.5:7b
   ```

4. **Ingest a small corpus** (creates `data/chroma`, `articles.jsonl`, BM25 index, optional triples — **not** in git; you build locally)
   ```bash
   python scripts/ingest.py --max-papers 50
   ```
   For a larger default slice and tuning, see **[RUNBOOK.md](RUNBOOK.md)**.

5. **(Optional) Topic labels for the UI**
   ```bash
   python scripts/topics_fit.py
   ```

6. **Ask from the terminal**
   ```bash
   python scripts/ask.py "What outcomes are reported for semaglutide in type 2 diabetes?"
   ```

7. **Run the web UI + API** (keep **Ollama** running in another terminal: `ollama serve`)
   ```bash
   source .venv/bin/activate
   python scripts/serve.py
   ```
   Open **http://127.0.0.1:8000/** (or `--port 8001` if 8000 is busy).

8. **Smoke check** (after ingest)
   ```bash
   python scripts/eval_smoke.py
   ```

**Wrong virtualenv?** If you see `No module named 'fastapi'`, you are not using this repo’s `.venv`. Run:
`.venv/bin/python scripts/serve.py`

---

## Configuration highlights (`.env`)

| Variable | Role |
|----------|------|
| `NCBI_EMAIL` | Required for ingest. |
| `OLLAMA_MODEL` / `OLLAMA_BASE_URL` | Chat model and Ollama URL. |
| `OLLAMA_TEMPERATURE` | Synthesis temperature; **0.0** recommended. |
| `EMBEDDING_MODEL` | Sentence-transformers id; after any change, **re-ingest with `--reset`**. |
| `RETRIEVAL_TOP_K`, `RERANK_TOP_K` | Chunk recall vs passages sent to the LLM. |
| `USE_HYBRID_RETRIEVAL`, `GRAPH_EXPAND_*` | BM25 + RRF and KG expansion. |

See **`.env.example`** for the full list.

---

## Stack (short)

- **Ingest:** Biopython Entrez → chunks → **sentence-transformers** → **Chroma**; optional Ollama **triples** → `triples.jsonl`.
- **Query:** **Dense + BM25 (RRF)** → **cross-encoder rerank** → graph context → **outcome JSON hint** → **Ollama synthesis** (citation clamping to retrieved PMIDs).
- **UI:** `GET /` static app, `POST /ask` JSON API, `GET /health`.

More detail: **[ROADMAP.md](ROADMAP.md)** · step-by-step ops: **[RUNBOOK.md](RUNBOOK.md)**.

---

## Scaling ingest

Vector index can reach **thousands** of papers; **triple extraction** is roughly **one LLM call per article** (slow at large N). Patterns:

- Full graph on subset: `ingest.py --max-papers 2000 --max-triple-articles 400`
- Vectors only: `--skip-graph`

Always use **`--reset`** when replacing an old index so chunk IDs and BM25 stay consistent.

**Retrieval QA:** `python scripts/eval_retrieval.py` (see `retrieval_eval.json`).

---

## Makefile

```bash
make install
make test
```

---

## Repository layout

| Path | Purpose |
|------|---------|
| `src/biomed_rag/` | Library (config, workflow, retrieval, prompts, …) |
| `scripts/` | CLI: `ingest.py`, `ask.py`, `serve.py`, `eval_smoke.py`, … |
| `web/` | Static frontend (served by `serve.py`) |
| `data/` | **Local only** (gitignored except `eval_questions.json`): Chroma, `articles.jsonl`, `triples.jsonl`, etc. |
| `data/eval_questions.json` | Bundled smoke questions (tracked in git) |
| `tests/` | `pytest` |

---

## License

**MIT.** PubMed metadata and publisher text remain subject to **NCBI** and publisher terms; do not redistribute full text against those terms.
