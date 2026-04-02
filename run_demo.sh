#!/usr/bin/env bash
# Full pipeline: requires Ollama running + .env with NCBI_EMAIL
set -euo pipefail
cd "$(dirname "$0")"

if ! curl -sS "http://127.0.0.1:11434/api/tags" >/dev/null 2>&1; then
  echo "Ollama does not respond at http://127.0.0.1:11434 — start the Ollama app or: ollama serve"
  exit 1
fi

if [[ ! -f .env ]]; then
  echo "Missing .env — run: cp .env.example .env && edit NCBI_EMAIL (and OLLAMA_MODEL if needed)"
  exit 1
fi

if [[ ! -d .venv ]]; then
  echo "Creating .venv …"
  python3 -m venv .venv
fi
# shellcheck source=/dev/null
source .venv/bin/activate
pip install -q -r requirements.txt

MAX="${1:-50}"
echo "=== Ingest (max $MAX papers) ==="
python scripts/ingest.py --max-papers "$MAX"

echo ""
echo "=== Ask (example question) ==="
python scripts/ask.py "What outcomes are commonly reported for semaglutide in type 2 diabetes?"
