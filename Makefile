.PHONY: install test ingest-smoke ingest-scale-vectors ingest-scale-vectors-partial-graph corpus-stats backfill-triples serve topics graph-stats graph-gexf eval-retrieval suggest-eval-pmids backfill-articles

# Override: `make ingest-scale-vectors MAX=3000`
MAX ?= 2500

install:
	python3 -m pip install -r requirements.txt

test:
	PYTHONPATH=src python3 -m pytest tests/ -q

# Requires .env with NCBI_EMAIL; small fetch for CI/local smoke (optional)
ingest-smoke:
	PYTHONPATH=src python3 scripts/ingest.py --reset --max-papers 5 --skip-graph

# Main dataset scale-up: PubMed → Chroma + BM25 only (no Ollama triples)
ingest-scale-vectors:
	PYTHONPATH=src python3 scripts/ingest.py --reset --max-papers $(MAX) --skip-graph

# Large vector index + triples for first 400 articles only
ingest-scale-vectors-partial-graph:
	PYTHONPATH=src python3 scripts/ingest.py --reset --max-papers $(MAX) --max-triple-articles 400

corpus-stats:
	PYTHONPATH=src python3 scripts/corpus_stats.py

# Triples only from existing articles.jsonl (Ollama; default first 400). Override: make backfill-triples LIMIT=200
LIMIT_TRIPLES ?= 400
backfill-triples:
	PYTHONPATH=src python3 scripts/backfill_triples.py --limit $(LIMIT_TRIPLES)

# After ingest: LDA topics (needs data/articles.jsonl)
topics:
	PYTHONPATH=src python3 scripts/topics_fit.py --n-topics 8

# Stats on triples.jsonl (needs data/triples.jsonl from ingest)
graph-stats:
	PYTHONPATH=src python3 scripts/graph_export.py

# Same + write GEXF for Gephi/Cytoscape
graph-gexf:
	PYTHONPATH=src python3 scripts/graph_export.py --write-gexf data/kg_graph.gexf

serve:
	PYTHONPATH=src python3 scripts/serve.py

# Default retrieval_eval.json (8 rows); measures recall without LLM
eval-retrieval:
	PYTHONPATH=src python3 scripts/eval_retrieval.py

# Find PMIDs in articles.jsonl matching keywords (for building retrieval_eval rows)
suggest-eval-pmids:
	PYTHONPATH=src python3 scripts/suggest_eval_pmids.py $(ARGS)

# Rebuild data/articles.jsonl from Chroma PMIDs (after older ingests)
backfill-articles:
	PYTHONPATH=src python3 scripts/backfill_articles_manifest.py
