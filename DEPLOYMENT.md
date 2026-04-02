# Sharing & hosting

## What GitHub is for

GitHub stores **source code** and small fixtures (e.g. `data/eval_questions.json`). It does **not** run Ollama, Chroma, or your embeddings. Anyone who clones the repo must either:

1. **Run locally** (recommended for development and research use), or  
2. **Deploy** the app to a server they control and run ingest + Ollama (or adapt the code to use a remote LLM API).

## This project vs Streamlit Cloud

- **This repo** uses **FastAPI** + a static **HTML/JS** UI (`web/`). You can host that stack on any VPS or PaaS that runs Python.
- **[Streamlit Cloud](https://streamlit.io/cloud)** only runs **Streamlit** (`streamlit run app.py`). It does **not** serve this FastAPI app as-is. Adding Streamlit would mean a **second UI** (duplicate of the web app) unless you remove FastAPI entirely.

For a **public demo without teaching users to clone**, you still need: a server, Python env, indexed `data/` (or a volume), and a running LLM (Ollama on the same host or an API). There is no free one-click path that includes local Ollama + multi-GB indexes.

## Practical options

| Goal | Approach |
|------|----------|
| **Reproducible research / lab** | Push to GitHub; README + `.env.example`; others clone and follow [README](README.md). |
| **Small public demo** | Docker image + single VM (e.g. Fly.io, Railway, EC2) with Ollama + ingest baked or volume-mounted; expose `serve.py` behind HTTPS. |
| **API-only consumers** | Deploy FastAPI; document `POST /ask`; omit static UI or put UI on CDN. |

## Secrets

Never commit `.env`. Use `.env.example` only. For deploys, inject env vars via the platform’s secret store.
