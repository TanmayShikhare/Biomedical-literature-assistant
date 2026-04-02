# Biomedical literature assistant

Search and summarize PubMed abstracts that **you** index locally. Responses link to the **underlying publications** so the text can be checked in the source. The stack runs on **your machine** (Python and [Ollama](https://ollama.com/) for the language model).

**Audience:** students and researchers who want **cited, literature-style summaries** over a **corpus they define**. This is **not** a substitute for reading papers or for clinical decisions.

---

## What this repository contains

| Item | Role |
|------|------|
| **`requirements.txt`** | Python dependencies (install with `pip`). |
| **`pyproject.toml`** | Package metadata for installing `src/biomed_rag` as a package (optional; `pip install -r requirements.txt` is the usual path). |
| **`.env.example`** | Environment variable template. Copy to **`.env`** and edit; **`.env` is not committed** to git. |
| **`Makefile`** | Shortcuts such as `make test` and `make install` (optional). |
| **`retrieval_eval.json`** | Optional **retrieval benchmark**: questions and PMIDs that should appear in the retrieval set after ingest. Used by `scripts/eval_retrieval.py` to check recall **without** calling the LLM. Not required to run the application. |
| **`data/eval_questions.json`** | Sample questions for `scripts/eval_smoke.py` (end-to-end check). |
| **`.github/workflows/ci.yml`** | Runs tests on push/pull request. |

---

## Clone vs. hosted app

GitHub stores **source code** only. It does not run Ollama, the vector index, or the server.

- **To run the app:** clone the repository, follow the steps below, and build a local index under `data/` (that directory is not part of git).
- **To offer a public URL:** deploy the same stack on a server you control (Python, dependencies, indexed data, and an LLM). There is no hosted demo included in this repository.

---

## Prerequisites

- Python **3.10+** (3.9 may work)
- Enough disk space for embeddings and the vector database (grows with corpus size)
- **[Ollama](https://ollama.com/)** for local inference (and optional relation extraction during ingest unless skipped)
- An **NCBI contact email** in `.env` when downloading from PubMed ([E-utilities policy](https://www.ncbi.nlm.nih.gov/books/NBK25497/))

---

## Setup and first run

1. **Virtual environment**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate    # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Environment file**
   ```bash
   cp .env.example .env
   ```
   Set at least `NCBI_EMAIL`. Set `OLLAMA_MODEL` as needed, then install the model, for example:
   ```bash
   ollama pull qwen2.5:7b
   ```

3. **Build an index** (creates files under `data/` locally; not stored in git)
   ```bash
   python scripts/ingest.py --max-papers 50
   ```
   Use a larger `--max-papers` value for a bigger corpus. After changing embedding settings, re-ingest with `--reset`. See `python scripts/ingest.py --help`.

4. **Optional:** corpus topic labels for the web UI
   ```bash
   python scripts/topics_fit.py
   ```

5. **Command-line query**
   ```bash
   python scripts/ask.py "Your question here"
   ```

6. **Browser UI and API** — with Ollama running (`ollama serve`):
   ```bash
   python scripts/serve.py
   ```
   Open [http://127.0.0.1:8000](http://127.0.0.1:8000). If the port is in use: `python scripts/serve.py --port 8001`.

If imports fail (e.g. `fastapi`), the active Python environment is wrong. Use this project’s interpreter: `.venv/bin/python scripts/serve.py`.

---

## Configuration

Copy from `.env.example`. Common variables:

| Variable | Purpose |
|----------|---------|
| `NCBI_EMAIL` | Required for PubMed ingest |
| `OLLAMA_MODEL` | Ollama model name |
| `OLLAMA_TEMPERATURE` | Synthesis temperature; `0.0` is a stable default |
| `EMBEDDING_MODEL` | Sentence-transformers model; change requires re-ingest with `--reset` |
| `RETRIEVAL_TOP_K`, `RERANK_TOP_K` | Retrieval breadth vs. number of passages sent to the model |

---

## Architecture (summary)

- **Ingest:** PubMed records → text chunks → embeddings in **Chroma**; optional extraction of relations to JSONL.
- **Query:** vector search, optional BM25 fusion, cross-encoder reranking, optional graph context, then a local LLM produces an answer restricted to citations from the retrieved set.
- **Serving:** `scripts/serve.py` exposes a static web UI and a JSON `POST /ask` endpoint.

---

## Tests and optional evaluations

```bash
make install
make test
```

Smoke test (requires a built index and Ollama):

```bash
python scripts/eval_smoke.py
```

Retrieval-only benchmark (optional; checks whether listed PMIDs appear in retrieval for each question):

```bash
python scripts/eval_retrieval.py
```

Edit **`retrieval_eval.json`** to match the corpus and the PMIDs that should be recoverable after ingest.

---

## Repository layout

| Path | Contents |
|------|----------|
| `src/biomed_rag/` | Application library |
| `scripts/` | Command-line tools (ingest, ask, serve, evaluation) |
| `web/` | Static assets for the browser UI |
| `data/` | Generated locally (index, manifests, etc.); only `eval_questions.json` is tracked in git |
| `tests/` | Automated tests |

---

## License

MIT. PubMed and publisher terms still govern use of downloaded metadata and full text where applicable.
